"""Phase E — signed manifest + RFC 3161 handling. Pure-function tests: no app, DB or network required.

The fake TSA below builds a structurally valid TimeStampResp (ContentInfo > SignedData > TSTInfo) so the parser is
exercised on real DER. Its CMS signature is deliberately empty — which is exactly why the module reports
``tsa_signature_verified: False`` instead of claiming validation it did not perform."""
import base64
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services import manifest as m


# ---------------------------------------------------------------- helpers
def _rows():
    media = [SimpleNamespace(id="m1", original_filename="a.png", sha256="aa" * 32, file_size_bytes=10, uploaded_at=datetime(2026, 1, 1, 10, 0, 0))]
    evidence = [
        SimpleNamespace(id="e2", item_type="screenshot", sha256="bb" * 32, source_id="s1", captured_at=datetime(2026, 1, 2)),
        SimpleNamespace(id="e1", item_type="note", sha256=None, source_id=None, captured_at=datetime(2026, 1, 3)),
    ]
    sources = [SimpleNamespace(id="s1", platform="Web", url="https://x.test/p", page_sha256="cc" * 32, observed_at=datetime(2026, 1, 2))]
    return media, evidence, sources


def _signed(key=None):
    key = key or m.parse_private_key(m.generate_seed_b64())
    entries = m.build_entries(*_rows())
    return key, m.sign_manifest(m.build_manifest("inc-1", entries, generated_at=datetime(2026, 2, 1)), key)


def _fake_tsa_reply(digest: bytes, nonce: int, *, status=0, gen_time=b"20260201120000Z", wrong_digest=False) -> bytes:
    tlv, i = m._tlv, m._der_int
    if wrong_digest:
        digest = bytes(32)
    algo = tlv(0x30, m._der_oid(m.SHA256_OID) + tlv(0x05, b""))
    tst = tlv(0x30, i(1) + m._der_oid("1.2.3.4") + tlv(0x30, algo + tlv(0x04, digest)) + i(987654321) + tlv(0x18, gen_time) + i(nonce))
    encap = tlv(0x30, m._der_oid("1.2.840.113549.1.9.16.1.4") + tlv(0xA0, tlv(0x04, tst)))
    signed = tlv(0x30, i(3) + tlv(0x31, algo) + encap + tlv(0x31, b""))
    token = tlv(0x30, m._der_oid("1.2.840.113549.1.7.2") + tlv(0xA0, signed))
    pki = tlv(0x30, i(status))
    return tlv(0x30, pki + (token if status in (0, 1) else b""))


def _post_factory(**kw):
    def post(url, data, headers, timeout):
        # decode our own request: digest and nonce sit in the DER we built
        assert headers["Content-Type"] == "application/timestamp-query"
        digest = data[data.index(b"\x04\x20") + 2:data.index(b"\x04\x20") + 34]
        top_children = m._children(data, *m._read(data, 0)[1:3])
        nonce = int.from_bytes(data[top_children[2][1]:top_children[2][2]], "big")
        body = _fake_tsa_reply(digest, nonce, **kw)
        return SimpleNamespace(status_code=200, content=body)
    return post


# ---------------------------------------------------------------- signing
def test_canonical_json_is_order_independent():
    assert m.canonical_json({"b": 1, "a": [2, 1]}) == m.canonical_json({"a": [2, 1], "b": 1})


def test_entries_are_sorted_and_record_missing_hashes_honestly():
    entries = m.build_entries(*_rows())
    assert [(e["kind"], e["id"]) for e in entries] == [("evidence", "e1"), ("evidence", "e2"), ("media", "m1"), ("source", "s1")]
    assert entries[0]["sha256"] is None  # a note with no file is recorded as such, not given a made-up hash


def test_sign_and_verify_roundtrip():
    key, env = _signed()
    r = m.verify_envelope(env)
    assert r["signature_valid"] and r["manifest_sha256_matches"] and r["entries_digest_matches"]
    assert r["key_trusted"] is False  # embedded key only proves self-consistency


def test_verify_with_trusted_key():
    key, env = _signed()
    good = base64.b64encode(m.public_key_bytes(key)).decode()
    assert m.verify_envelope(env, good)["key_trusted"] is True
    other = base64.b64encode(m.public_key_bytes(m.parse_private_key(m.generate_seed_b64()))).decode()
    r = m.verify_envelope(env, other)
    assert r["signature_valid"] is False and r["key_matches_embedded"] is False


def test_any_tamper_breaks_the_signature():
    _, env = _signed()
    env["manifest"]["entries"][0]["sha256"] = "dd" * 32
    r = m.verify_envelope(env)
    assert r["signature_valid"] is False and r["entries_digest_matches"] is False


def test_attacker_cannot_swap_in_their_own_key_unnoticed():
    key, env = _signed()
    attacker = m.parse_private_key(m.generate_seed_b64())
    forged = m.sign_manifest(env["manifest"], attacker)
    trusted = base64.b64encode(m.public_key_bytes(key)).decode()
    assert m.verify_envelope(forged)["signature_valid"] is True           # self-consistent...
    assert m.verify_envelope(forged, trusted)["signature_valid"] is False  # ...but not under the real key


def test_malformed_envelope_raises():
    with pytest.raises(m.ManifestError):
        m.verify_envelope({"manifest": {}})


def test_key_parsing_pem_and_base64():
    from cryptography.hazmat.primitives import serialization
    key = m.parse_private_key(m.generate_seed_b64())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    assert m.public_key_bytes(m.parse_private_key(pem)) == m.public_key_bytes(key)
    with pytest.raises(m.ManifestError):
        m.parse_private_key(base64.b64encode(b"short").decode())


def test_diff_detects_add_remove_change():
    _, env = _signed()
    current = m.build_entries(*_rows())
    assert m.diff_against_current(env["manifest"], current)["unchanged"] is True
    current = [e for e in current if e["id"] != "m1"]
    current[0] = {**current[0], "sha256": "ee" * 32}
    current.append({"kind": "evidence", "id": "e9", "sha256": None})
    d = m.diff_against_current(env["manifest"], current)
    assert d["removed"] == ["media:m1"] and d["added"] == ["evidence:e9"] and d["hash_changed"] and not d["unchanged"]


# ---------------------------------------------------------------- RFC 3161
def test_request_is_well_formed_der():
    req = m.build_timestamp_request(bytes(range(32)), 12345)
    tag, vs, ve, nxt = m._read(req, 0)
    assert tag == 0x30 and nxt == len(req)
    kids = m._children(req, vs, ve)
    assert [k[0] for k in kids] == [0x02, 0x30, 0x02, 0x01]  # version, imprint, nonce, certReq
    assert req[kids[0][1]:kids[0][2]] == b"\x01"
    assert bytes(range(32)) in req


def test_oid_encoding_matches_known_sha256_bytes():
    assert m._der_oid(m.SHA256_OID) == bytes.fromhex("0609608648016503040201")


def test_timestamp_roundtrip_with_fake_tsa():
    _, env = _signed()
    m.attach_timestamp(env, "https://tsa.invalid", post=_post_factory())
    ts = env["timestamp"]
    assert ts["imprint_matches"] is True and ts["nonce_matches"] is True
    assert ts["gen_time"] == "20260201120000Z" and ts["serial"] == 987654321
    assert ts["tsa_signature_verified"] is False  # never overstated
    assert "openssl ts -verify" in ts["note"]
    assert m.check_timestamp(env)["imprint_matches"] is True


def test_timestamp_detects_signature_swap_after_the_fact():
    _, env = _signed()
    m.attach_timestamp(env, "https://tsa.invalid", post=_post_factory())
    other_key, other = _signed(m.parse_private_key(m.generate_seed_b64()))
    env["signature"] = other["signature"]  # token no longer covers this signature
    assert m.check_timestamp(env)["imprint_matches"] is False


def test_mismatched_imprint_is_rejected_not_stored():
    _, env = _signed()
    m.attach_timestamp(env, "https://tsa.invalid", post=_post_factory(wrong_digest=True))
    assert env["timestamp"] is None and "mismatch" in env["timestamp_error"]
    assert m.verify_envelope(env)["signature_valid"] is True  # the signed manifest itself is unaffected


def test_refused_status_and_http_failure_do_not_break_signing():
    _, env = _signed()
    m.attach_timestamp(env, "https://tsa.invalid", post=_post_factory(status=2))
    assert env["timestamp"] is None and "PKIStatus=2" in env["timestamp_error"]
    _, env2 = _signed()
    m.attach_timestamp(env2, "https://tsa.invalid", post=lambda *a, **k: SimpleNamespace(status_code=503, content=b""))
    assert "HTTP 503" in env2["timestamp_error"]
    def boom(*a, **k): raise ConnectionError("down")
    _, env3 = _signed()
    m.attach_timestamp(env3, "https://tsa.invalid", post=boom)
    assert "ConnectionError" in env3["timestamp_error"]


def test_unparseable_token_is_kept_but_marked_unverified():
    reply = m._tlv(0x30, m._tlv(0x30, m._der_int(0)) + m._tlv(0x30, m._der_oid("1.2.840.113549.1.7.2") + m._tlv(0xA0, m._tlv(0x30, b""))))
    parsed = m.parse_timestamp_response(reply)
    assert parsed["tst_info_parsed"] is False and "parse_note" in parsed


def test_audit_anchor_is_inside_the_signed_payload():
    key = m.parse_private_key(m.generate_seed_b64())
    anchor = {"chain_ok": True, "head_seq": 7, "head_hash": "ab" * 32, "events_chained": 7, "legacy_unchained": 0}
    env = m.sign_manifest(m.build_manifest("inc-1", m.build_entries(*_rows()), generated_at=datetime(2026, 2, 1), audit_anchor=anchor), key)
    assert env["manifest"]["audit_anchor"]["head_hash"] == "ab" * 32
    assert m.verify_envelope(env)["signature_valid"] is True
    env["manifest"]["audit_anchor"]["head_hash"] = "cd" * 32          # swap in a different head after signing
    assert m.verify_envelope(env)["signature_valid"] is False


def test_manifest_without_anchor_is_unchanged_in_shape():
    _, env = _signed()
    assert "audit_anchor" not in env["manifest"]
