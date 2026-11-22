"""Immutable upload-time metadata snapshots and conservative comparison."""
import hashlib, json, re
from datetime import datetime
from PIL import Image
from app.models.media import MetadataSnapshot
PARSER_NAME = "Pillow-EXIF-XMP"
PARSER_VERSION = "1.0.0"

def _extract_xmp(raw: bytes) -> dict:
    """Extract bounded XMP attribute/element text without invoking an XML parser."""
    out = {}
    sample = raw[:4 * 1024 * 1024]
    for match in re.finditer(rb"<x:xmpmeta\b.*?</x:xmpmeta>|<xmpmeta\b.*?</xmpmeta>", sample, re.I | re.S):
        packet = match.group(0)[:512_000].decode("utf-8", "replace")
        for m in re.finditer(r"([A-Za-z_][\w:.-]{0,100})\s*=\s*['\"]([^'\"]{0,2000})['\"]", packet):
            out["xmp:" + m.group(1)] = m.group(2)
        for m in re.finditer(r"<([A-Za-z_][\w:.-]{0,100})>([^<]{1,2000})</\1>", packet):
            out["xmp:" + m.group(1)] = m.group(2).strip()
    return out

def _extract_iptc_jpeg(raw: bytes) -> dict:
    """Read simple IPTC IIM records from Photoshop APP13 resources (bounded, no XML)."""
    out = {}; i = 2; limit = min(len(raw), 4 * 1024 * 1024)
    if raw[:2] != b"\xff\xd8": return out
    while i + 4 <= limit and raw[i] == 0xff:
        marker = raw[i+1]
        if marker in (0xda, 0xd9): break
        length = int.from_bytes(raw[i+2:i+4], "big")
        segment = raw[i+4:i+2+length]
        if marker == 0xed and segment.startswith(b"Photoshop 3.0\x00"):
            j=14
            while j+12 <= len(segment):
                if segment[j:j+4] != b"8BIM": break
                resource=int.from_bytes(segment[j+4:j+6],"big"); j+=6
                name_len=segment[j]; j+=1+name_len
                if (1+name_len) % 2: j+=1
                if j+4>len(segment): break
                size=int.from_bytes(segment[j:j+4],"big"); j+=4
                block=segment[j:j+size]; j+=size+(size%2)
                if resource == 0x0404:
                    k=0
                    while k+5<=len(block):
                        if block[k] != 0x1c: k+=1; continue
                        record, dataset = block[k+1], block[k+2]; n=int.from_bytes(block[k+3:k+5],"big"); k+=5
                        if n & 0x8000 or k+n>len(block): break
                        value=block[k:k+n].decode("utf-8","replace")[:2000]; k+=n
                        out[f"iptc:{record}:{dataset}"]=value
        i += 2 + length
    return out

def parse_metadata(raw: bytes, filename: str = "") -> tuple[dict, dict]:
    fields = {"filename": filename}
    fields.update(_extract_xmp(raw))
    fields.update(_extract_iptc_jpeg(raw))
    try:
        import io
        with Image.open(io.BytesIO(raw)) as im:
            fields.update({"format": im.format, "width": im.width, "height": im.height, "mode": im.mode})
            # Include bounded container/ICC/XMP/IPTC-style metadata exposed by Pillow.
            for key, value in (im.info or {}).items():
                if key.lower() in {"icc_profile"}:
                    fields["icc_profile_sha256"] = hashlib.sha256(value).hexdigest() if isinstance(value, bytes) else str(value)[:200]
                elif isinstance(value, bytes):
                    if len(value) <= 256_000:
                        fields[str(key)] = value.decode("utf-8", "replace")[:20_000]
                elif isinstance(value, (str, int, float, bool)):
                    fields[str(key)] = value[:20_000] if isinstance(value, str) else value
            exif = im.getexif()
            for key, value in exif.items():
                try:
                    from PIL.ExifTags import TAGS
                    name = TAGS.get(key, str(key))
                    if isinstance(value, bytes): value = value.decode("utf-8", "replace")
                    elif not isinstance(value, (str, int, float, bool, list, tuple)): value = str(value)
                    fields[str(name)] = value
                except Exception: continue
    except Exception as exc:
        fields["parse_error"] = type(exc).__name__
    raw_fields = fields
    normalized = {str(k).strip().lower(): (v.strip() if isinstance(v, str) else v) for k,v in fields.items()}
    return raw_fields, normalized

def create_snapshot(db, media, raw: bytes):
    raw_fields, normalized = parse_metadata(raw, media.original_filename)
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
    snap = MetadataSnapshot(media_item_id=media.id, parser_name=PARSER_NAME, parser_version=PARSER_VERSION, file_sha256=media.sha256 or hashlib.sha256(raw).hexdigest(), raw_fields_json=json.dumps(raw_fields, sort_keys=True, default=str), normalized_fields_json=canonical, snapshot_sha256=hashlib.sha256(canonical.encode()).hexdigest(), taken_at=datetime.utcnow())
    db.add(snap); db.flush(); return snap

def compare_snapshots(previous, current_fields: dict | None, file_sha256: str | None = None):
    if previous is None: return {"state":"unknown", "reason":"No preserved earlier metadata snapshot exists."}
    prior = json.loads(previous.normalized_fields_json)
    current = current_fields or {}
    # File identity/geometry are not provenance metadata; their presence must not
    # mask the fact that EXIF/XMP/IPTC/ICC metadata was stripped from a later copy.
    structural = {"filename", "format", "width", "height", "mode", "parse_error"}
    prior = {k:v for k,v in prior.items() if k not in structural}
    current = {k:v for k,v in current.items() if k not in structural}
    if prior and not current:
        return {"state":"stripped", "reason":"Metadata present in the preserved snapshot is absent from the re-check."}
    if not current:
        return {"state":"stripped", "reason":"No comparable metadata fields are present in the re-check."}
    shared = set(prior) & set(current)
    if not shared: return {"state":"unknown", "reason":"There are no comparable fields."}
    differences = [k for k in sorted(shared) if str(prior[k]) != str(current[k])]
    if differences:
        return {"state":"changed against snapshot", "reason":"Fields differ from a preserved earlier snapshot.", "changed_fields":differences}
    if set(prior) - set(current): return {"state":"inconsistent", "reason":"Some earlier fields are absent, but stripping cannot be distinguished from parser coverage."}
    return {"state":"unchanged", "reason":"Comparable metadata fields match the preserved snapshot."}
