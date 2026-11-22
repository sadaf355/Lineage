from __future__ import annotations

import ipaddress
import socket
from datetime import datetime
from io import BytesIO
from urllib.parse import urlparse

from PIL import Image, ExifTags


def media_metadata(raw: bytes, filename: str) -> dict:
    result = {
        "filename": filename,
        "mime_hint": None,
        "dimensions": None,
        "camera": None,
        "software": None,
        "timestamp": None,
        "generator_tags": [],
        "c2pa_present": False,
        "metadata_stripped": False,
    }
    try:
        im = Image.open(BytesIO(raw))
        result["dimensions"] = {"width": im.width, "height": im.height}
        result["mime_hint"] = im.format
        exif = im.getexif()
        tags = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
        result["camera"] = " ".join(str(x) for x in [tags.get("Make"), tags.get("Model")] if x) or None
        result["software"] = str(tags.get("Software")) if tags.get("Software") else None
        result["timestamp"] = str(tags.get("DateTimeOriginal") or tags.get("DateTime")) if (tags.get("DateTimeOriginal") or tags.get("DateTime")) else None
        generators = [tags.get(k) for k in ("Software", "ProcessingSoftware", "HostComputer") if tags.get(k)]
        result["generator_tags"] = [str(x) for x in generators]
        result["metadata_stripped"] = not bool(exif)
    except Exception as exc:
        result["error"] = f"Metadata could not be parsed: {type(exc).__name__}"
    low = raw[:2 * 1024 * 1024].lower()
    result["c2pa_present"] = b"c2pa" in low or b"jumbf" in low
    return result


def hosting_footprint(url: str) -> dict:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    ips: list[str] = []
    if host:
        try:
            ips = sorted({info[4][0] for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)})
        except OSError:
            ips = []
    public_ips = []
    for ip in ips:
        try:
            if not ipaddress.ip_address(ip).is_private:
                public_ips.append(ip)
        except ValueError:
            pass
    return {
        "domain": host,
        "server_ips": public_ips,
        "country": "Not resolved — hosting geolocation provider not configured",
        "captured_at": datetime.utcnow().isoformat() + "Z",
        "label": "Hosting server, not the creator",
    }
