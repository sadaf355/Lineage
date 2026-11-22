#!/usr/bin/env python3
"""Find near-duplicate images before they inflate the test score.

    cd backend
    python eval/check_leakage.py            # report only
    python eval/check_leakage.py --apply    # also write a `group` column so near-duplicates share one split

Why: public datasets often contain the same picture more than once under different names, and the same celebrity or the same
generator prompt many times. If one copy ends up in the calibration split and another in the test split, the detector is being
tested on something it was effectively tuned on. This script hashes every ORIGINAL image (256-bit difference hash plus a colour layout), clusters
images that match on both, and (with --apply) gives each cluster one group so the split keeps it together.

A cluster that contains BOTH a real and a fake image is a labelling problem (or a dataset that pairs a face with its
manipulated version). It is reported and, because the evaluation cannot be trusted with it, makes the script exit 1.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services import eval_stats  # noqa: E402


def signature(path: Path, size: int = 16, grid: int = 4) -> tuple[int, list[float]]:
    """A 256-bit difference hash (structure) plus a 4x4 colour layout (48 numbers). Two images are called near-duplicates only if
    BOTH agree. A 64-bit hash alone confuses low-detail images (flat backgrounds, gradients, graphics), and a false 'duplicate'
    of a real and a fake image would stop the run for no reason."""
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        g = rgb.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
        px = g.load()
        bits = 0
        for y in range(size):
            for x in range(size):
                bits = (bits << 1) | (1 if px[x, y] > px[x + 1, y] else 0)
        small = rgb.resize((grid, grid), Image.Resampling.BOX)
        layout = [float(c) for pixel in small.getdata() for c in pixel]
        return bits, layout


def analyse(rows: list[dict[str, str]], images: Path, max_dist: int, max_color: float) -> dict:
    originals = [r for r in rows if r["condition"] == "original"]
    sigs: dict[str, tuple[int, list[float]]] = {}
    skipped: list[str] = []
    for r in originals:
        try:
            sigs[r["filename"]] = signature(images / r["filename"])
        except Exception:
            skipped.append(r["filename"])
    hashes = sigs
    label = {r["filename"]: r["label"].strip().lower() for r in originals}
    clusters = eval_stats.cluster(list(sigs), lambda x, y: eval_stats.hamming(sigs[x][0], sigs[y][0]) <= max_dist
                                  and eval_stats.color_layout_distance(sigs[x][1], sigs[y][1]) <= max_color)
    conflicts = [c for c in clusters if len({label[f] for f in c}) > 1]
    return {"originals": len(originals), "hashed": len(hashes), "skipped": skipped, "clusters": clusters,
            "conflicts": conflicts, "label": label}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="eval/manifest.csv")
    ap.add_argument("--images", default=None)
    ap.add_argument("--max-dist", type=int, default=24, help="max differing bits (of 256) in the structure hash")
    ap.add_argument("--max-color", type=float, default=14.0, help="max mean colour-layout difference (0-255) to call two images near-duplicates")
    ap.add_argument("--apply", action="store_true", help="write a 'group' column so near-duplicates stay in one split")
    a = ap.parse_args()
    manifest = Path(a.manifest)
    images = Path(a.images) if a.images else manifest.parent / "images"
    with manifest.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    res = analyse(rows, images, a.max_dist, a.max_color)
    n_dupe = sum(len(c) for c in res["clusters"])
    print(f"{res['hashed']} of {res['originals']} original images hashed; {len(res['clusters'])} near-duplicate cluster(s) "
          f"covering {n_dupe} images (structure hash within {a.max_dist}/256 bits and colour layout within {a.max_color:g}).")
    for fn in res["skipped"][:5]:
        print(f"  could not read: {fn}")
    for c in res["clusters"][:15]:
        labs = Counter(res["label"][f] for f in c)
        print(f"  cluster of {len(c)} ({dict(labs)}): {', '.join(sorted(c)[:4])}{' ...' if len(c) > 4 else ''}")
    if res["conflicts"]:
        print(f"\nERROR: {len(res['conflicts'])} cluster(s) mix real and fake images. Fix the labels or remove one side "
              f"before evaluating:")
        for c in res["conflicts"][:10]:
            print("  " + ", ".join(f"{f} [{res['label'][f]}]" for f in sorted(c)))
        return 1
    if a.apply:
        base = {r["filename"]: (r.get("group") or "").strip() or eval_stats.group_of(r["filename"]) for r in rows}
        groups = eval_stats.merged_groups(base, res["clusters"])
        for r in rows:
            r["group"] = groups[r["filename"]]
        fields = ["filename", "label", "source", "condition", "group"]
        with manifest.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote a 'group' column to {manifest}. Near-duplicates now share a split.")
    elif res["clusters"]:
        print("Run again with --apply so each cluster stays in a single split.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
