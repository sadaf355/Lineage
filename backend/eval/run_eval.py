"""Evaluate the configured detector(s) on the labelled set.

    cd backend
    python eval/run_eval.py                              # primary model only
    python eval/run_eval.py --models primary second ensemble
    python eval/run_eval.py --check-only                 # validate the manifest, run no models

Outputs eval/results/latest.json (the in-app Detector panel reads this), eval/results/latest.md
(paste into the deck / docs/DETECTOR_MODEL_CARD.md) and eval/results/predictions.csv (per-image scores, used by
analyze_failures.py).
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import eval_harness  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="eval/manifest.csv")
    ap.add_argument("--images", default=None)
    ap.add_argument("--models", nargs="+", default=["primary"], choices=["primary", "second", "ensemble"])
    ap.add_argument("--protocol", choices=["split", "fixed"], default="split",
                    help="split (default): choose the threshold on a calibration split, report on the held-out test split. "
                         "fixed: score every image at one threshold (no held-out data; use only for a quick look).")
    ap.add_argument("--threshold", type=float, default=None, help="percent; with --protocol fixed the default is DETECTOR_EVAL_THRESHOLD; "
                    "with split it overrides calibration")
    ap.add_argument("--calib-fraction", type=float, default=0.3, help="share of ORIGINAL images held for threshold calibration")
    ap.add_argument("--seed", default="lineage-eval", help="split seed (same seed, same split)")
    ap.add_argument("--bootstrap", type=int, default=1000, help="bootstrap resamples for confidence intervals")
    ap.add_argument("--out", default="eval/results/latest.json")
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()

    manifest = Path(args.manifest)
    images = Path(args.images) if args.images else manifest.parent / "images"
    try:
        rows = eval_harness.load_manifest(manifest, images)
    except eval_harness.ManifestError as exc:
        print(f"ERROR: {exc}")
        return 2

    labels = Counter(r["label"].strip().lower() for r in rows)
    conds = Counter(r["condition"] for r in rows)
    print(f"Manifest OK: {len(rows)} rows. Labels: {dict(labels)}. Conditions: {dict(conds)}.")
    n_originals = len({eval_harness.eval_stats.group_of(r["filename"]) for r in rows})
    print(f"{n_originals} original images (copies of one original always stay in the same split).")
    if n_originals < 300:
        print("NOTE: fewer than 300 ORIGINAL images. Treat the metrics as a smoke test, not a result. Degraded copies do not count as new images.")
    if args.check_only:
        return 0

    try:
        scorers = eval_harness.build_scorers(args.models)
    except eval_harness.ManifestError as exc:
        print(f"ERROR: {exc}")
        return 2
    predictions = eval_harness.score_manifest(
        rows, images, scorers, progress=lambda i, n: print(f"\rscoring {i}/{n}", end="", flush=True))
    print()
    if args.protocol == "split":
        try:
            report = eval_harness.summarize_protocol(predictions, args.calib_fraction, args.seed, args.threshold, args.bootstrap)
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 2
    else:
        report = eval_harness.summarize(predictions, args.threshold)
    out = Path(args.out)
    split = report.pop("split", None)   # per-original assignment goes to predictions.csv, not the app-facing report
    eval_harness.save_report(report, out)
    eval_harness.save_predictions(predictions, out.with_name("predictions.csv"), split)
    md = eval_harness.to_markdown(report)
    out.with_suffix(".md").write_text(md, encoding="utf-8")
    print(md)
    print(f"\nWrote {out} and {out.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
