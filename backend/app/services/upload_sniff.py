"""Upload content sniffing: decide from the first bytes whether a file really is what it claims to be.

Why this exists: the browser-supplied Content-Type and the filename are attacker-controlled. A renamed
``.exe`` sent as ``image/png`` must not be stored as evidence media.

Design rule (deliberate): reject only when we are CONFIDENT.
  * Known executable/script/archive/document signatures are always refused for media uploads.
  * Images must carry a real image signature (the four formats we accept are unambiguous).
  * Video/audio containers are messy (``.mov`` atoms, WAV variants, ID3-less MP3). A recognised
    container of ANY audio/video kind is accepted for either an audio or a video claim. A file whose
    signature we simply do not recognise is ACCEPTED but flagged ``verified=False`` and written to the
    audit trail, unless ``UPLOAD_SNIFF_STRICT_AV=true``. That keeps odd-but-valid demo files working.

Modes (``UPLOAD_SNIFF_MODE``): ``enforce`` (default) rejects, ``log`` only records what it would have
rejected (use this to trial the check against real files first), ``off`` disables it.

Known limit: this reads the header only. A polyglot (valid PNG header followed by hostile bytes) passes;
images are protected separately by being fully decoded by Pillow and never served as executable content
(``X-Content-Type-Options: nosniff``, ``Content-Disposition: inline`` with a media type).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

HEAD_BYTES = 4096

# Final filename extensions that are never acceptable as media or evidence uploads.
DANGEROUS_EXTENSIONS = frozenset({
    ".exe", ".dll", ".scr", ".com", ".bat", ".cmd", ".msi", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse",
    ".wsf", ".sh", ".bash", ".run", ".bin", ".so", ".dylib", ".jar", ".apk", ".app", ".pif", ".lnk", ".reg",
    ".hta", ".cpl", ".php", ".phtml", ".py", ".pl", ".rb",
})

# (name, prefix) signatures that are executable code. Refused for media AND evidence uploads.
_EXECUTABLE = (
    ("windows-executable", b"MZ"),
    ("elf-executable", b"\x7fELF"),
    ("mach-o-executable", b"\xfe\xed\xfa\xce"), ("mach-o-executable", b"\xfe\xed\xfa\xcf"),
    ("mach-o-executable", b"\xce\xfa\xed\xfe"), ("mach-o-executable", b"\xcf\xfa\xed\xfe"),
    ("java-class-or-mach-o-fat", b"\xca\xfe\xba\xbe"),
    ("script", b"#!"),
)
# Not media. Refused for media uploads only (evidence may legitimately be a PDF, archive or saved page).
_NOT_MEDIA = (
    ("zip-or-office-archive", b"PK\x03\x04"), ("zip-or-office-archive", b"PK\x05\x06"),
    ("pdf", b"%PDF"), ("rar-archive", b"Rar!\x1a\x07"), ("7z-archive", b"7z\xbc\xaf\x27\x1c"),
    ("gzip-archive", b"\x1f\x8b"), ("ole-document", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"),
)
_TEXT_CODE = re.compile(rb"^(?:\xef\xbb\xbf)?\s*<(?:\?php|\?xml|!doctype|html|script|svg|%)", re.IGNORECASE)

# ISO base media (mp4, m4a, 3gp, QuickTime .mov): box type at offset 4. Old .mov files often start with
# moov/mdat/wide/free rather than ftyp.
_ISO_BOX_TYPES = frozenset({b"ftyp", b"moov", b"mdat", b"free", b"skip", b"wide", b"pnot", b"junk", b"uuid"})


@dataclass(frozen=True)
class SniffResult:
    ok: bool                 # False = refuse the upload (in enforce mode)
    detected: str | None     # what the bytes look like, e.g. "png", "mp4/quicktime", "windows-executable"
    verified: bool           # True = positively recognised as an acceptable type for the claim
    reason: str
    would_reject: bool = False  # set in "log" mode so callers can record it without refusing


def detect(head: bytes) -> tuple[str | None, str | None]:
    """Return (name, family). family is image | av | executable | not-media | None."""
    for name, prefix in _EXECUTABLE:
        if head.startswith(prefix):
            return name, "executable"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg", "image"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif", "image"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp", "image"
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return "avi", "av"
    if head[:4] in (b"RIFF", b"RIFX", b"RF64", b"BW64") and head[8:12] == b"WAVE":
        return "wav", "av"
    if head[4:8] in _ISO_BOX_TYPES:
        return "mp4/quicktime", "av"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm/matroska", "av"
    if head.startswith(b"OggS"):
        return "ogg", "av"
    if head.startswith(b"ID3") or (len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "mp3/aac", "av"
    for name, prefix in _NOT_MEDIA:
        if head.startswith(prefix):
            return name, "not-media"
    if _TEXT_CODE.match(head):
        return "html-or-script-text", "not-media"
    return None, None


def _ext(filename: str | None) -> str:
    return Path(filename or "").suffix.lower()


def safe_ext(filename: str | None) -> str:
    """A filename suffix that is safe to put in a stored path: dot plus up to 8 [a-z0-9] characters, else ''."""
    ext = _ext(filename)
    return ext if re.fullmatch(r"\.[a-z0-9]{1,8}", ext) else ""


def _decide(result: SniffResult, mode: str) -> SniffResult:
    if mode == "log" and not result.ok:
        return SniffResult(True, result.detected, False, result.reason, would_reject=True)
    return result


def sniff_media(head: bytes, claimed_kind: str, filename: str | None, *, mode: str = "enforce",
                strict_av: bool = False) -> SniffResult:
    """claimed_kind is image | video | audio (already derived from the declared Content-Type)."""
    mode = (mode or "enforce").lower()
    if mode == "off":
        return SniffResult(True, None, False, "content sniffing disabled")
    if _ext(filename) in DANGEROUS_EXTENSIONS:
        return _decide(SniffResult(False, None, False, f"File extension '{_ext(filename)}' is not allowed for media uploads."), mode)
    name, family = detect(head)
    if family in ("executable", "not-media"):
        return _decide(SniffResult(False, name, False, f"File content looks like {name}, not {claimed_kind}."), mode)
    if claimed_kind == "image":
        if family == "image":
            return SniffResult(True, name, True, "image signature recognised")
        if family == "av":
            return _decide(SniffResult(False, name, False, f"File content looks like {name}, not an image."), mode)
        return _decide(SniffResult(False, None, False, "File content is not a recognised JPEG, PNG, GIF or WebP image."), mode)
    # video / audio claims
    if family == "image":
        return _decide(SniffResult(False, name, False, f"File content looks like a {name} image, not {claimed_kind}."), mode)
    if family == "av":
        return SniffResult(True, name, True, "audio/video container recognised")
    if strict_av:
        return _decide(SniffResult(False, None, False, f"Could not recognise the {claimed_kind} container (strict mode)."), mode)
    return SniffResult(True, None, False, f"{claimed_kind} container not recognised; accepted unverified.")


def sniff_evidence(head: bytes, filename: str | None, *, mode: str = "enforce") -> SniffResult:
    """Evidence files may be PDFs, saved pages, archives: refuse only executable code."""
    mode = (mode or "enforce").lower()
    if mode == "off":
        return SniffResult(True, None, False, "content sniffing disabled")
    if _ext(filename) in DANGEROUS_EXTENSIONS:
        return _decide(SniffResult(False, None, False, f"File extension '{_ext(filename)}' is not allowed for evidence uploads."), mode)
    name, family = detect(head)
    if family == "executable":
        return _decide(SniffResult(False, name, False, f"File content looks like {name}; executable files cannot be stored as evidence."), mode)
    return SniffResult(True, name, name is not None, "no executable content detected")


def read_head(fileobj, n: int = HEAD_BYTES) -> bytes:
    """Peek at the start of an upload stream and rewind it."""
    head = fileobj.read(n) or b""
    try:
        fileobj.seek(0)
    except Exception:  # noqa: BLE001 — non-seekable stream: caller should not have passed it
        raise ValueError("Upload stream is not seekable")
    return head


def main(argv: list[str]) -> int:
    """Check files before a demo:  python -m app.services.upload_sniff clip.mov voice.wav photo.png"""
    if not argv:
        print("usage: python -m app.services.upload_sniff FILE [FILE ...]")
        return 2
    bad = 0
    kinds = {".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image", ".webp": "image",
             ".mp4": "video", ".mov": "video", ".webm": "video", ".avi": "video", ".mp3": "audio",
             ".wav": "audio", ".ogg": "audio", ".m4a": "audio"}
    for arg in argv:
        p = Path(arg)
        kind = kinds.get(p.suffix.lower(), "video")
        with p.open("rb") as fh:
            res = sniff_media(fh.read(HEAD_BYTES), kind, p.name)
        status = "OK        " if res.ok and res.verified else ("UNVERIFIED" if res.ok else "REFUSED   ")
        bad += 0 if res.ok else 1
        print(f"{status} {p.name}: {res.detected or 'unknown'} - {res.reason}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
