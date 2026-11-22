#!/usr/bin/env python3
"""Prove the evaluation TOOLING works, without a dataset or a model.

    cd backend && python eval/selftest.py

It builds a small SYNTHETIC set in a temporary folder (smooth 'real' images, 'fake' images with a periodic artefact), runs the
real ``build_degraded.py``, scores with a trivial stand-in detector, and checks the evaluation protocol: copies of one original
never cross splits, the threshold comes from the calibration split only, intervals bracket the point estimate, and the same
seed reproduces the same split.

THE NUMBERS PRINTED HERE ARE NOT A DETECTOR RESULT. They describe a toy detector on toy images. Nothing is written to
``eval/results`` or to the model card. Use it to find a broken pipeline *before* spending hours on a real run.
"""
from __future__ import annotations

import csv
import io
import math
import random
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageFilter

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
from app.services import eval_stats  # noqa: E402


def _synthetic(kind: str, i: int) -> Image.Image:
    rnd = random.Random(f"{kind}-{i}")
    w = h = 128
    img = Image.new("RGB", (w, h))
    px = img.load()
    a, b, c = rnd.randint(30, 200), rnd.randint(30, 200), rnd.randint(30, 200)
    for y in range(h):
        for x in range(w):
            n = rnd.randint(-6, 6)
            r, g, bl = a + x // 3 + n, b + y // 3 + n, c + (x + y) // 5 + n
            if kind == "fake" and (x % 8 == 0 or y % 8 == 0):   # periodic artefact a real photo would not have
                r, g, bl = r + 14, g + 14, bl + 14
            px[x, y] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, bl)))
    return img


def _stand_in_detector(raw: bytes) -> float:
    """Toy score 0-100: how much of the image's variation sits on an 8-pixel grid. NOT a real detector."""
    img = Image.open(io.BytesIO(raw)).convert("L").resize((128, 128))
    edges = img.filter(ImageFilter.FIND_EDGES)
    e = edges.load()
    on = off = 0
    for y in range(128):
        for x in range(128):
            if x % 8 == 0 or y % 8 == 0:
                on += e[x, y]
            else:
                off += e[x, y]
    ratio = (on / max(1, 15 * 128 * 2 - 1)) / max(1e-6, off / (128 * 128 - 15 * 128 * 2 + 1))
    return max(0.0, min(100.0, 50 + 25 * math.log(max(ratio, 1e-3))))


def run(n_per_class: int = 30, seed: str = "selftest", verbose: bool = True) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        images = root / "images"
        images.mkdir()
        rows = []
        for kind in ("real", "fake"):
            for i in range(n_per_class):
                name = f"{kind}_{i:03d}.png"
                _synthetic(kind, i).save(images / name)
                rows.append({"filename": name, "label": kind, "source": f"toy_{i % 2}", "condition": "original"})
        manifest = root / "manifest.csv"
        with manifest.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["filename", "label", "source", "condition"])
            w.writeheader()
            w.writerows(rows)
        done = subprocess.run([sys.executable, str(BACKEND / "eval" / "build_degraded.py"), "--manifest", str(manifest)],
                              capture_output=True, text=True)
        assert done.returncode == 0, f"build_degraded failed: {done.stderr or done.stdout}"
        with manifest.open(newline="", encoding="utf-8") as fh:
            full = list(csv.DictReader(fh))
        assert len(full) == len(rows) * 5, f"expected 5 rows per original, got {len(full)} for {len(rows)}"
        stat_rows = []
        for r in full:
            score = _stand_in_detector((images / r["filename"]).read_bytes())
            stat_rows.append({"group": eval_stats.group_of(r["filename"]), "y": 1 if r["label"] == "fake" else 0, "score": score,
                              "condition": r["condition"], "source": r["source"]})
        res = eval_stats.evaluate_protocol(stat_rows, 0.3, seed, None, 300)
        again = eval_stats.evaluate_protocol(stat_rows, 0.3, seed, None, 300)
        other = eval_stats.evaluate_protocol(stat_rows, 0.3, seed + "-different", None, 300)

    # --- checks
    assign = res["assignment"]
    eval_stats.assert_no_leakage(stat_rows, assign)                               # no original's copies cross splits
    assert res["protocol"]["rows"]["calib"] + res["protocol"]["rows"]["test"] == len(stat_rows)
    assert assign == again["assignment"] and res["protocol"]["threshold"] == again["protocol"]["threshold"], "same seed must reproduce"
    assert assign != other["assignment"], "a different seed should give a different split"
    calib_only = [r for r in stat_rows if assign[r["group"]] == "calib"]
    thr, _ = eval_stats.pick_threshold(calib_only)
    assert thr == res["protocol"]["threshold"], "threshold must come from the calibration split only"
    for k, v in res["ci"]["metrics"].items():
        assert v["low"] is not None and v["low"] <= v["point"] <= v["high"], f"CI does not bracket {k}: {v}"
    assert set(res["by_condition"]) == {"original", "jpeg_q50", "resize_50", "crop_80", "screenshot"}
    if verbose:
        t = res["test"]
        print("SYNTHETIC SELF-TEST. NOT A DETECTOR RESULT. Toy detector, toy images.")
        print(f"  originals: {2 * n_per_class}, rows incl. degraded copies: {len(stat_rows)}")
        print(f"  split: {res['protocol']['groups']}  threshold (from calibration only): {thr}")
        print(f"  toy test accuracy {t['accuracy']}%  95% CI {res['ci']['metrics']['accuracy']['low']} to {res['ci']['metrics']['accuracy']['high']}")
        print("  checks passed: no leakage, threshold from calibration only, reproducible split, intervals bracket estimates, 5 conditions present")
    return res


if __name__ == "__main__":
    try:
        run()
    except AssertionError as exc:
        print(f"SELF-TEST FAILED: {exc}")
        sys.exit(1)
