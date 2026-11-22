from __future__ import annotations

import hashlib


def sha256_bytes(data: bytes) -> str:
    """Return the canonical lowercase SHA-256 hex digest for stored bytes."""
    return hashlib.sha256(data).hexdigest()


def verify_sha256(data: bytes, expected: str | None) -> tuple[bool, str]:
    """Re-hash bytes and compare against a stored digest."""
    actual = sha256_bytes(data)
    return bool(expected) and actual == expected, actual
