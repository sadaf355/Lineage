#!/usr/bin/env python3
"""Verify a LINEAGE signed manifest offline. Needs only `pip install cryptography` — no LINEAGE code, no network.

    python scripts/verify_manifest.py envelope.json --public-key <base64 key published by the operator>

Without --public-key the envelope's own key is used, which proves self-consistency ONLY (a forger can embed their own key).
Exit code: 0 = signature valid under the key you supplied, 1 = invalid, 2 = usage/format error.
"""
import argparse, base64, hashlib, json, sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def canonical(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("envelope"); ap.add_argument("--public-key", help="base64 raw Ed25519 public key from the operator")
    a = ap.parse_args()
    try:
        env = json.load(open(a.envelope, encoding="utf-8"))
        manifest, sig = env["manifest"], env["signature"]
        value = base64.b64decode(sig["value"], validate=True)
        embedded = base64.b64decode(sig["public_key"], validate=True)
        trusted = base64.b64decode(a.public_key, validate=True) if a.public_key else None
    except Exception as exc:
        print(f"Cannot read envelope: {exc}", file=sys.stderr); return 2
    payload = canonical(manifest)
    try:
        Ed25519PublicKey.from_public_bytes(trusted or embedded).verify(value, payload); ok = True
    except (InvalidSignature, ValueError):
        ok = False
    digest_ok = hashlib.sha256(canonical(manifest.get("entries", []))).hexdigest() == manifest.get("entries_digest")
    print(f"signature valid:        {ok}")
    print(f"key trusted by you:     {trusted is not None}" + ("" if trusted else "   <-- no --public-key given: self-consistency only"))
    print(f"entries digest matches: {digest_ok}")
    print(f"entries:                {manifest.get('entry_count')}  incident {manifest.get('incident_id')}  generated {manifest.get('generated_at')}")
    if env.get("timestamp"):
        print(f"RFC 3161 token present (gen_time {env['timestamp'].get('gen_time')}); validate its CMS signature with openssl, see docs/EVIDENCE_INTEGRITY.md")
    return 0 if ok and digest_ok else 1


if __name__ == "__main__":
    sys.exit(main())
