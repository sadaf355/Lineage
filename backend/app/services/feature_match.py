"""Crop-robust image matching using local features (ORB) + geometric verification (RANSAC homography).

Why this exists: whole-image perceptual hashes describe the composition of the frame, so any substantial crop
changes them completely. Local features survive cropping, scaling and mild rotation, and RANSAC checks that
the matched points are geometrically consistent with ONE transformation — which is what separates a real
crop from a coincidence of similar-looking patches.

It is a verification step for candidates, not a search engine: cost is O(reference features x candidate features)
per pair, so callers must keep candidate counts bounded (source tracing already caps images per page).

Honest limits (also reported by scripts/eval_crop_matching.py):
* Needs texture. Flat graphics, near-uniform images and tiny crops yield few features and are reported as
  "insufficient_features", never as a match or a non-match.
* Repeated patterns (tiles, text) can produce consistent-looking but wrong geometry; the inlier floor and the
  inlier-ratio floor are there to limit this, not to eliminate it.
* A match means "this candidate contains a region of the reference" (or vice versa), not "same source" or "same
  person". Investigator confirmation is still required, as for every trace.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

MAX_SIDE = 640            # downscale before detection; bounds CPU and makes results resolution-independent
N_FEATURES = 800
MIN_FEATURES = 60         # below this on either side: insufficient evidence either way
RATIO = 0.75              # Lowe ratio test
MIN_INLIERS = 30
MIN_INLIER_RATIO = 0.35
MIN_AREA_FRACTION = 0.08  # the matched region must cover a meaningful part of the smaller image


@dataclass
class FeatureSet:
    keypoints: list
    descriptors: np.ndarray | None
    size: tuple[int, int]  # (w, h) after downscale

    @property
    def count(self) -> int:
        return 0 if self.descriptors is None else len(self.descriptors)


@dataclass
class FeatureMatch:
    status: str            # "match" | "no_match" | "insufficient_features"
    inliers: int = 0
    good_matches: int = 0
    inlier_ratio: float = 0.0
    area_fraction: float = 0.0
    mirrored: bool = False

    @property
    def matched(self) -> bool:
        return self.status == "match"

    @property
    def score(self) -> float:
        """85-100 when matched, else 0. This is a confidence band derived from the inlier count (30 -> 85, >=150 -> 100).
        It is NOT a percentage of pixels or hash bits and is NOT comparable to hash-based similarity; the
        method string ("orb+ransac; inliers=...") is what identifies how a match was found."""
        if not self.matched:
            return 0.0
        return round(85.0 + 15.0 * min(1.0, (self.inliers - MIN_INLIERS) / (150 - MIN_INLIERS)), 2)

    @property
    def method(self) -> str:
        return f"orb+ransac; inliers={self.inliers}; inlier_ratio={self.inlier_ratio}; region={self.area_fraction}" + ("; mirrored" if self.mirrored else "")


def extract(img: Image.Image) -> FeatureSet:
    gray = np.asarray(img.convert("L"))
    h, w = gray.shape
    scale = min(1.0, MAX_SIDE / max(h, w))
    if scale < 1.0:
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)  # stabilises contrast across recompressions
    orb = cv2.ORB_create(nfeatures=N_FEATURES, fastThreshold=10)
    kps, desc = orb.detectAndCompute(gray, None)
    return FeatureSet(list(kps or []), desc, (gray.shape[1], gray.shape[0]))


def _area_fraction(pts: np.ndarray, size: tuple[int, int]) -> float:
    if len(pts) < 3:
        return 0.0
    hull = cv2.convexHull(pts.astype(np.float32))
    return float(cv2.contourArea(hull)) / float(size[0] * size[1])


def match(ref: FeatureSet, cand: FeatureSet) -> FeatureMatch:
    if ref.count < MIN_FEATURES or cand.count < MIN_FEATURES:
        return FeatureMatch("insufficient_features")
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = bf.knnMatch(ref.descriptors, cand.descriptors, k=2)
    good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < RATIO * p[1].distance]
    if len(good) < MIN_INLIERS:
        return FeatureMatch("no_match", good_matches=len(good))
    src = np.float32([ref.keypoints[m.queryIdx].pt for m in good])
    dst = np.float32([cand.keypoints[m.trainIdx].pt for m in good])
    # Partial affine (scale + rotation + translation) is the right model for crops/resizes and is much harder to
    # satisfy by accident than a full homography.
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=4.0)
    if M is None or inl is None:
        return FeatureMatch("no_match", good_matches=len(good))
    mask = inl.ravel().astype(bool)
    n_in = int(mask.sum())
    ratio = n_in / len(good)
    # The matched region must be substantial in the smaller image's own frame
    area_ref = _area_fraction(src[mask], ref.size)
    area_cand = _area_fraction(dst[mask], cand.size)
    area = max(area_ref, area_cand)
    ok = n_in >= MIN_INLIERS and ratio >= MIN_INLIER_RATIO and area >= MIN_AREA_FRACTION
    return FeatureMatch("match" if ok else "no_match", n_in, len(good), round(ratio, 3), round(area, 3))


def best_match(ref: FeatureSet, candidate: Image.Image) -> FeatureMatch:
    """Match a candidate against a reference, also trying a horizontal mirror (ORB is not flip-invariant)."""
    direct = match(ref, extract(candidate))
    if direct.matched or direct.status == "insufficient_features":
        return direct
    flipped = match(ref, extract(candidate.transpose(Image.Transpose.FLIP_LEFT_RIGHT)))
    if flipped.matched:
        flipped.mirrored = True
        return flipped
    return direct
