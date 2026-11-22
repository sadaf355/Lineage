"""
Provenance signals: Content Credentials (C2PA) and AI-generator markers.

Honesty rules (see docs/METADATA_FORENSICS.md):
  * The built-in reader only finds and describes the C2PA/JUMBF structure ("structural"). It does NOT verify signatures.
    Signature validation runs only when the optional `c2pa` Python package is installed; otherwise the result says so.
  * "No credentials found" and "credentials present" never mean the image is real or fake.
  * AI markers are claims written into the file. Absence proves nothing; presence shows what the file says about itself.
"""
from __future__ import annotations

import re
import struct
from typing import Any

from app.services.metadata_forensics import AI_NAMES, MAX_SCAN, _png_chunks, _png_text, read_xmp

_C2PA_ACTIONS = ("c2pa.created", "c2pa.edited", "c2pa.converted", "c2pa.cropped", "c2pa.filtered", "c2pa.placed", "c2pa.resized",
                 "c2pa.color_adjustments", "c2pa.drawing", "c2pa.orientation", "c2pa.published", "c2pa.transcoded", "c2pa.opened")
_DST_AI = ("trainedalgorithmicmedia", "compositewithtrainedalgorithmicmedia", "algorithmicmedia", "compositesynthetic")


def _jumbf_payloads(raw: bytes) -> list[bytes]:
    """Collect JUMBF byte runs: JPEG APP11 segments (marker 0xFFEB, 'JP' common identifier) and PNG caBX chunks."""
    out: list[bytes] = []
    try:
        if raw[:2] == b"\xff\xd8":
            i = 2
            while i + 4 <= len(raw) and raw[i] == 0xFF:
                marker = raw[i + 1]
                if marker in (0xDA, 0xD9):
                    break
                if marker == 0x01 or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                seglen = struct.unpack(">H", raw[i + 2:i + 4])[0]
                if marker == 0xEB:
                    seg = raw[i + 4:i + 2 + seglen]
                    if seg[:2] == b"JP":
                        out.append(seg[8:])          # skip CI(2) + En(2) + Z(4)
                i += 2 + seglen
        elif raw[:8] == b"\x89PNG\r\n\x1a\n":
            for ctype, data in _png_chunks(raw):
                if ctype == b"caBX":
                    out.append(data)
    except Exception:
        pass
    return out


def inspect_c2pa(raw: bytes) -> dict[str, Any]:
    """Structural look at Content Credentials, plus optional signature validation via the `c2pa` package if installed."""
    blobs = _jumbf_payloads(raw)
    joined = b"".join(blobs)
    present = b"c2pa" in joined or (not blobs and b"c2pa" in raw[:MAX_SCAN] and b"jumb" in raw[:MAX_SCAN])
    res: dict[str, Any] = {"present": bool(present), "validation": {"status": "not_validated", "reason": "structural read only"},
                           "labels": [], "actions": [], "claim_generator": None, "ai_marked": False}
    if not present:
        res["note"] = "No Content Credentials found. Most images carry none and platforms often strip them, so this says nothing about authenticity."
        return res
    data = joined or raw[:MAX_SCAN]
    labels = sorted({m.decode("ascii", "ignore") for m in re.findall(rb"c2pa(?:\.[a-z_]+)+", data)})
    res["labels"] = labels[:40]
    res["actions"] = [a for a in _C2PA_ACTIONS if a.encode() in data]
    m = re.search(rb"claim_generator(?:_info)?[^\x20-\x7e]{0,4}([\x20-\x7e]{3,80})", data)
    if m:
        res["claim_generator"] = m.group(1).decode("ascii", "ignore").strip()
    low = data.lower()
    res["ai_marked"] = any(d.encode() in low for d in _DST_AI)
    res["validation"] = _validate_with_library(raw)
    res["note"] = ("Content Credentials found. A valid signature shows who signed and that the file was not altered since signing; "
                   "it does not show that what the picture depicts is true.")
    return res


def _interpret_reader(info: dict[str, Any]) -> dict[str, Any]:
    """Turn the JSON from c2pa Reader into one of: valid, invalid, untrusted_signer. Pure; tested without the library.

    `validation_status` lists problems. A signer that is not on the trust list shows up as a code containing 'untrusted'
    (signingCredential.untrusted): the signature itself may be fine, so that is reported separately from 'invalid'."""
    failures = [f for f in (info.get("validation_status") or []) if isinstance(f, dict)]
    codes = [str(f.get("code")) for f in failures]
    active = (info.get("manifests") or {}).get(info.get("active_manifest"), {}) or {}
    signer = active.get("signature_info") or {}
    hard = [c for c in codes if "untrusted" not in c.lower()]
    if hard:
        status = "invalid"
    elif codes:
        status = "untrusted_signer"
    else:
        status = "valid"
    return {"status": status, "failures": codes[:10], "signer": signer.get("issuer") or signer.get("common_name"),
            "time": signer.get("time"),
            "trust": "signature checked; whether the signer is trusted depends on the trust anchors configured for the c2pa library"}


def _validate_with_library(raw: bytes) -> dict[str, Any]:
    """Optional: use the official `c2pa` package when installed. Unavailable here means 'not validated', never 'valid'."""
    try:
        import c2pa  # type: ignore
    except Exception:
        return {"status": "not_validated", "reason": "c2pa package not installed (pip install -r requirements-c2pa.txt)"}
    try:
        import io
        import json
        mime = "image/jpeg" if raw[:2] == b"\xff\xd8" else "image/png" if raw[:4] == b"\x89PNG" else "application/octet-stream"
        reader = c2pa.Reader(mime, io.BytesIO(raw))
        return _interpret_reader(json.loads(reader.json()))
    except Exception as exc:                      # a broken or truncated manifest, or an API change, is a finding, not a crash
        return {"status": "error", "reason": f"{type(exc).__name__}: {str(exc)[:160]}"}


def ai_markers(raw: bytes) -> list[dict[str, Any]]:
    """Markers a file claims about AI generation: XMP/IPTC DigitalSourceType, PNG generator text, software strings."""
    found: list[dict[str, Any]] = []
    xmp = read_xmp(raw)
    dst = (xmp.get("digital_source_type") or "").lower()
    if any(d in dst for d in _DST_AI):
        found.append({"type": "iptc_digital_source_type", "value": xmp["digital_source_type"], "strength": "claim",
                      "note": "The file states it was produced or composited with algorithmic (AI) media."})
    for k, v in _png_text(raw).items():
        kl, vl = k.lower(), v.lower()
        if kl in ("parameters", "prompt", "workflow", "negative_prompt") or "stable diffusion" in vl or "comfyui" in vl:
            found.append({"type": "png_generator_text", "value": f"{k}: {v[:160]}", "strength": "strong_claim",
                          "note": "Text written by common image-generation tools into the PNG."})
        else:
            nm = next((n for n in AI_NAMES if n in vl or n in kl), None)
            if nm:
                found.append({"type": "png_text_ai_name", "value": f"{k}: {v[:120]}", "strength": "claim", "note": f"Mentions '{nm}'."})
    head = raw[:MAX_SCAN].lower()
    for n in AI_NAMES:
        if n.encode() in head and n in ("midjourney", "dall-e", "firefly", "stable diffusion", "comfyui", "ideogram"):
            if not any(n in str(f["value"]).lower() for f in found):
                found.append({"type": "embedded_string", "value": n, "strength": "weak_claim",
                              "note": "The name appears somewhere in the file bytes; it may be a tag, a comment or coincidence."})
    return found
