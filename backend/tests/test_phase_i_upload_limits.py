from types import SimpleNamespace
import pytest
from app.services.upload_limits import validate_image_limits, validate_video_limits

def test_image_decompression_ratio_is_refused():
    cfg=SimpleNamespace(MAX_IMAGE_PIXELS=10000000, MAX_DECOMPRESSION_RATIO=10, DECOMPRESSION_RATIO_MIN_PIXELS=0)
    with pytest.raises(ValueError, match="decompression ratio"):
        validate_image_limits(1000,1000,1000,cfg)
def test_image_pixel_limit_is_refused():
    cfg=SimpleNamespace(MAX_IMAGE_PIXELS=100, MAX_DECOMPRESSION_RATIO=999999, DECOMPRESSION_RATIO_MIN_PIXELS=0)
    with pytest.raises(ValueError, match="pixel limit"):
        validate_image_limits(20,20,1000,cfg)
def test_video_frame_and_duration_limits_are_configured():
    # Probe is isolated behind this helper; a missing/invalid probe fails closed.
    cfg=SimpleNamespace(MAX_VIDEO_FRAMES=1, MAX_VIDEO_DURATION_SECONDS=1, UPLOAD_PROBE_TIMEOUT_SECONDS=1)
    with pytest.raises(ValueError, match="could not be safely probed"):
        validate_video_limits("/definitely/not/a/video", 1, cfg)

def test_flat_screenshot_is_not_refused_by_the_ratio_rule():
    cfg=SimpleNamespace(MAX_IMAGE_PIXELS=100_000_000, MAX_DECOMPRESSION_RATIO=250, DECOMPRESSION_RATIO_MIN_PIXELS=20_000_000)
    validate_image_limits(1920,1080,8_000,cfg)  # 2 MP, ratio 259: a normal flat screenshot
def test_huge_image_with_tiny_file_is_still_refused():
    cfg=SimpleNamespace(MAX_IMAGE_PIXELS=100_000_000, MAX_DECOMPRESSION_RATIO=250, DECOMPRESSION_RATIO_MIN_PIXELS=20_000_000)
    with pytest.raises(ValueError, match="decompression ratio"):
        validate_image_limits(8000,8000,50_000,cfg)  # 64 MP from 50 KB

def test_unreadable_video_raises_video_probe_unavailable():
    from app.services.upload_limits import VideoProbeUnavailable
    cfg = SimpleNamespace(MAX_VIDEO_FRAMES=1000, MAX_VIDEO_DURATION_SECONDS=60, UPLOAD_PROBE_TIMEOUT_SECONDS=5)
    with pytest.raises(VideoProbeUnavailable):
        validate_video_limits("/definitely/not/a/video", 10, cfg)

def test_limit_violations_use_the_dedicated_refusal_type_not_a_bare_valueerror():
    from app.services.upload_limits import UploadLimitExceeded
    cfg = SimpleNamespace(MAX_IMAGE_PIXELS=100, MAX_DECOMPRESSION_RATIO=0, DECOMPRESSION_RATIO_MIN_PIXELS=0)
    with pytest.raises(UploadLimitExceeded):
        validate_image_limits(1000, 1000, 10, cfg)
    assert not issubclass(ValueError, UploadLimitExceeded)
