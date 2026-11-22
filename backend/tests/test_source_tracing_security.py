import pytest
import io
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from app.services.source_tracing import _hash_score, _validate_public_url, sign_pending_match, verify_pending_match, trace_url, validate_trace_accept_payload
from app.services import pixel_analysis


def test_private_targets_are_rejected():
    for url in ("http://127.0.0.1:8000", "http://localhost:8000", "http://169.254.169.254/latest/meta-data"):
        try:
            _validate_public_url(url)
        except ValueError:
            continue
        raise AssertionError(f"SSRF target was not rejected: {url}")


def test_identical_images_require_three_agreeing_hashes():
    image = Image.new("RGB", (64, 64), "white")
    hashes = pixel_analysis.robust_hashes(image)
    score, agreeing, method = _hash_score(hashes, hashes)
    assert score == 100
    assert agreeing == 3
    assert "perceptual" in method


def test_source_tracing_uses_strict_threshold():
    src = Path("app/services/source_tracing.py").read_text()
    assert "best >= 85" in src
    assert "best_agree >= 2" in src
    assert "redirect=False" in src
    assert "_validate_public_url(image_url)" in src


def test_trace_url_fetches_images_with_redirects_disabled_and_stream_cap():
    image = Image.new("RGB", (64, 64), "white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    page = Mock()
    page.status_code = 200
    page.headers = {"content-type": "text/html"}
    page.iter_content = lambda size: [b'<html><meta property="og:image" content="https://cdn.example.test/a.png"></html>']
    page.raise_for_status = lambda: None

    img = Mock()
    img.status_code = 200
    img.headers = {"content-type": "image/png"}
    img.iter_content = lambda size: [image_bytes]
    img.raise_for_status = lambda: None

    hashes = pixel_analysis.robust_hashes(image)
    with patch("app.services.source_tracing._validate_public_url") as validate, patch("app.services.source_tracing._pinned_get", side_effect=[(page, "93.184.216.34"), (img, "93.184.216.34")]) as get:
        result = trace_url("https://example.test/page", [("media-1", image_bytes)])

    assert result.matches
    assert result.matches[0].agreeing_hashes == 3
    assert get.call_count == 2
    # Page URL + discovered image URL are both validated before the pinned fetch.
    assert validate.call_count >= 2


def test_trace_accept_payload_requires_strict_match():
    valid = {"url": "https://example.test", "platform": "example.test", "observed_at": "2026-09-30T10:00:00", "similarity_score": 91, "page_sha256": "a"*64, "page_storage_path": "encrypted/x", "agreeing_hashes": 2}
    assert validate_trace_accept_payload(valid)["similarity_score"] == 91
    try:
        validate_trace_accept_payload({**valid, "similarity_score": 80})
    except ValueError:
        pass
    else:
        raise AssertionError("Low-confidence traced source was accepted")


def _pending(**over):
    import time
    p = {"url": "https://example.com/p", "platform": "example.com", "observed_at": "2026-01-01T00:00:00",
         "similarity_score": 91.5, "method": "perceptual+difference+average", "agreeing_hashes": 3,
         "page_sha256": "ab" * 32, "page_storage_path": "/tmp/uploads/x.enc",
         "matched_image_url": "https://example.com/i.jpg", "issued_at": int(time.time())}
    p.update(over)
    return p


def test_pending_match_signature_round_trip_and_tamper_detection():
    p = _pending()
    p["signature"] = sign_pending_match(p, "case-1")
    verify_pending_match(p, "case-1")
    # JSON round trip changes 91.5 formatting rules, not the value
    verify_pending_match(dict(p, similarity_score=91.50), "case-1")
    for field, value in (("similarity_score", 99), ("url", "https://evil.example"), ("page_sha256", "cd" * 32)):
        try:
            verify_pending_match(dict(p, **{field: value}), "case-1")
        except ValueError:
            continue
        raise AssertionError(f"tampered {field} was accepted")
    try:
        verify_pending_match(p, "case-2")
    except ValueError:
        return
    raise AssertionError("signature was accepted for a different case")


def test_pinned_fetch_connects_to_validated_ip_and_preserves_tls_hostname():
    class Raw:
        status = 200
        reason = "OK"
        headers = {}
        def stream(self, _size):
            yield b"ok"
        def close(self):
            pass

    fake_pool = Mock()
    fake_pool.urlopen.return_value = Raw()
    with patch("app.services.source_tracing._validate_public_url"), patch("app.services.source_tracing._resolve_public_ip", return_value="93.184.216.34"), patch("app.services.source_tracing.urllib3.HTTPSConnectionPool", return_value=fake_pool) as pool:
        response, ip = __import__("app.services.source_tracing", fromlist=["_pinned_get"])._pinned_get("https://example.test/page")
    assert ip == "93.184.216.34"
    pool.assert_called_once_with("93.184.216.34", port=443, cert_reqs="CERT_REQUIRED", ca_certs=__import__("certifi").where(), assert_hostname="example.test", server_hostname="example.test", maxsize=1, block=True)
    assert response.status_code == 200


def test_feature_match_acceptance_is_separate_and_hash_rule_is_unchanged():
    from app.services.source_tracing import FEATURE_METHOD_PREFIX, validate_trace_accept_payload
    base = {"url": "https://example.test", "platform": "example.test", "observed_at": "2026-09-30T10:00:00",
            "similarity_score": 91.5, "page_sha256": "a" * 64, "page_storage_path": "/tmp/x.enc"}
    # A hash-style method with fewer than two agreeing hashes is still rejected.
    with pytest.raises(ValueError):
        validate_trace_accept_payload({**base, "method": "perceptual+difference+average", "agreeing_hashes": 1})
    with pytest.raises(ValueError):
        validate_trace_accept_payload({**base, "method": "none", "agreeing_hashes": 0})
    # A geometrically verified feature match carries no hash agreement and is accepted via its own method label.
    ok = {**base, "method": FEATURE_METHOD_PREFIX + " inliers=88", "agreeing_hashes": 0}
    assert validate_trace_accept_payload(ok) is ok
    # The score floor still applies to it.
    with pytest.raises(ValueError):
        validate_trace_accept_payload({**ok, "similarity_score": 70})
