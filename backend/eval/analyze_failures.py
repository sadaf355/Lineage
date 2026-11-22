"""Explain where the detector fails, from the per-image scores run_eval.py saved.

    python eval/analyze_failures.py                 # reads results/predictions.csv, writes results/failure_modes.md

Everything printed is computed from your predictions: error rates by source and by condition, the largest
accuracy drop versus the untouched images, the worst individual mistakes, and whether the ensemble really
beats the single models. It states "not better" when that is what the numbers say.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import eval_harness  # noqa: E402
from app.services.phase34 import _parse_label, roc_auc  # noqa: E402


def _stats(rows: list[dict], thr: float) -> dict:
    scored = [r for r in rows if r["score"] is not None]
    tp = fp = tn = fn = 0
    for r in scored:
        actual, pred = _parse_label(r["label"]), r["score"] >= thr
        tp += actual and pred; fp += (not actual) and pred; tn += (not actual) and (not pred); fn += actual and (not pred)
    n = len(scored)
    pct = lambda a, b: None if b == 0 else round(100 * a / b, 1)  # noqa: E731
    auc = roc_auc([_parse_label(r["label"]) for r in scored], [r["score"] for r in scored]) if scored else None
    return {"n": n, "unscored": len(rows) - n, "accuracy": pct(tp + tn, n), "fpr": pct(fp, fp + tn), "fnr": pct(fn, fn + tp),
            "auc": None if auc is None else round(auc, 3), "tp": tp, "fp": fp, "tn": tn, "fn": fn}


def _fmt(v, suffix="%"):
    return "n/a" if v is None else f"{v}{suffix}"


def _t(thr, model: str) -> float:
    """thr is one number, or a {model: number} map when each model was calibrated separately."""
    return thr[model] if isinstance(thr, dict) else thr


def analyze(preds: dict[str, list[dict]], thr) -> str:
    shown = ", ".join(f"{m} {_t(thr, m):g}%" for m in preds) if isinstance(thr, dict) else f"{thr:g}%"
    out = [f"Computed from {sum(len(v) for v in preds.values())} rows at threshold {shown}.", ""]
    for model, rows in preds.items():
        t = _t(thr, model)
        total = _stats(rows, t)
        out += [f"### {model}", "",
                f"Overall: accuracy {_fmt(total['accuracy'])}, false-positive rate {_fmt(total['fpr'])} (real flagged as fake), "
                f"false-negative rate {_fmt(total['fnr'])} (fakes missed), {total['unscored']} unscored.", ""]
        by_cond: dict[str, list] = defaultdict(list); by_src: dict[str, list] = defaultdict(list)
        for r in rows:
            by_cond[r["condition"]].append(r); by_src[r["source"]].append(r)
        base = _stats(by_cond.get("original", []), t) if "original" in by_cond else None
        out += ["| Condition | n | Accuracy | False-positive | False-negative | Change vs original |", "|---|---|---|---|---|---|"]
        worst = None
        for cond, rs in sorted(by_cond.items()):
            st = _stats(rs, t)
            delta = None
            if base and cond != "original" and st["accuracy"] is not None and base["accuracy"] is not None:
                delta = round(st["accuracy"] - base["accuracy"], 1)
                if worst is None or delta < worst[1]:
                    worst = (cond, delta)
            out.append(f"| {cond} | {st['n']} | {_fmt(st['accuracy'])} | {_fmt(st['fpr'])} | {_fmt(st['fnr'])} | {'' if delta is None else f'{delta:+} pts'} |")
        out.append("")
        if worst and worst[1] < 0:
            out += [f"Largest drop: **{worst[0]}** ({worst[1]:+} points versus original images).", ""]
        elif worst:
            out += ["No condition lowered accuracy versus the original images on this set.", ""]
        out += ["| Source | n | Accuracy | False-positive | False-negative |", "|---|---|---|---|---|"]
        for src, rs in sorted(by_src.items()):
            st = _stats(rs, t)
            out.append(f"| {src} | {st['n']} | {_fmt(st['accuracy'])} | {_fmt(st['fpr'])} | {_fmt(st['fnr'])} |")
        out.append("")
        scored = [r for r in rows if r["score"] is not None and r["condition"] == "original"]
        fp_rows = sorted((r for r in scored if not _parse_label(r["label"]) and r["score"] >= t), key=lambda r: -r["score"])[:5]
        fn_rows = sorted((r for r in scored if _parse_label(r["label"]) and r["score"] < t), key=lambda r: r["score"])[:5]
        out += ["Most confident false positives (real images scored as fake): " + (", ".join(f"{r['filename']} ({r['score']})" for r in fp_rows) or "none"), "",
                "Most confident false negatives (fakes scored as real): " + (", ".join(f"{r['filename']} ({r['score']})" for r in fn_rows) or "none"), ""]
    ens = [m for m in preds if m.startswith("ensemble")]
    singles = [m for m in preds if not m.startswith("ensemble")]
    if ens and singles:
        e = _stats(preds[ens[0]], _t(thr, ens[0]))
        out += ["### Single model versus ensemble", "", "| Model | n | Accuracy | ROC-AUC |", "|---|---|---|---|"]
        best = None
        for m in singles + ens:
            st = _stats(preds[m], _t(thr, m))
            out.append(f"| {m} | {st['n']} | {_fmt(st['accuracy'])} | {_fmt(st['auc'], '')} |")
            if m in singles and st["accuracy"] is not None and (best is None or st["accuracy"] > best[1]):
                best = (m, st["accuracy"])
        out.append("")
        if best and e["accuracy"] is not None:
            diff = round(e["accuracy"] - best[1], 1)
            if diff > 0.5:
                out.append(f"The ensemble is better than the best single model ({best[0]}) by {diff} points of accuracy.")
            elif diff < -0.5:
                out.append(f"The ensemble is WORSE than the best single model ({best[0]}) by {abs(diff)} points of accuracy. Say so; do not present it as an improvement.")
            else:
                out.append(f"The ensemble is not meaningfully different from the best single model ({best[0]}): {diff:+} points. Say so.")
        by_file = defaultdict(dict)
        for m in singles + ens[:1]:
            for r in preds[m]:
                if r["score"] is not None:
                    by_file[(r["filename"])][m] = (r["score"] >= _t(thr, m)) == _parse_label(r["label"])
        both = [f for f, d in by_file.items() if len(d) == len(singles) + 1]
        helped = sum(1 for f in both if by_file[f][ens[0]] and not all(by_file[f][m] for m in singles))
        hurt = sum(1 for f in both if not by_file[f][ens[0]] and any(by_file[f][m] for m in singles))
        out += ["", f"Images where the ensemble was right but at least one single model was wrong: {helped}. "
                    f"Images where the ensemble was wrong but at least one single model was right: {hurt}.", ""]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions", default="eval/results/predictions.csv")
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--out", default="eval/results/failure_modes.md")
    a = ap.parse_args()
    if not Path(a.predictions).is_file():
        print(f"ERROR: {a.predictions} not found. Run eval/run_eval.py first.")
        return 2
    from app.core.config import get_settings
    preds = eval_harness.load_predictions(a.predictions)
    thr = a.threshold if a.threshold is not None else get_settings().DETECTOR_EVAL_THRESHOLD
    latest = eval_harness.load_latest(Path(a.predictions).with_name("latest.json"))
    if latest and latest.get("thresholds") and a.threshold is None:
        thr = latest["thresholds"]          # each model was calibrated on its own calibration split
    if any(r.get("split") for rows in preds.values() for r in rows):
        # Analyse only the held-out test split; calibration images were used to pick the threshold.
        preds = {m: [r for r in rows if r.get("split") == "test"] for m, rows in preds.items()}
        print("Using the held-out test split only.")
    md = analyze(preds, thr)
    Path(a.out).write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
