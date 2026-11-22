#!/usr/bin/env python3
"""Measure the crop-robust matcher (backend/app/services/feature_match.py) on YOUR images.

    python scripts/eval_crop_matching.py /path/to/photos [--max 60] [--trials 3] [--json out.json]

Reports, per transformation, how often a transformed copy is matched back to its original (recall), how often the
image has too few features to judge (insufficient), and how often two DIFFERENT images are wrongly matched.
Use >=30 distinct real photos. Do not evaluate on near-duplicates, icons or screenshots of one template: their
shared structure produces matches that are real similarity, not errors, and make the false-match rate meaningless.
"""
import argparse, io, json, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from PIL import Image  # noqa: E402
from app.services import feature_match as fm  # noqa: E402


def jpeg(im, q=35):
    b = io.BytesIO(); im.save(b, "JPEG", quality=q); return Image.open(io.BytesIO(b.getvalue())).convert("RGB")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("folder"); ap.add_argument("--max", type=int, default=60)
    ap.add_argument("--trials", type=int, default=3); ap.add_argument("--json"); ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args(); rng = random.Random(a.seed)
    paths = sorted(p for p in Path(a.folder).rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    imgs = []
    for p in paths:
        try:
            im = Image.open(p).convert("RGB")
            if min(im.size) >= 160: imgs.append(im)
        except Exception: pass
        if len(imgs) >= a.max: break
    feats = [fm.extract(i) for i in imgs]
    usable = [k for k, f in enumerate(feats) if f.count >= fm.MIN_FEATURES]
    if len(usable) < 10: sys.exit(f"Need at least 10 usable images, found {len(usable)} (of {len(imgs)} read).")

    def crop(im, frac):
        w, h = im.size; cw, ch = int(w * frac), int(h * frac)
        x, y = rng.randint(0, w - cw), rng.randint(0, h - ch)
        return im.crop((x, y, x + cw, y + ch))

    tests = {f"crop {int(f * 100)}%": (lambda im, f=f: crop(im, f), a.trials) for f in (.9, .75, .6, .5, .35)}
    tests.update({"resize 50%": (lambda im: im.resize((max(1, im.width // 2), max(1, im.height // 2))), 1),
                  "rotate 8deg": (lambda im: im.rotate(8, expand=True, fillcolor="white"), 1),
                  "mirror": (lambda im: im.transpose(Image.Transpose.FLIP_LEFT_RIGHT), 1), "jpeg q35": (jpeg, 1)})
    out = {"images_read": len(imgs), "images_usable": len(usable), "thresholds": {"min_inliers": fm.MIN_INLIERS, "min_inlier_ratio": fm.MIN_INLIER_RATIO, "min_area": fm.MIN_AREA_FRACTION}, "recall": {}}
    for name, (fn, n) in tests.items():
        hit = tot = insuf = 0
        for k in usable:
            for _ in range(n):
                r = fm.best_match(feats[k], fn(imgs[k])); tot += 1; hit += r.matched; insuf += r.status == "insufficient_features"
        out["recall"][name] = {"trials": tot, "recall": round(hit / tot, 3), "insufficient_features": insuf}
    pairs = wrong = 0
    for i in range(len(usable)):
        for j in range(i + 1, len(usable)):
            pairs += 1; wrong += fm.best_match(feats[usable[i]], imgs[usable[j]]).matched
    out["false_match"] = {"different_image_pairs": pairs, "wrongly_matched": wrong, "rate": round(wrong / pairs, 4)}
    print(json.dumps(out, indent=2))
    if a.json: Path(a.json).write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
