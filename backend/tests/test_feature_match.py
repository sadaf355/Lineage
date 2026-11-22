"""Crop-robust feature matching (ORB + RANSAC). Images are synthetic but textured, generated from a fixed seed,
so the tests are deterministic and need no fixtures on disk. Real-photo accuracy is measured by
scripts/eval_crop_matching.py, not asserted here."""
import numpy as np
import pytest
from PIL import Image, ImageFilter

from app.services import feature_match as fm


def _scene(seed: int, size=(480, 360)) -> Image.Image:
    """Cluttered synthetic 'photo': many random shapes at several scales, lightly blurred."""
    rng = np.random.default_rng(seed)
    w, h = size
    canvas = np.full((h, w, 3), 128, np.uint8)
    for _ in range(220):
        x, y = int(rng.integers(0, w - 20)), int(rng.integers(0, h - 20))
        sw, sh = int(rng.integers(6, 70)), int(rng.integers(6, 70))
        canvas[y:y + sh, x:x + sw] = rng.integers(0, 256, 3)
    return Image.fromarray(canvas).filter(ImageFilter.GaussianBlur(0.8))


def test_same_image_matches_itself():
    im = _scene(1)
    r = fm.best_match(fm.extract(im), im)
    assert r.matched and r.inliers >= fm.MIN_INLIERS and 85 <= r.score <= 100


@pytest.mark.parametrize("box", [(0, 0, 360, 270), (100, 60, 460, 330), (60, 40, 300, 240)])
def test_crop_of_reference_is_matched(box):
    im = _scene(2)
    r = fm.best_match(fm.extract(im), im.crop(box))
    assert r.matched, r


def test_resized_rotated_and_mirrored_copies_match():
    im = _scene(3)
    ref = fm.extract(im)
    assert fm.best_match(ref, im.resize((im.width // 2, im.height // 2))).matched
    assert fm.best_match(ref, im.rotate(6, expand=True, fillcolor=(128, 128, 128))).matched
    m = fm.best_match(ref, im.transpose(Image.Transpose.FLIP_LEFT_RIGHT))
    assert m.matched and m.mirrored and m.method.endswith("; mirrored")


def test_different_images_do_not_match():
    refs = [fm.extract(_scene(s)) for s in (10, 11, 12, 13)]
    wrong = sum(fm.best_match(refs[i], _scene(20 + j)).matched for i in range(4) for j in range(4))
    assert wrong == 0


def test_featureless_image_is_insufficient_not_a_verdict():
    flat = Image.new("RGB", (400, 300), (200, 200, 200))
    r = fm.best_match(fm.extract(_scene(4)), flat)
    assert r.status == "insufficient_features" and not r.matched and r.score == 0.0
    # and the reverse: a flat reference cannot be matched against anything
    assert fm.best_match(fm.extract(flat), _scene(4)).status == "insufficient_features"


def test_tiny_overlap_is_not_reported_as_a_match():
    im = _scene(5)
    r = fm.best_match(fm.extract(im), im.crop((0, 0, 70, 55)))
    assert not r.matched  # a ~2% sliver is outside what this matcher claims to detect


def test_score_is_a_confidence_band_in_the_accepted_range():
    assert fm.FeatureMatch("match", inliers=fm.MIN_INLIERS).score == 85.0
    assert fm.FeatureMatch("match", inliers=500).score == 100.0
    assert fm.FeatureMatch("no_match", inliers=500).score == 0.0
