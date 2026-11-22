"""Test helper: build real EXIF/TIFF bytes and splice them into JPEG / PNG files. Used only by tests."""
import struct
from io import BytesIO

from PIL import Image

ASCII, SHORT, LONG, RATIONAL, UNDEF = 2, 3, 4, 5, 7


def _enc(typ, val):
    if typ == ASCII:
        b = val.encode() + b"\x00"
        return len(b), b
    if typ == SHORT:
        vals = val if isinstance(val, list) else [val]
        return len(vals), struct.pack("<" + "H" * len(vals), *vals)
    if typ == LONG:
        vals = val if isinstance(val, list) else [val]
        return len(vals), struct.pack("<" + "I" * len(vals), *vals)
    if typ == RATIONAL:
        vals = val if isinstance(val, list) else [val]
        return len(vals), b"".join(struct.pack("<II", int(round(v * 1000)), 1000) for v in vals)
    if typ == UNDEF:
        return len(val), val
    raise ValueError(typ)


def _ifd_bytes(entries, base, next_off=0):
    """entries: {tag: (type, value)}; data larger than 4 bytes goes after the IFD. Returns bytes placed at offset `base`."""
    n = len(entries)
    head = 2 + 12 * n + 4
    data = b""
    rows = b""
    for tag in sorted(entries):
        typ, val = entries[tag]
        cnt, b = _enc(typ, val)
        if len(b) <= 4:
            rows += struct.pack("<HHI", tag, typ, cnt) + b.ljust(4, b"\x00")
        else:
            rows += struct.pack("<HHI", tag, typ, cnt) + struct.pack("<I", base + head + len(data))
            data += b + (b"\x00" if len(b) % 2 else b"")
    return struct.pack("<H", n) + rows + struct.pack("<I", next_off) + data


def _ifd_size(entries):
    return len(_ifd_bytes(entries, 0))


def build_tiff(ifd0, exif=None, gps=None, thumb=None):
    ifd0 = dict(ifd0)
    exif = dict(exif or {})
    gps = dict(gps or {})
    # placeholders so sizes are right
    if exif:
        ifd0[0x8769] = (LONG, 0)
    if gps:
        ifd0[0x8825] = (LONG, 0)
    off = 8
    ifd0_size = _ifd_size(ifd0)
    exif_off = off + ifd0_size
    exif_size = _ifd_size(exif) if exif else 0
    gps_off = exif_off + exif_size
    gps_size = _ifd_size(gps) if gps else 0
    ifd1_off = gps_off + gps_size if thumb else 0
    if exif:
        ifd0[0x8769] = (LONG, exif_off)
    if gps:
        ifd0[0x8825] = (LONG, gps_off)
    out = b"II*\x00" + struct.pack("<I", 8)
    out += _ifd_bytes(ifd0, off, ifd1_off)
    if exif:
        out += _ifd_bytes(exif, exif_off)
    if gps:
        out += _ifd_bytes(gps, gps_off)
    if thumb:
        ifd1 = {0x0201: (LONG, 0), 0x0202: (LONG, len(thumb))}
        thumb_off = ifd1_off + _ifd_size(ifd1)
        ifd1[0x0201] = (LONG, thumb_off)
        out += _ifd_bytes(ifd1, ifd1_off) + thumb
    return out


def jpeg(size=(96, 64), color=(120, 80, 40), quality=85, pattern=True):
    img = Image.new("RGB", size, color)
    if pattern:
        px = img.load()
        for x in range(size[0]):
            for y in range(size[1]):
                px[x, y] = ((x * 3 + color[0]) % 256, (y * 4 + color[1]) % 256, ((x + y) * 2 + color[2]) % 256)
    buf = BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def jpeg_bytes_of(img, quality=85):
    buf = BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def with_exif(jpeg_bytes, tiff):
    seg = b"Exif\x00\x00" + tiff
    app1 = b"\xff\xe1" + struct.pack(">H", len(seg) + 2) + seg
    return jpeg_bytes[:2] + app1 + jpeg_bytes[2:]


def with_xmp(jpeg_bytes, xmp_xml):
    payload = b"http://ns.adobe.com/xap/1.0/\x00" + xmp_xml.encode()
    app1 = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    return jpeg_bytes[:2] + app1 + jpeg_bytes[2:]


def png_with_text(img, text: dict):
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    for k, v in text.items():
        info.add_text(k, v)
    buf = BytesIO()
    img.save(buf, "PNG", pngitxt=None, pnginfo=info)
    return buf.getvalue()
