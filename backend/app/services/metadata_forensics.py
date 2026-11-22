"""
Metadata forensics: does an image's metadata look changed since capture?

Design rules (see docs/METADATA_FORENSICS.md):
  * Every check returns a *signal* with its own caveat. Nothing here proves who edited a file or why.
  * Missing or stripped metadata is "cannot judge", never "tampered": most platforms strip it.
  * No XML parser is used on untrusted XMP (regex extraction only), so there is no XXE / entity-expansion surface.
  * All parsing is bounded: only the first MAX_SCAN bytes are scanned, and a malformed file yields "cannot judge", not an error.

Verdict ladder (the order matters):
    cannot_judge            no readable metadata at all
    no_signals              metadata present, nothing suspicious
    inconsistent_single   exactly one category of medium-or-higher signal
    inconsistent_multiple  two or more independent categories of medium-or-higher signals
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any

from PIL import Image, ImageChops

RULESET_VERSION = "2026.10-1"
MAX_SCAN = 4 * 1024 * 1024          # bytes of the file searched for XMP / markers
DATE_GAP_SECONDS = 300               # ModifyDate may trail DateTimeOriginal by this much before we flag it
THUMB_HASH_DISTANCE = 14             # out of 64 dHash bits
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3}

# Software names that indicate an editing / design / retouching tool (reviewed data, versioned with RULESET_VERSION).
EDITOR_NAMES = (
    "photoshop", "lightroom", "gimp", "snapseed", "canva", "pixlr", "paint.net", "affinity", "capture one", "picsart",
    "facetune", "remini", "fotor", "luminar", "photoscape", "paintshop", "corel", "krita", "photopea", "polarr",
    "vsco", "meitu", "beautyplus", "youcam", "airbrush", "adobe express", "illustrator", "inkscape", "darktable",
    "rawtherapee", "imagemagick", "pillow", "gd-jpeg", "ffmpeg",
)
# Software names that indicate an AI generator or AI editor.
AI_NAMES = (
    "midjourney", "stable diffusion", "stablediffusion", "dall-e", "dalle", "firefly", "comfyui", "automatic1111",
    "invokeai", "leonardo", "ideogram", "imagen", "flux", "sdxl", "novelai", "nightcafe", "dreamstudio", "gemini",
    "openai", "bing image creator", "copilot designer", "adobe firefly", "runway", "playground ai",
)
# A "software" string that looks like camera/phone firmware rather than an editor.
FIRMWARE_RE = re.compile(r"^(ver(sion)?[ .]*)?[a-z0-9\-_ ]*\d+(\.\d+)+[a-z0-9\-_ .]*$", re.I)
KNOWN_CAMERA_MAKES = ("canon", "nikon", "sony", "fujifilm", "panasonic", "olympus", "pentax", "leica", "apple", "samsung", "google", "huawei", "xiaomi", "oneplus")

# ---- IJG standard luminance quantisation table (natural order) used to recognise plain libjpeg re-saves
_STD_LUM = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
            18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92, 49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]
_ZIGZAG = [0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5, 12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
           35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51, 58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63]

# ---- EXIF tag ids used
T_MAKE, T_MODEL, T_SOFTWARE, T_DATETIME, T_ORIENT, T_HOST, T_PROCSW = 0x010F, 0x0110, 0x0131, 0x0132, 0x0112, 0x013C, 0x000B
T_EXIF_IFD, T_GPS_IFD = 0x8769, 0x8825
T_DTO, T_DTD, T_OFFSET, T_OFFSET_O, T_OFFSET_D = 0x9003, 0x9004, 0x9010, 0x9011, 0x9012
T_MAKERNOTE, T_EXPOSURE, T_ISO, T_PXX, T_PXY, T_USERCOMMENT, T_DESC = 0x927C, 0x829A, 0x8827, 0xA002, 0xA003, 0x9286, 0x010E
T_THUMB_OFF, T_THUMB_LEN = 0x0201, 0x0202


@dataclass
class Finding:
    id: str
    category: str
    title: str
    severity: str            # info | low | medium | high
    evidence: dict[str, Any]
    caveat: str


# ------------------------------------------------------------------ container helpers
def _find_exif_bytes(raw: bytes) -> bytes | None:
    """Return the TIFF-structured EXIF block (starting at the byte-order mark) from a JPEG, PNG, WebP or bare TIFF."""
    try:
        if raw[:2] == b"\xff\xd8":                                   # JPEG: walk the marker segments
            i = 2
            while i + 4 <= len(raw) and raw[i] == 0xFF:
                marker = raw[i + 1]
                if marker == 0xDA or marker == 0xD9:
                    break
                if marker == 0x01 or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                seglen = struct.unpack(">H", raw[i + 2:i + 4])[0]
                seg = raw[i + 4:i + 2 + seglen]
                if marker == 0xE1 and seg[:6] == b"Exif\x00\x00":
                    return seg[6:]
                i += 2 + seglen
            return None
        if raw[:8] == b"\x89PNG\r\n\x1a\n":                          # PNG: eXIf chunk
            for ctype, data in _png_chunks(raw):
                if ctype == b"eXIf":
                    return data
            return None
        if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":              # WebP: EXIF chunk
            i = 12
            while i + 8 <= len(raw):
                ctype = raw[i:i + 4]
                size = struct.unpack("<I", raw[i + 4:i + 8])[0]
                if ctype == b"EXIF":
                    d = raw[i + 8:i + 8 + size]
                    return d[6:] if d[:6] == b"Exif\x00\x00" else d
                i += 8 + size + (size & 1)
            return None
        if raw[:4] in (b"II*\x00", b"MM\x00*"):
            return raw
    except Exception:
        return None
    return None


def _png_chunks(raw: bytes):
    i = 8
    while i + 8 <= len(raw):
        size = struct.unpack(">I", raw[i:i + 4])[0]
        ctype = raw[i + 4:i + 8]
        data = raw[i + 8:i + 8 + size]
        yield ctype, data
        i += 12 + size
        if ctype == b"IEND":
            break


def _png_text(raw: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        return out
    try:
        for ctype, data in _png_chunks(raw):
            if ctype == b"tEXt" and b"\x00" in data:
                k, v = data.split(b"\x00", 1)
                out[k.decode("latin-1")[:80]] = v.decode("latin-1")[:4000]
            elif ctype == b"iTXt" and b"\x00" in data:
                k, rest = data.split(b"\x00", 1)
                if len(rest) >= 2 and rest[0] == 0:                  # uncompressed only; compressed chunks are skipped, not decoded
                    parts = rest[2:].split(b"\x00", 2)
                    if len(parts) == 3:
                        out[k.decode("utf-8", "replace")[:80]] = parts[2].decode("utf-8", "replace")[:4000]
            elif ctype == b"zTXt" and b"\x00" in data:
                k = data.split(b"\x00", 1)[0]
                out[k.decode("latin-1")[:80]] = "(compressed text chunk not decoded)"
    except Exception:
        pass
    return out


# ------------------------------------------------------------------ minimal TIFF/EXIF reader (bounded, no recursion bombs)
_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}


def _read_ifd(buf: bytes, off: int, bo: str) -> tuple[dict[int, Any], int]:
    """Return ({tag: value}, next_ifd_offset). Raises on malformed data; callers catch."""
    tags: dict[int, Any] = {}
    n = struct.unpack(bo + "H", buf[off:off + 2])[0]
    if n > 512:
        raise ValueError("implausible IFD size")
    for k in range(n):
        e = off + 2 + 12 * k
        tag, typ, cnt = struct.unpack(bo + "HHI", buf[e:e + 8])
        size = _TYPE_SIZE.get(typ)
        if size is None or cnt > 1_000_000:
            continue
        total = size * cnt
        data = buf[e + 8:e + 12] if total <= 4 else buf[struct.unpack(bo + "I", buf[e + 8:e + 12])[0]:][:total]
        if len(data) < total:
            continue
        tags[tag] = _decode_value(typ, cnt, data, bo)
    nxt = struct.unpack(bo + "I", buf[off + 2 + 12 * n:off + 6 + 12 * n])[0] if off + 6 + 12 * n <= len(buf) else 0
    return tags, nxt


def _decode_value(typ: int, cnt: int, data: bytes, bo: str):
    if typ == 2:
        return data.split(b"\x00", 1)[0].decode("utf-8", "replace").strip()
    if typ in (1, 7):
        return bytes(data) if typ == 7 else list(data) if cnt > 1 else data[0]
    fmt = {3: "H", 4: "I", 6: "b", 8: "h", 9: "i", 11: "f", 12: "d"}.get(typ)
    if typ in (5, 10):
        f = "II" if typ == 5 else "ii"
        vals = [struct.unpack(bo + f, data[i * 8:i * 8 + 8]) for i in range(cnt)]
        vals = [(a / b if b else 0.0) for a, b in vals]
        return vals if cnt > 1 else vals[0]
    vals = list(struct.unpack(bo + fmt * cnt, data[:cnt * struct.calcsize(fmt)]))
    return vals if cnt > 1 else vals[0]


def parse_exif(tiff: bytes) -> dict[str, Any]:
    """Return {'ifd0': {...}, 'exif': {...}, 'gps': {...}, 'ifd1': {...}, 'thumbnail': bytes|None}. Empty dict on failure."""
    try:
        bo = "<" if tiff[:2] == b"II" else ">" if tiff[:2] == b"MM" else None
        if bo is None or struct.unpack(bo + "H", tiff[2:4])[0] != 42:
            return {}
        ifd0_off = struct.unpack(bo + "I", tiff[4:8])[0]
        ifd0, nxt = _read_ifd(tiff, ifd0_off, bo)
        out: dict[str, Any] = {"ifd0": ifd0, "exif": {}, "gps": {}, "ifd1": {}, "thumbnail": None}
        for key, tag in (("exif", T_EXIF_IFD), ("gps", T_GPS_IFD)):
            if isinstance(ifd0.get(tag), int):
                try:
                    out[key], _ = _read_ifd(tiff, ifd0[tag], bo)
                except Exception:
                    out[key] = {}
        if nxt:
            try:
                ifd1, _ = _read_ifd(tiff, nxt, bo)
                out["ifd1"] = ifd1
                off, ln = ifd1.get(T_THUMB_OFF), ifd1.get(T_THUMB_LEN)
                if isinstance(off, int) and isinstance(ln, int) and 0 < ln < 2_000_000:
                    th = tiff[off:off + ln]
                    out["thumbnail"] = th if th[:2] == b"\xff\xd8" else None
            except Exception:
                pass
        return out
    except Exception:
        return {}


# ------------------------------------------------------------------ XMP (regex only)
_XMP_RE = re.compile(rb"<x:xmpmeta.*?</x:xmpmeta>", re.S)


def read_xmp(raw: bytes) -> dict[str, Any]:
    m = _XMP_RE.search(raw[:MAX_SCAN])
    if not m:
        return {}
    text = m.group(0).decode("utf-8", "replace")
    out: dict[str, Any] = {"present": True}

    def attr_or_elem(name: str) -> str | None:
        a = re.search(rf'{re.escape(name)}="([^"]*)"', text)
        if a:
            return a.group(1)
        e = re.search(rf"<{re.escape(name)}>([^<]*)</{re.escape(name)}>", text)
        return e.group(1) if e else None

    for key, name in (("creator_tool", "xmp:CreatorTool"), ("create_date", "xmp:CreateDate"), ("modify_date", "xmp:ModifyDate"),
                      ("metadata_date", "xmp:MetadataDate"), ("digital_source_type", "Iptc4xmpExt:DigitalSourceType"),
                      ("original_document_id", "xmpMM:OriginalDocumentID"), ("derived_from", "stRef:documentID"),
                      ("history_agent_first", "stEvt:softwareAgent")):
        v = attr_or_elem(name)
        if v:
            out[key] = v[:300]
    events = re.findall(r'stEvt:action="([^"]+)"', text) + re.findall(r"<stEvt:action>([^<]+)</stEvt:action>", text)
    agents = re.findall(r'stEvt:softwareAgent="([^"]+)"', text) + re.findall(r"<stEvt:softwareAgent>([^<]+)</stEvt:softwareAgent>", text)
    if events:
        out["history_actions"] = events[:50]
    if agents:
        out["history_agents"] = sorted(set(agents))[:20]
    return out


# ------------------------------------------------------------------ helpers
def _parse_exif_dt(s: Any) -> datetime | None:
    if not isinstance(s, str):
        return None
    s = s.strip().replace("\x00", "")
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def _parse_xmp_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d.replace(tzinfo=None) if d.tzinfo is None else d.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return _parse_exif_dt(s)


def _parse_offset(s: Any) -> timedelta | None:
    if not isinstance(s, str):
        return None
    m = re.fullmatch(r"\s*([+-])(\d{2}):?(\d{2})\s*", s)
    if not m:
        return None
    d = timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
    return d if m.group(1) == "+" else -d


def _dhash(img: Image.Image) -> int:
    g = img.convert("L").resize((9, 8), Image.LANCZOS)
    px = list(g.tobytes())
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (1 if px[r * 9 + c] > px[r * 9 + c + 1] else 0)
    return bits


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _name_match(value: str, names: tuple[str, ...]) -> str | None:
    low = value.lower()
    for n in names:
        if n in low:
            return n
    return None


def jpeg_quant_tables(raw: bytes) -> list[list[int]]:
    tables: list[list[int]] = []
    if raw[:2] != b"\xff\xd8":
        return tables
    i = 2
    try:
        while i + 4 <= len(raw) and raw[i] == 0xFF:
            marker = raw[i + 1]
            if marker in (0xDA, 0xD9):
                break
            if marker == 0x01 or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seglen = struct.unpack(">H", raw[i + 2:i + 4])[0]
            if marker == 0xDB:
                seg = raw[i + 4:i + 2 + seglen]
                j = 0
                while j < len(seg):
                    pq, _tq = seg[j] >> 4, seg[j] & 15
                    j += 1
                    n = 128 if pq else 64
                    vals = seg[j:j + n]
                    j += n
                    if len(vals) < n:
                        break
                    q = [struct.unpack(">H", vals[k:k + 2])[0] for k in range(0, n, 2)] if pq else list(vals)
                    nat = [0] * 64
                    for z, pos in enumerate(_ZIGZAG):
                        nat[pos] = q[z]
                    tables.append(nat)
            i += 2 + seglen
    except Exception:
        pass
    return tables


def estimate_ijg_quality(table: list[int]) -> int | None:
    """Exact match against libjpeg's scaled standard table, or None (camera-specific / custom tables return None)."""
    for q in range(1, 101):
        scale = 5000 // q if q < 50 else 200 - q * 2
        cand = [min(255, max(1, (v * scale + 50) // 100)) for v in _STD_LUM]
        if cand == table:
            return q
    return None


def error_level(raw: bytes, quality: int = 90) -> dict[str, float] | None:
    """Mean / max pixel difference after a recompression. Supporting statistic only: re-saves by any platform change it too."""
    try:
        img = Image.open(BytesIO(raw))
        if img.format != "JPEG" or img.width * img.height > 12_000_000:
            return None
        rgb = img.convert("RGB")
        buf = BytesIO()
        rgb.save(buf, "JPEG", quality=quality)
        diff = ImageChops.difference(rgb, Image.open(BytesIO(buf.getvalue())).convert("RGB"))
        hist = diff.convert("L").histogram()
        n = sum(hist) or 1
        mean = sum(i * c for i, c in enumerate(hist)) / n
        mx = max((i for i, c in enumerate(hist) if c), default=0)
        return {"mean": round(mean, 3), "max": float(mx), "quality": quality}
    except Exception:
        return None


# ------------------------------------------------------------------ main analysis
def analyze(raw: bytes, filename: str | None = None, *, uploaded_at: datetime | None = None, now: datetime | None = None,
            date_gap_seconds: int = DATE_GAP_SECONDS) -> dict[str, Any]:
    """Analyse one image. Never raises on bad input; returns verdict 'cannot_judge' with a reason instead."""
    now = now or datetime.utcnow()
    result: dict[str, Any] = {"ruleset_version": RULESET_VERSION, "filename": filename, "supported": True, "findings": [],
                              "fields": {}, "limits": [], "analysed_at": now.isoformat() + "Z"}
    try:
        img = Image.open(BytesIO(raw))
        fmt = img.format
        size = img.size
        if len(raw) < 25_000_000:
            img.load()
    except Exception:
        result.update(supported=False, verdict="cannot_judge", reason="not_a_readable_image")
        result["limits"].append("The file could not be read as an image, so no metadata analysis was possible.")
        return result
    result["fields"]["format"], result["fields"]["width"], result["fields"]["height"] = fmt, size[0], size[1]

    exif_bytes = _find_exif_bytes(raw)
    ex = parse_exif(exif_bytes) if exif_bytes else {}
    xmp = read_xmp(raw)
    png_text = _png_text(raw)
    ifd0, exif_ifd, gps, thumb = ex.get("ifd0", {}), ex.get("exif", {}), ex.get("gps", {}), ex.get("thumbnail")

    f: dict[str, Any] = result["fields"]
    f.update({
        "make": ifd0.get(T_MAKE), "model": ifd0.get(T_MODEL),
        "software": ifd0.get(T_SOFTWARE), "host_computer": ifd0.get(T_HOST), "processing_software": ifd0.get(T_PROCSW),
        "datetime_original": exif_ifd.get(T_DTO), "datetime_digitized": exif_ifd.get(T_DTD), "datetime_modified": ifd0.get(T_DATETIME),
        "offset_time_original": exif_ifd.get(T_OFFSET_O) or exif_ifd.get(T_OFFSET),
        "has_exif": bool(ex), "has_xmp": bool(xmp), "has_png_text": bool(png_text), "has_thumbnail": thumb is not None,
        "has_maker_note": T_MAKERNOTE in exif_ifd, "has_gps": bool(gps),
        "xmp": {k: v for k, v in xmp.items() if k != "present"} or None,
    })

    findings: list[Finding] = []

    # --- T1 editing software
    sw_values = {k: v for k, v in (("Software", f["software"]), ("HostComputer", f["host_computer"]), ("ProcessingSoftware", f["processing_software"]),
                                    ("xmp:CreatorTool", xmp.get("creator_tool"))) if isinstance(v, str) and v}
    for fld, val in sw_values.items():
        ed = _name_match(val, EDITOR_NAMES)
        ai = _name_match(val, AI_NAMES)
        if ai:
            findings.append(Finding("T1", "software", "AI tool named in metadata", "medium", {"field": fld, "value": val, "matched": ai},
                                    "A software tag can be written or copied by anyone; it shows what the file says, not what happened."))
        elif ed:
            findings.append(Finding("T1", "software", "Editing software named in metadata", "medium", {"field": fld, "value": val, "matched": ed},
                                    "Editors are also used for harmless changes (crop, brightness); a tag cannot show what was changed."))
        elif not FIRMWARE_RE.match(val) and fld == "Software":
            findings.append(Finding("T1", "software", "Unrecognised software string", "info", {"field": fld, "value": val},
                                    "Not on the editor list and not a firmware-style version; shown for the reviewer."))

    # --- T2 dates
    dto, dtd, dtm = _parse_exif_dt(f["datetime_original"]), _parse_exif_dt(f["datetime_digitized"]), _parse_exif_dt(f["datetime_modified"])
    xmod, xcre = _parse_xmp_dt(xmp.get("modify_date")), _parse_xmp_dt(xmp.get("create_date"))
    capture = dto or dtd or xcre
    modified = dtm or xmod
    if capture and modified and modified - capture > timedelta(seconds=date_gap_seconds):
        gap = modified - capture
        findings.append(Finding("T2", "dates", "File was saved after the capture time", "medium",
                                {"capture": capture.isoformat(sep=" "), "modified": modified.isoformat(sep=" "), "gap_seconds": int(gap.total_seconds()),
                                 "gap_text": _human_gap(gap)},
                                "Some cameras and phones write ModifyDate later (for example after in-camera processing), and clocks can be wrong."))
    for label, d in (("DateTimeOriginal", dto), ("ModifyDate", dtm)):
        if d and d > now + timedelta(days=1):
            findings.append(Finding("T2", "dates", f"{label} is in the future", "medium", {"field": label, "value": d.isoformat(sep=" ")},
                                    "A wrong device clock produces the same result."))
    if capture and uploaded_at and capture > uploaded_at + timedelta(hours=1):
        findings.append(Finding("T2", "dates", "Capture time is later than the upload time", "medium",
                                {"capture": capture.isoformat(sep=" "), "uploaded_at": uploaded_at.isoformat(sep=" ")},
                                "Time zones can shift the comparison by up to a day; the device clock can also be wrong."))
    if modified and not capture:
        findings.append(Finding("T2", "dates", "A modify date exists but no capture date", "low", {"modified": modified.isoformat(sep=" ")},
                                "Capture dates are often removed by platforms or by privacy tools."))

    # --- T3 thumbnail vs image
    if thumb:
        try:
            timg = Image.open(BytesIO(thumb))
            timg.load()
            main = img.convert("RGB")
            th = timg.convert("RGB")
            best = _hamming(_dhash(main), _dhash(th))
            for rot in (90, 270):                              # thumbnails are sometimes stored rotated relative to the pixel data
                best = min(best, _hamming(_dhash(main), _dhash(th.rotate(rot, expand=True))))
            ar_main, ar_th = size[0] / size[1], timg.size[0] / max(1, timg.size[1])
            ar_diff = abs(ar_main - ar_th) / max(ar_main, ar_th)
            ar_diff_rot = abs(ar_main - 1 / ar_th) / max(ar_main, 1 / ar_th)
            f["thumbnail_distance"] = best
            aspect_gap = min(ar_diff, ar_diff_rot)
            if best > THUMB_HASH_DISTANCE or aspect_gap > 0.25:
                findings.append(Finding("T3", "thumbnail", "Embedded thumbnail does not match the image", "high",
                                        {"hash_distance_of_64": best, "threshold": THUMB_HASH_DISTANCE, "aspect_difference": round(aspect_gap, 3)},
                                        "Common after editing without regenerating the thumbnail; very small or heavily cropped thumbnails can also differ."))
        except Exception:
            result["limits"].append("The embedded thumbnail could not be decoded.")

    # --- T4 structure
    make = (f["make"] or "") if isinstance(f["make"], str) else ""
    if sw_values.get("Software") and not make and not f["model"] and f["has_exif"]:
        findings.append(Finding("T4", "structure", "Software tag present but no camera make or model", "low", {"software": sw_values.get("Software")},
                                "Exports and screenshots look like this; so do photos whose camera fields were stripped."))
    if make and any(k in make.lower() for k in KNOWN_CAMERA_MAKES):
        missing = [n for n, t in (("MakerNote", T_MAKERNOTE), ("ExposureTime", T_EXPOSURE), ("ISO", T_ISO)) if t not in exif_ifd]
        if missing and f["has_exif"]:
            findings.append(Finding("T4", "structure", "Camera fields that normally accompany this make are missing", "low", {"make": make, "missing": missing},
                                    "Platforms and privacy tools remove these fields; editors often drop MakerNote."))

    # --- T5 time zone / GPS time
    off = _parse_offset(f["offset_time_original"])
    lon = _gps_deg(gps.get(4), gps.get(3))
    if off is not None and lon is not None:
        expected = round(lon / 15.0)
        got = off.total_seconds() / 3600
        if abs(got - expected) > 3:
            findings.append(Finding("T5", "timezone", "Time-zone offset does not fit the GPS longitude", "low",
                                    {"offset_hours": got, "expected_hours_from_longitude": expected},
                                    "Political time zones differ from longitude; the camera may still be set to its home zone."))
    gps_date, gps_time = gps.get(0x1D), gps.get(0x07)
    if dto and off is not None and isinstance(gps_date, str) and isinstance(gps_time, list) and len(gps_time) == 3:
        try:
            gdt = datetime.strptime(gps_date.strip(), "%Y:%m:%d") + timedelta(hours=gps_time[0], minutes=gps_time[1], seconds=gps_time[2])
            if abs((dto - off) - gdt) > timedelta(hours=1):
                findings.append(Finding("T5", "timezone", "GPS time and capture time disagree", "medium",
                                        {"gps_utc": gdt.isoformat(sep=" "), "capture_as_utc": (dto - off).isoformat(sep=" ")},
                                        "GPS time is only written by some devices; an unsynchronised clock produces this too."))
        except Exception:
            pass

    # --- T6 dimensions
    pxx, pxy = exif_ifd.get(T_PXX), exif_ifd.get(T_PXY)
    if isinstance(pxx, int) and isinstance(pxy, int) and (pxx, pxy) != size and (pxy, pxx) != size:
        findings.append(Finding("T6", "dimensions", "Declared pixel size differs from the real size", "low",
                                {"declared": [pxx, pxy], "actual": list(size)},
                                "Resizers and croppers that keep old EXIF leave this behind; it says the image was processed."))

    # --- T7 JPEG forensics (supporting statistics, never a verdict on their own)
    if fmt == "JPEG":
        qts = jpeg_quant_tables(raw)
        if qts:
            q = estimate_ijg_quality(qts[0])
            f["jpeg_ijg_quality"] = q
            if q is not None and make and any(k in make.lower() for k in KNOWN_CAMERA_MAKES):
                findings.append(Finding("T7", "jpeg", "Quantisation tables match a standard software encoder", "info",
                                        {"estimated_quality": q, "make": make},
                                        "Most cameras use their own tables; a standard table suggests the pixels were re-encoded by software at some point (editing or a platform)."))
        el = error_level(raw)
        if el:
            f["error_level"] = el
            result["limits"].append("Error-level statistics are supporting information only: every platform re-save changes them.")

    # --- T8 edit history in XMP
    acts = [a for a in xmp.get("history_actions", []) if a.lower() in {"saved", "converted", "derived", "edited", "cropped", "filtered", "placed", "color_adjustments", "resized", "transcoded"}]
    if acts:
        findings.append(Finding("T8", "history", "Embedded edit history lists changes", "medium",
                                {"actions": acts[:15], "agents": xmp.get("history_agents", [])},
                                "History is written by the editing program and can be removed or forged; its presence shows an editor touched the file."))
    elif xmp.get("derived_from") or xmp.get("original_document_id"):
        findings.append(Finding("T8", "history", "File is marked as derived from another document", "low",
                                {"derived_from": xmp.get("derived_from"), "original_document_id": xmp.get("original_document_id")},
                                "Derivation markers are written by editors and some export tools."))

    # --- verdict
    has_any_metadata = bool(ex) or bool(xmp) or bool(png_text)
    result["findings"] = [asdict(x) for x in findings]
    cats = sorted({x.category for x in findings if SEVERITY_ORDER[x.severity] >= SEVERITY_ORDER["medium"]})
    result["signal_categories"] = cats
    if not has_any_metadata:
        result["verdict"] = "cannot_judge"
        result["reason"] = "no_metadata"
        result["limits"].append("This file has no EXIF, XMP or text metadata. Most social platforms and messaging apps remove it, so this says nothing about whether the image was edited.")
    elif len(cats) >= 2:
        result["verdict"] = "inconsistent_multiple"
    elif len(cats) == 1:
        result["verdict"] = "inconsistent_single"
    else:
        result["verdict"] = "no_signals"
    result["limits"].append("Metadata can be edited, copied or invented. This analysis never proves who changed a file, when, or why, and a clean result does not prove the image is genuine.")
    return result


def _gps_deg(v: Any, ref: Any) -> float | None:
    try:
        d, m, s = v
        deg = d + m / 60 + s / 3600
        return -deg if str(ref).upper() in ("W", "S") else deg
    except Exception:
        return None


def _human_gap(gap: timedelta) -> str:
    s = int(gap.total_seconds())
    if s >= 86400:
        return f"{s // 86400} day(s) {((s % 86400) // 3600)} hour(s)"
    if s >= 3600:
        return f"{s // 3600} hour(s) {((s % 3600) // 60)} minute(s)"
    return f"{s // 60} minute(s) {s % 60} second(s)"


# ------------------------------------------------------------------ wording
_EN = {
    "cannot_judge": "Cannot judge: this file has no usable metadata, so nothing can be said about whether it was changed.",
    "no_signals": "No signs of change found in the metadata. This does not prove the image is genuine.",
    "inconsistent_single": "The metadata is inconsistent in one respect. This is a lead to investigate. Without a preserved earlier copy, LINEAGE cannot say the file was changed.",
    "inconsistent_multiple": "The metadata is inconsistent in several independent respects. This is a stronger lead, but without a preserved earlier copy LINEAGE cannot say the file was changed.",
}
_HI = {   # Drafted for review by a Hindi-speaking reviewer before use in legal documents.
    "cannot_judge": "निर्णय संभव नहीं: इस फ़ाइल में उपयोगी मेटाडेटा नहीं है, इसलिए यह नहीं कहा जा सकता कि इसे बदला गया या नहीं।",
    "no_signals": "मेटाडेटा में बदलाव के कोई संकेत नहीं मिले। इसका अर्थ यह नहीं कि चित्र असली है।",
    "inconsistent_single": "मेटाडेटा एक बिंदु पर असंगत है। यह जाँच का सुराग है; पहले की सुरक्षित प्रति के बिना यह नहीं कहा जा सकता कि फ़ाइल बदली गई।",
    "inconsistent_multiple": "मेटाडेटा कई स्वतंत्र बिंदुओं पर असंगत है। यह मज़बूत सुराग है, पर पहले की सुरक्षित प्रति के बिना यह नहीं कहा जा सकता कि फ़ाइल बदली गई।",
}
_CAVEAT = {"en": "This is a signal, not proof of who changed the file, when, or why.",
           "hi": "यह एक संकेत है, इस बात का प्रमाण नहीं कि फ़ाइल किसने, कब या क्यों बदली।"}


def describe(report: dict[str, Any], lang: str = "en") -> str:
    """One plain-language paragraph that names the exact fields and values behind the verdict."""
    table = _HI if lang == "hi" else _EN
    parts = [table[report["verdict"]]]
    for fd in report.get("findings", []):
        if SEVERITY_ORDER[fd["severity"]] >= SEVERITY_ORDER["medium"]:
            ev = fd["evidence"]
            bits = "; ".join(f"{k} = {v}" for k, v in ev.items() if v not in (None, "", []))
            parts.append(f"- {fd['title']} ({bits}).")
    parts.append(_CAVEAT["hi" if lang == "hi" else "en"])
    return "\n".join(parts)


def diff_reports(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    """T9 metadata drift: which key fields differ between two copies of the same image."""
    keys = ("make", "model", "software", "datetime_original", "datetime_modified", "has_exif", "has_xmp", "has_thumbnail", "has_maker_note", "has_gps", "width", "height", "format")
    out = []
    for k in keys:
        va, vb = a.get("fields", {}).get(k), b.get("fields", {}).get(k)
        if va != vb:
            out.append({"field": k, "a": va, "b": vb})
    return out
