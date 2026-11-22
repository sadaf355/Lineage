"""Upload malware / decompression-bomb screening. Modes: off | log | enforce."""
from __future__ import annotations

import socket
import struct
from dataclasses import dataclass

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@dataclass
class ScanResult:
    ok: bool
    reason: str | None = None
    engine: str = "builtin"


def scan_eicar(data: bytes) -> ScanResult:
    if EICAR in data:
        return ScanResult(False, "EICAR test signature", "builtin")
    return ScanResult(True)


CHUNK = 64 * 1024
HEADER_BYTES = 1024 * 1024        # enough to reach the size marker of any normal JPEG/PNG/GIF/WEBP


class _ClamdStream:
    """One clamd INSTREAM conversation fed chunk by chunk, so the file is never held in memory.
    Any socket problem marks the stream failed; the caller then reports 'clamd unavailable'."""

    def __init__(self, host: str, port: int, timeout: float):
        self.sock = None
        self.failed = False
        self.timeout = timeout
        try:
            self.sock = socket.create_connection((host, port), timeout=timeout)
            self.sock.settimeout(timeout)
            self.sock.sendall(b"zINSTREAM\0")
        except OSError:
            self.failed = True

    def feed(self, chunk: bytes) -> None:
        if self.failed or not chunk:
            return
        try:
            self.sock.sendall(struct.pack(">I", len(chunk)) + chunk)
        except OSError:
            self.failed = True

    def finish(self) -> ScanResult:
        if self.failed:
            self.close()
            return ScanResult(True, "clamd unavailable", "clamd")
        try:
            self.sock.sendall(struct.pack(">I", 0))
            resp = b""
            while not resp.endswith(b"\0") and len(resp) < 4096:
                part = self.sock.recv(1024)
                if not part:
                    break
                resp += part
        except OSError:
            self.close()
            return ScanResult(True, "clamd unavailable", "clamd")
        self.close()
        txt = resp.strip(b"\0").decode("utf-8", "replace")
        if txt.endswith("FOUND"):
            return ScanResult(False, txt, "clamd")
        if txt.endswith("OK"):
            return ScanResult(True, None, "clamd")
        return ScanResult(True, "clamd unavailable", "clamd")      # e.g. 'INSTREAM size limit exceeded. ERROR'

    def close(self) -> None:
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass


def scan_clamd(data: bytes, host: str, port: int, timeout: float = 5.0) -> ScanResult:
    """clamd INSTREAM for an in-memory buffer. Any connection problem returns ok=True with reason 'clamd unavailable'
    so callers can decide (enforce mode treats unavailable as a refusal)."""
    st = _ClamdStream(host, port, timeout)
    for i in range(0, len(data), CHUNK):
        st.feed(data[i:i + CHUNK])
    return st.finish()


def image_pixels(data: bytes) -> int | None:
    """Pixel count from the header only (PNG/JPEG/GIF/WEBP-VP8X); never decodes."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        w, h = struct.unpack(">II", data[16:24])
        return w * h
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        w, h = struct.unpack("<HH", data[6:10])
        return w * h
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            seglen = struct.unpack(">H", data[i + 2:i + 4])[0]
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w * h
            i += 2 + seglen
        return None
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and data[12:16] == b"VP8X" and len(data) >= 30:
        w = 1 + int.from_bytes(data[24:27], "little")
        h = 1 + int.from_bytes(data[27:30], "little")
        return w * h
    return None


def scan_stream(fileobj, *, mode: str, max_pixels: int, max_bytes: int = 0, clamd_host: str = "", clamd_port: int = 3310,
                clamd_timeout: float = 15.0) -> ScanResult:
    """Scan an upload in 64 KB chunks: memory use is constant however large the file is. Leaves the stream rewound.

    Order: header-only pixel limit, then one pass feeding the built-in EICAR check and (when clamd_host is set) clamd.
    `max_bytes` (0 = no cap) stops reading and refuses, so a scan can never be made to read without limit."""
    if (mode or "off").lower() == "off":
        return ScanResult(True, "scanning disabled")
    try:
        fileobj.seek(0)
        head = fileobj.read(HEADER_BYTES) or b""
        px = image_pixels(head)
        if px is not None and max_pixels and px > max_pixels:
            return ScanResult(False, f"image has {px} pixels (limit {max_pixels})", "pixel-guard")
        clam = _ClamdStream(clamd_host, clamd_port, clamd_timeout) if clamd_host else None
        carry, total, chunk = b"", 0, head
        while chunk:
            total += len(chunk)
            if max_bytes and total > max_bytes:
                if clam:
                    clam.close()
                return ScanResult(False, f"file is larger than the scan limit ({max_bytes} bytes)", "size-guard")
            window = carry + chunk
            if EICAR in window:
                if clam:
                    clam.close()
                return ScanResult(False, "EICAR test signature", "builtin")
            carry = window[-(len(EICAR) - 1):]
            if clam:
                clam.feed(chunk)
            chunk = fileobj.read(CHUNK)
        return clam.finish() if clam else ScanResult(True, None, "builtin")
    finally:
        try:
            fileobj.seek(0)
        except Exception:  # noqa: BLE001
            pass


def scan(data: bytes, *, mode: str, max_pixels: int, clamd_host: str = "", clamd_port: int = 3310,
         clamd_timeout: float = 5.0) -> ScanResult:
    """In-memory convenience wrapper around scan_stream (used by tests and small buffers)."""
    import io
    return scan_stream(io.BytesIO(data), mode=mode, max_pixels=max_pixels, clamd_host=clamd_host,
                       clamd_port=clamd_port, clamd_timeout=clamd_timeout)
