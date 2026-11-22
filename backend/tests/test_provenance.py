import struct

from PIL import Image
from io import BytesIO

from app.services import provenance as pv
from tests import exif_builder as eb


def _jpeg_with_c2pa(extra=b""):
    body = b"jumb" + b"\x00\x00\x00\x20jumdc2pa\x00" + b"c2pa.claim c2pa.signature c2pa.actions " + extra
    payload = b"JP\x00\x00\x00\x00\x00\x01" + struct.pack(">I", len(body) + 8) + body
    seg = b"\xff\xeb" + struct.pack(">H", len(payload) + 2) + payload
    j = eb.jpeg()
    return j[:2] + seg + j[2:]


def test_no_credentials_is_neutral():
    r = pv.inspect_c2pa(eb.jpeg())
    assert r["present"] is False and "says nothing about authenticity" in r["note"]


def test_structural_detection_never_claims_valid_without_library():
    r = pv.inspect_c2pa(_jpeg_with_c2pa(b"c2pa.created c2pa.edited claim_generator\x00\x65Acme Editor 1.2"))
    assert r["present"] is True
    assert r["validation"]["status"] != "valid"
    assert "c2pa.edited" in r["actions"] and "c2pa.created" in r["actions"]
    assert any(l.startswith("c2pa.") for l in r["labels"])


def test_ai_source_type_in_xmp_is_a_claim_not_proof():
    xmp = '<x:xmpmeta Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"></x:xmpmeta>'
    m = pv.ai_markers(eb.with_xmp(eb.jpeg(), xmp))
    assert m and m[0]["type"] == "iptc_digital_source_type" and m[0]["strength"] == "claim"


def test_png_generator_parameters_detected():
    img = Image.new("RGB", (30, 30), (4, 5, 6))
    m = pv.ai_markers(eb.png_with_text(img, {"parameters": "a cat, Steps: 20, Sampler: Euler, Model: sdxl"}))
    assert any(x["type"] == "png_generator_text" for x in m)


def test_clean_image_has_no_markers():
    assert pv.ai_markers(eb.jpeg()) == []
    buf = BytesIO(); Image.new("RGB", (8, 8)).save(buf, "PNG")
    assert pv.ai_markers(buf.getvalue()) == []


def test_truncated_garbage_does_not_raise():
    assert pv.inspect_c2pa(b"\xff\xd8\xff\xeb\x00")["present"] in (True, False)


# ---- the "validator installed" path, with a stand-in for the c2pa package (the real package is not installable in CI sandboxes) ----
import json
import sys
import types


def _fake_c2pa(monkeypatch, payload=None, boom=None):
    mod = types.ModuleType("c2pa")

    class Reader:
        def __init__(self, mime, stream):
            if boom:
                raise boom
            self.mime, self.data = mime, stream.read()
        def json(self):
            return json.dumps(payload)

    mod.Reader = Reader
    monkeypatch.setitem(sys.modules, "c2pa", mod)


_OK = {"active_manifest": "m1", "manifests": {"m1": {"signature_info": {"issuer": "Acme CA", "time": "2026-10-01T00:00:00Z"}}}}


def test_validator_present_clean_manifest_is_valid(monkeypatch):
    _fake_c2pa(monkeypatch, _OK)
    r = pv.inspect_c2pa(_jpeg_with_c2pa())
    assert r["validation"]["status"] == "valid" and r["validation"]["signer"] == "Acme CA"


def test_validator_present_hash_mismatch_is_invalid(monkeypatch):
    _fake_c2pa(monkeypatch, {**_OK, "validation_status": [{"code": "assertion.dataHash.mismatch"}]})
    v = pv.inspect_c2pa(_jpeg_with_c2pa())["validation"]
    assert v["status"] == "invalid" and v["failures"] == ["assertion.dataHash.mismatch"]


def test_validator_present_untrusted_signer_is_its_own_state(monkeypatch):
    _fake_c2pa(monkeypatch, {**_OK, "validation_status": [{"code": "signingCredential.untrusted"}]})
    assert pv.inspect_c2pa(_jpeg_with_c2pa())["validation"]["status"] == "untrusted_signer"
    _fake_c2pa(monkeypatch, {**_OK, "validation_status": [{"code": "signingCredential.untrusted"}, {"code": "assertion.dataHash.mismatch"}]})
    assert pv.inspect_c2pa(_jpeg_with_c2pa())["validation"]["status"] == "invalid"       # any real failure wins


def test_validator_present_but_failing_reports_error_not_valid(monkeypatch):
    _fake_c2pa(monkeypatch, boom=ValueError("manifest truncated"))
    v = pv.inspect_c2pa(_jpeg_with_c2pa())["validation"]
    assert v["status"] == "error" and "truncated" in v["reason"]


def test_validator_is_not_called_when_no_credentials(monkeypatch):
    _fake_c2pa(monkeypatch, boom=AssertionError("must not be called"))
    assert pv.inspect_c2pa(eb.jpeg())["present"] is False


def test_validator_missing_says_not_validated(monkeypatch):
    monkeypatch.setitem(sys.modules, "c2pa", None)            # makes `import c2pa` raise ImportError
    assert pv.inspect_c2pa(_jpeg_with_c2pa())["validation"]["status"] == "not_validated"


def test_requirements_file_lists_the_validator_and_is_not_in_core():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    assert "c2pa-python" in (root / "requirements-c2pa.txt").read_text()
    assert "c2pa" not in (root / "requirements.txt").read_text().lower()
