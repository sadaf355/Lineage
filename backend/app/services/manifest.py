"""Phase E — signed integrity manifest (Ed25519) with an optional RFC 3161 trusted timestamp.

What this proves, and what it does not
--------------------------------------
* The manifest lists every preserved item in a case with its SHA-256 and is signed with this deployment's
  Ed25519 key. Anyone holding the *published* public key can confirm the list was produced by this deployment
  and has not been edited since.
* The embedded public key inside an envelope is a convenience only. A verifier who trusts the envelope's own key
  has proved self-consistency, nothing more. Compare ``key_id`` against the key published out-of-band
  (``GET /trust/manifest-key``, printed on the report, or held by the court/registry).
* The optional RFC 3161 token is issued by an independent Time-Stamp Authority and proves the *signature* existed
  at the stated time. This module checks the token's message imprint, nonce and generation time. It does NOT
  validate the TSA's CMS signature or certificate chain in-process; use ``openssl ts -verify`` (see docs/EVIDENCE_INTEGRITY.md)
  for that. The result says so explicitly rather than implying full validation.

The pure functions here take explicit arguments and import settings lazily so they can be unit-tested without the app.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

SCHEMA = "lineage.manifest/1"
SIGNATURE_ALGORITHM = "Ed25519"
SHA256_OID = "2.16.840.1.101.3.4.2.1"


class ManifestError(Exception):
    """Raised for signing-key problems or malformed envelopes."""


class TimestampError(Exception):
    """Raised when a TSA request fails or its reply is not a granted RFC 3161 response."""


# --------------------------------------------------------------------------------------------------
# Canonical JSON
# --------------------------------------------------------------------------------------------------

def canonical_json(obj: Any) -> bytes:
    """Deterministic UTF-8 JSON: sorted keys, no whitespace. The manifest contains no floats by design."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(text: str) -> bytes:
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except Exception as exc:  # noqa: BLE001 - normalise every decoding failure
        raise ManifestError("Invalid base64 value in envelope.") from exc


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat(timespec="seconds") + "Z"


# --------------------------------------------------------------------------------------------------
# Keys
# --------------------------------------------------------------------------------------------------

def parse_private_key(raw: str) -> Ed25519PrivateKey:
    """Accept a PEM private key or a base64 (standard or URL-safe) 32-byte seed."""
    raw = raw.strip()
    if raw.startswith("-----BEGIN"):
        key = serialization.load_pem_private_key(raw.encode("ascii"), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ManifestError("MANIFEST_SIGNING_KEY must be an Ed25519 key.")
        return key
    try:
        seed = base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_")
    except Exception as exc:  # noqa: BLE001
        raise ManifestError("MANIFEST_SIGNING_KEY is neither PEM nor base64.") from exc
    if len(seed) != 32:
        raise ManifestError("MANIFEST_SIGNING_KEY must decode to exactly 32 bytes.")
    return Ed25519PrivateKey.from_private_bytes(seed)


def public_key_bytes(key: Ed25519PrivateKey | Ed25519PublicKey) -> bytes:
    pub = key.public_key() if isinstance(key, Ed25519PrivateKey) else key
    return pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(public_raw: bytes) -> str:
    """Short, stable fingerprint of a public key (first 16 hex chars of SHA-256 over the raw key)."""
    return sha256_hex(public_raw)[:16]


def generate_seed_b64() -> str:
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


def load_signing_key() -> Ed25519PrivateKey:
    """Resolve the deployment signing key from settings; auto-create a persisted dev key only in dev/test."""
    from app.core.config import get_settings

    s = get_settings()
    raw = (s.MANIFEST_SIGNING_KEY or "").strip()
    if raw:
        return parse_private_key(raw)
    if s.ENV.lower() not in {"development", "dev", "test"}:
        raise ManifestError("MANIFEST_SIGNING_KEY must be supplied by the deployment secret manager outside development/test.")
    path = Path(s.DATA_DIR) / ".manifest_signing_key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return parse_private_key(path.read_text())
    seed = generate_seed_b64()
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(seed)
    return parse_private_key(seed)


def public_key_info(key: Ed25519PrivateKey | None = None) -> dict:
    key = key or load_signing_key()
    raw = public_key_bytes(key)
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")
    return {"algorithm": SIGNATURE_ALGORITHM, "key_id": key_id(raw), "public_key": _b64(raw), "public_key_pem": pem}


# --------------------------------------------------------------------------------------------------
# Building the manifest
# --------------------------------------------------------------------------------------------------

def build_entries(media: Iterable[Any], evidence: Iterable[Any], sources: Iterable[Any]) -> list[dict]:
    """Flatten ORM rows into manifest entries. Only recorded facts: no scores, no model output."""
    entries: list[dict] = []
    for m in media:
        entries.append({"kind": "media", "id": m.id, "filename": m.original_filename, "sha256": m.sha256,
                        "size_bytes": m.file_size_bytes, "recorded_at": _iso(m.uploaded_at)})
    for e in evidence:
        entries.append({"kind": "evidence", "id": e.id, "item_type": e.item_type, "sha256": e.sha256,
                        "source_id": e.source_id, "recorded_at": _iso(e.captured_at)})
    for s in sources:
        # Only sources that carry a captured page hash are integrity-relevant; seeded/manual ones are listed with null.
        entries.append({"kind": "source", "id": s.id, "platform": s.platform, "url": s.url,
                        "sha256": s.page_sha256, "recorded_at": _iso(s.observed_at)})
    entries.sort(key=lambda x: (x["kind"], x["id"]))
    return entries


def build_manifest(incident_id: str, entries: list[dict], *, generated_at: datetime | None = None,
                   audit_anchor: dict | None = None) -> dict:
    """`audit_anchor` (see audit_chain.anchor) pins the head of the case's audit chain inside the signed manifest."""
    manifest = {
        "schema": SCHEMA,
        "incident_id": incident_id,
        "generated_at": _iso(generated_at or datetime.utcnow()),
        "generator": "LINEAGE",
        "entry_count": len(entries),
        "entries_digest": sha256_hex(canonical_json(entries)),
        "entries": entries,
    }
    if audit_anchor is not None:
        manifest["audit_anchor"] = audit_anchor
    return manifest


def sign_manifest(manifest: dict, key: Ed25519PrivateKey) -> dict:
    payload = canonical_json(manifest)
    sig = key.sign(payload)
    raw = public_key_bytes(key)
    return {
        "manifest": manifest,
        "manifest_sha256": sha256_hex(payload),
        "signature": {"algorithm": SIGNATURE_ALGORITHM, "key_id": key_id(raw), "public_key": _b64(raw), "value": _b64(sig)},
        "timestamp": None,
    }


def verify_envelope(envelope: dict, trusted_public_key_b64: str | None = None) -> dict:
    """Verify signature and internal digests.

    ``trusted_public_key_b64`` is the key the *verifier* trusts (published out-of-band). When omitted the envelope's
    embedded key is used and ``key_trusted`` is False: the result then proves self-consistency only.
    """
    try:
        manifest = envelope["manifest"]
        sig = envelope["signature"]
        signature = _unb64(sig["value"])
        embedded = _unb64(sig["public_key"])
    except (KeyError, TypeError) as exc:
        raise ManifestError("Malformed envelope.") from exc
    trusted = _unb64(trusted_public_key_b64) if trusted_public_key_b64 else None
    used = trusted or embedded
    payload = canonical_json(manifest)
    try:
        Ed25519PublicKey.from_public_bytes(used).verify(signature, payload)
        signature_valid = True
    except (InvalidSignature, ValueError):
        signature_valid = False
    entries = manifest.get("entries", []) if isinstance(manifest, dict) else []
    return {
        "signature_valid": signature_valid,
        "key_trusted": trusted is not None,
        "key_matches_embedded": trusted is None or trusted == embedded,
        "key_id": key_id(used),
        "manifest_sha256_matches": envelope.get("manifest_sha256") == sha256_hex(payload),
        "entries_digest_matches": isinstance(manifest, dict) and manifest.get("entries_digest") == sha256_hex(canonical_json(entries)),
    }


def diff_against_current(manifest: dict, current_entries: list[dict]) -> dict:
    """Compare a signed manifest to the case as it is now: what was added, removed or changed since signing."""
    old = {(e["kind"], e["id"]): e for e in manifest.get("entries", [])}
    new = {(e["kind"], e["id"]): e for e in current_entries}
    added = sorted(f"{k}:{i}" for (k, i) in new.keys() - old.keys())
    removed = sorted(f"{k}:{i}" for (k, i) in old.keys() - new.keys())
    changed = sorted(f"{k}:{i}" for (k, i) in old.keys() & new.keys() if old[(k, i)].get("sha256") != new[(k, i)].get("sha256"))
    return {"unchanged": not (added or removed or changed), "added": added, "removed": removed, "hash_changed": changed}


# --------------------------------------------------------------------------------------------------
# Minimal DER (just enough for RFC 3161 request/response handling)
# --------------------------------------------------------------------------------------------------

def _der_len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(body)]) + body


def _tlv(tag: int, value: bytes) -> bytes:
    return bytes([tag]) + _der_len(len(value)) + value


def _der_int(n: int) -> bytes:
    body = n.to_bytes(max(1, (n.bit_length() + 8) // 8), "big")  # leading 0x00 keeps it non-negative
    return _tlv(0x02, body)


def _der_oid(dotted: str) -> bytes:
    parts = [int(p) for p in dotted.split(".")]
    body = bytearray([parts[0] * 40 + parts[1]])
    for p in parts[2:]:
        chunk = [p & 0x7F]
        p >>= 7
        while p:
            chunk.append(0x80 | (p & 0x7F))
            p >>= 7
        body.extend(reversed(chunk))
    return _tlv(0x06, bytes(body))


def build_timestamp_request(digest: bytes, nonce: int) -> bytes:
    """DER TimeStampReq for a SHA-256 digest, nonce included, certificates requested."""
    if len(digest) != 32:
        raise ValueError("SHA-256 digest must be 32 bytes.")
    algorithm = _tlv(0x30, _der_oid(SHA256_OID) + _tlv(0x05, b""))
    imprint = _tlv(0x30, algorithm + _tlv(0x04, digest))
    return _tlv(0x30, _der_int(1) + imprint + _der_int(nonce) + _tlv(0x01, b"\xff"))


def _read(data: bytes, pos: int) -> tuple[int, int, int, int]:
    """Return (tag, value_start, value_end, next_pos) for the TLV at ``pos``. Definite lengths only."""
    if pos + 2 > len(data):
        raise TimestampError("Truncated DER.")
    tag = data[pos]
    first = data[pos + 1]
    if first == 0x80:
        raise TimestampError("Indefinite-length (BER) encoding is not supported by the in-process parser.")
    if first < 0x80:
        length, start = first, pos + 2
    else:
        n = first & 0x7F
        if n == 0 or n > 4 or pos + 2 + n > len(data):
            raise TimestampError("Invalid DER length.")
        length, start = int.from_bytes(data[pos + 2:pos + 2 + n], "big"), pos + 2 + n
    end = start + length
    if end > len(data):
        raise TimestampError("DER value overruns buffer.")
    return tag, start, end, end


def _children(data: bytes, start: int, end: int) -> list[tuple[int, int, int, int]]:
    out, pos = [], start
    while pos < end:
        tag, vs, ve, nxt = _read(data, pos)
        out.append((tag, vs, ve, pos))  # last item is the TLV's own offset so callers can re-slice the whole element
        pos = nxt
    return out


def parse_timestamp_response(reply: bytes) -> dict:
    """Parse a DER TimeStampResp. Returns the granted token and, when readable, the TSTInfo fields."""
    tag, vs, ve, _ = _read(reply, 0)
    if tag != 0x30:
        raise TimestampError("Reply is not a DER SEQUENCE.")
    top = _children(reply, vs, ve)
    if not top or top[0][0] != 0x30:
        raise TimestampError("Missing PKIStatusInfo.")
    status_children = _children(reply, top[0][1], top[0][2])
    if not status_children or status_children[0][0] != 0x02:
        raise TimestampError("Missing PKIStatus.")
    status = int.from_bytes(reply[status_children[0][1]:status_children[0][2]], "big")
    if status not in (0, 1):
        raise TimestampError(f"TSA did not grant the timestamp (PKIStatus={status}).")
    if len(top) < 2:
        raise TimestampError("Granted response carried no timeStampToken.")
    token_off = top[1][3]
    token = reply[token_off:top[1][2]]
    info: dict = {"status": status, "token_der": token, "tst_info_parsed": False}
    try:
        info.update(_parse_tst_info(token))
        info["tst_info_parsed"] = True
    except TimestampError as exc:
        info["parse_note"] = str(exc)
    return info


def _parse_tst_info(token: bytes) -> dict:
    # ContentInfo { OID, [0] SignedData }
    _, vs, ve, _ = _read(token, 0)
    ci = _children(token, vs, ve)
    if len(ci) < 2 or ci[1][0] != 0xA0:
        raise TimestampError("Unexpected ContentInfo layout.")
    sd_tag, sd_vs, sd_ve, _ = _read(token, ci[1][1])
    sd = _children(token, sd_vs, sd_ve)  # version, digestAlgorithms, encapContentInfo, ...
    if len(sd) < 3 or sd[2][0] != 0x30:
        raise TimestampError("Unexpected SignedData layout.")
    encap = _children(token, sd[2][1], sd[2][2])
    if len(encap) < 2 or encap[1][0] != 0xA0:
        raise TimestampError("TSTInfo content is absent or not definite-length.")
    otag, ovs, ove, _ = _read(token, encap[1][1])
    if otag != 0x04:
        raise TimestampError("TSTInfo is not a primitive OCTET STRING.")
    tst = token[ovs:ove]
    _, tvs, tve, _ = _read(tst, 0)
    f = _children(tst, tvs, tve)  # version, policy, messageImprint, serial, genTime, [accuracy], [ordering], [nonce], ...
    if len(f) < 5 or f[2][0] != 0x30 or f[4][0] != 0x18:
        raise TimestampError("Unexpected TSTInfo layout.")
    imprint = _children(tst, f[2][1], f[2][2])
    if len(imprint) < 2 or imprint[1][0] != 0x04:
        raise TimestampError("Unexpected MessageImprint layout.")
    nonce = None
    for tag, a, b, _off in f[5:]:
        if tag == 0x02:
            nonce = int.from_bytes(tst[a:b], "big")
            break
    return {
        "imprint_sha256": tst[imprint[1][1]:imprint[1][2]].hex(),
        "gen_time": tst[f[4][1]:f[4][2]].decode("ascii"),
        "serial": int.from_bytes(tst[f[3][1]:f[3][2]], "big"),
        "nonce": nonce,
    }


def request_timestamp(signature_value_b64: str, tsa_url: str, timeout: float = 10.0, *, post=None) -> dict:
    """Ask a TSA to timestamp SHA-256(signature). ``post`` is injectable for tests."""
    digest = hashlib.sha256(_unb64(signature_value_b64)).digest()
    nonce = secrets.randbits(63)
    req = build_timestamp_request(digest, nonce)
    if post is None:
        import requests

        def post(url, data, headers, timeout):  # type: ignore[no-redef]
            return requests.post(url, data=data, headers=headers, timeout=timeout)
    try:
        resp = post(tsa_url, req, {"Content-Type": "application/timestamp-query", "Accept": "application/timestamp-reply"}, timeout)
        if resp.status_code != 200:
            raise TimestampError(f"TSA returned HTTP {resp.status_code}.")
        reply = resp.content
    except TimestampError:
        raise
    except Exception as exc:  # noqa: BLE001 - network failures must not break manifest signing
        raise TimestampError(f"TSA request failed: {type(exc).__name__}") from exc
    parsed = parse_timestamp_response(reply)
    result = {
        "type": "RFC3161",
        "tsa_url": tsa_url,
        "requested_digest_sha256": digest.hex(),
        "covers": "SHA-256 of the Ed25519 signature value",
        "nonce_sent": nonce,
        "response_der": _b64(reply),
        "tst_info_parsed": parsed["tst_info_parsed"],
        "gen_time": parsed.get("gen_time"),
        "serial": parsed.get("serial"),
        "imprint_matches": (parsed.get("imprint_sha256") == digest.hex()) if parsed["tst_info_parsed"] else None,
        "nonce_matches": (parsed.get("nonce") == nonce) if parsed["tst_info_parsed"] else None,
        "tsa_signature_verified": False,
        "note": "Imprint, nonce and time were read from the token. The TSA's CMS signature and certificate chain were NOT "
                "validated in-process; verify with `openssl ts -verify` against the TSA's CA certificate.",
    }
    if parsed.get("parse_note"):
        result["parse_note"] = parsed["parse_note"]
    # A token that does not bind our digest or nonce must never be presented as a valid timestamp.
    if result["tst_info_parsed"] and not (result["imprint_matches"] and result["nonce_matches"] is not False):
        raise TimestampError("TSA reply does not match the request (imprint or nonce mismatch).")
    return result


def check_timestamp(envelope: dict) -> dict | None:
    """Re-check a stored timestamp against the envelope's signature. None when the manifest was never timestamped."""
    ts = envelope.get("timestamp")
    if not ts:
        return None
    digest = hashlib.sha256(_unb64(envelope["signature"]["value"])).hexdigest()
    try:
        parsed = parse_timestamp_response(_unb64(ts["response_der"]))
    except TimestampError as exc:
        return {"present": True, "parsed": False, "imprint_matches": None, "error": str(exc), "tsa_signature_verified": False}
    return {
        "present": True,
        "parsed": parsed["tst_info_parsed"],
        "imprint_matches": (parsed.get("imprint_sha256") == digest) if parsed["tst_info_parsed"] else None,
        "gen_time": parsed.get("gen_time"),
        "tsa_signature_verified": False,
    }


def attach_timestamp(envelope: dict, tsa_url: str, timeout: float = 10.0, *, post=None) -> dict:
    """Best-effort: a TSA outage records the failure on the envelope instead of blocking the signed manifest."""
    try:
        envelope["timestamp"] = request_timestamp(envelope["signature"]["value"], tsa_url, timeout, post=post)
    except TimestampError as exc:
        envelope["timestamp"] = None
        envelope["timestamp_error"] = str(exc)
    return envelope
