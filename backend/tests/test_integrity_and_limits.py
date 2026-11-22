from app.services.integrity import sha256_bytes, verify_sha256
from app.services.rate_limit import InMemoryRateLimiter


def test_sha256_and_integrity_verification_use_real_bytes():
    payload = b"LINEAGE evidence payload"
    digest = sha256_bytes(payload)
    assert len(digest) == 64
    assert digest == "e1b002162d5c773e4ce8497bd5b8f1010ad2bd69c0fb86a64f50455f9688d312"
    verified, actual = verify_sha256(payload, digest)
    assert verified is True
    assert actual == digest
    tampered, actual_tampered = verify_sha256(payload + b"!", digest)
    assert tampered is False
    assert actual_tampered != digest


def test_rate_limiter_enforces_real_window_limit():
    limiter = InMemoryRateLimiter()
    assert limiter.allow("test", 2) is True
    assert limiter.allow("test", 2) is True
    assert limiter.allow("test", 2) is False


def test_delete_media_removes_database_row_before_commit():
    from unittest.mock import Mock, patch
    from app.routers import media as media_router

    db = Mock()
    incident = Mock(id="incident-1")
    media = Mock(id="media-1", storage_path="/tmp/media.enc", original_filename="evidence.jpg")
    user = Mock()

    with patch.object(media_router, "_get_media_item", return_value=media), \
         patch.object(media_router, "_get_owned_incident", return_value=incident), \
         patch.object(media_router.audit, "record"), \
         patch.object(media_router.file_storage, "delete_encrypted"):
        response = media_router.delete_media("incident-1", "media-1", db, user)

    db.delete.assert_called_once_with(media)
    db.commit.assert_called_once()
    assert response.status_code == 204


def test_crop_variant_is_available_for_trace_matching():
    from PIL import Image, ImageDraw
    from app.services.pixel_analysis import robust_hash_variants, _ensemble_similarity
    image = Image.new("RGB", (200, 200), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 170, 170), fill="black")
    draw.ellipse((70, 70, 130, 130), fill="white")
    reference = dict(robust_hash_variants(image))
    cropped = image.crop((20, 20, 180, 180))
    candidate = dict(robust_hash_variants(cropped))
    best = max(_ensemble_similarity(a, b)[0] for a in candidate.values() for b in reference.values())
    assert best >= 85
