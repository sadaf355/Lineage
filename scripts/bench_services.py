#!/usr/bin/env python3
"""Micro-benchmarks of CPU-bound LINEAGE services (no database, no network). NOT an API load test.

    python scripts/bench_services.py [--json out.json]

Measures: manifest build+sign+verify at several case sizes, and the crop-robust feature matcher (extract + match).
"""
import argparse, json, os, platform, statistics, sys, time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import numpy as np  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402
from app.services import manifest as mf, feature_match as fm  # noqa: E402


def timeit(fn, n):
    xs = []
    for _ in range(n):
        t = time.perf_counter(); fn(); xs.append(time.perf_counter() - t)
    xs.sort(); return {"runs": n, "median_ms": round(statistics.median(xs) * 1000, 2), "p95_ms": round(xs[min(n - 1, int(.95 * (n - 1) + .5))] * 1000, 2)}


def scene(seed, size=(1280, 960)):
    rng = np.random.default_rng(seed); w, h = size; c = np.full((h, w, 3), 128, np.uint8)
    for _ in range(600):
        x, y = int(rng.integers(0, w - 30)), int(rng.integers(0, h - 30)); c[y:y + int(rng.integers(8, 120)), x:x + int(rng.integers(8, 120))] = rng.integers(0, 256, 3)
    return Image.fromarray(c).filter(ImageFilter.GaussianBlur(1.0))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--json"); a = ap.parse_args()
    out = {"machine": {"python": platform.python_version(), "platform": platform.platform(), "cpus": os.cpu_count(), "processor": platform.processor() or "n/a"}, "manifest": {}, "feature_match": {}}
    key = mf.parse_private_key(mf.generate_seed_b64())
    for n in (100, 1000, 10000):
        media = [SimpleNamespace(id=f"m{i}", original_filename=f"f{i}.png", sha256="ab" * 32, file_size_bytes=1000, uploaded_at=datetime(2026, 1, 1)) for i in range(n)]
        entries = mf.build_entries(media, [], [])
        def sign(): return mf.sign_manifest(mf.build_manifest("inc", entries), key)
        env = sign()
        out["manifest"][f"{n}_entries"] = {"build_and_sign": timeit(sign, 5 if n < 10000 else 3), "verify": timeit(lambda: mf.verify_envelope(env), 5 if n < 10000 else 3), "envelope_kb": round(len(mf.canonical_json(env)) / 1024, 1)}
    a_img, b_img = scene(1), scene(2)
    out["feature_match"]["image_px"] = "1280x960 (downscaled to 640 max side before detection)"
    out["feature_match"]["extract"] = timeit(lambda: fm.extract(a_img), 10)
    ref, cand = fm.extract(a_img), fm.extract(a_img.crop((200, 150, 900, 700)))
    out["feature_match"]["match_cropped_copy"] = timeit(lambda: fm.match(ref, cand), 20)
    other = fm.extract(b_img)
    out["feature_match"]["match_unrelated"] = timeit(lambda: fm.match(ref, other), 20)
    out["feature_match"]["best_match_unrelated_incl_mirror_extract"] = timeit(lambda: fm.best_match(ref, b_img), 5)
    print(json.dumps(out, indent=2))
    if a.json: Path(a.json).write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
