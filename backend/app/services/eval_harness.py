"""Detector evaluation harness: manifest in, honest per-model, per-condition metrics out.

Nothing here invents numbers. An image a model cannot score is counted as `unscored`
and excluded from that model's metrics, so a broken model shows up as a low scored
count instead of a flattering accuracy.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.core.config import get_settings
from app.services import eval_stats, phase34

settings = get_settings()

REQUIRED_COLUMNS = ("filename", "label", "source", "condition")
Scorer = Callable[[bytes], "float | None"]


class ManifestError(ValueError):
    pass


def load_manifest(path: Path, images_dir: Path | None = None) -> list[dict[str, str]]:
    """Read manifest.csv and validate it: required columns, binary labels, files exist."""
    path = Path(path)
    images_dir = Path(images_dir) if images_dir else path.parent / "images"
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ManifestError(f"Manifest is missing columns: {', '.join(missing)}")
        rows = list(reader)
    if not rows:
        raise ManifestError("Manifest has no rows.")
    problems: list[str] = []
    for i, row in enumerate(rows, start=2):  # line 1 is the header
        for col in REQUIRED_COLUMNS:
            if not (row.get(col) or "").strip():
                problems.append(f"line {i}: empty '{col}'")
        try:
            phase34._parse_label(row.get("label"))
        except ValueError as exc:
            problems.append(f"line {i}: {exc}")
        fn = (row.get("filename") or "").strip()
        if fn and not (images_dir / fn).is_file():
            problems.append(f"line {i}: file not found: {images_dir / fn}")
    if problems:
        shown = "; ".join(problems[:10]) + (f" (+{len(problems) - 10} more)" if len(problems) > 10 else "")
        raise ManifestError(f"Invalid manifest: {shown}")
    return rows


def build_scorers(include: list[str]) -> dict[str, Scorer]:
    """Scorers keyed by display name. 'primary' and 'second' use the configured model ids."""
    scorers: dict[str, Scorer] = {}
    primary, second = settings.DETECTOR_MODEL_ID, settings.DETECTOR_SECOND_MODEL_ID
    if "primary" in include:
        scorers[primary] = lambda raw, m=primary: phase34.score_with_model(m, raw)
    if "second" in include:
        if not second:
            raise ManifestError("DETECTOR_SECOND_MODEL_ID is not set, so there is no second model to evaluate.")
        scorers[second] = lambda raw, m=second: phase34.score_with_model(m, raw)
    if "ensemble" in include:
        if not second:
            raise ManifestError("The ensemble needs DETECTOR_SECOND_MODEL_ID.")
        def _ens(raw: bytes, a=primary, b=second):
            sa, sb = phase34.score_with_model(a, raw), phase34.score_with_model(b, raw)
            vals = [v for v in (sa, sb) if v is not None]
            # Mirrors the app: the ensemble is the mean of the models that produced a score.
            return round(sum(vals) / len(vals), 2) if vals else None
        scorers[f"ensemble ({primary} + {second})"] = _ens
    return scorers


def score_manifest(rows: list[dict[str, str]], images_dir: Path, scorers: dict[str, Scorer],
                   progress: Callable[[int, int], None] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Run every scorer over every image. Returns per-model prediction rows (score may be None)."""
    out: dict[str, list[dict[str, Any]]] = {name: [] for name in scorers}
    for idx, row in enumerate(rows, start=1):
        raw = (Path(images_dir) / row["filename"].strip()).read_bytes()
        for name, scorer in scorers.items():
            try:
                score = scorer(raw)
            except Exception:
                score = None
            out[name].append({"filename": row["filename"], "label": row["label"], "source": row["source"],
                              "condition": row["condition"], "score": score, "group": (row.get("group") or "").strip()})
        if progress:
            progress(idx, len(rows))
    return out


def summarize(predictions: dict[str, list[dict[str, Any]]], threshold: float | None = None) -> dict[str, Any]:
    thr = settings.DETECTOR_EVAL_THRESHOLD if threshold is None else threshold
    models: dict[str, Any] = {}
    for name, rows in predictions.items():
        scored = [{**r, "threshold": thr} for r in rows if r["score"] is not None]
        unscored = len(rows) - len(scored)
        entry: dict[str, Any] = {"rows_total": len(rows), "unscored": unscored}
        if scored:
            entry.update(phase34.evaluate_binary_predictions(scored))
        models[name] = entry
    first = next(iter(predictions.values()), [])
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "threshold": thr,
        "images": len(first),
        "sources": sorted({r["source"] for r in first}),
        "conditions": sorted({r["condition"] for r in first}),
        "models": models,
        "warning": "Metrics describe only this labelled set and these degradations. They are not a general benchmark, "
                   "and new generators, heavy crops and low-resolution inputs are known weak spots.",
    }


is_smoke_test = eval_stats.is_smoke_test


def _stat_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"group": (r.get("group") or "").strip() or eval_stats.group_of(r["filename"]), "y": 1 if phase34._parse_label(r["label"]) else 0,
             "score": r["score"], "condition": r["condition"], "source": r["source"], "filename": r["filename"], "label": r["label"]}
            for r in rows]


def summarize_protocol(predictions: dict[str, list[dict[str, Any]]], calib_fraction: float = 0.3, seed: str = "lineage-eval",
                       fixed_threshold: float | None = None, n_boot: int = 1000) -> dict[str, Any]:
    """Leakage-safe report: threshold chosen on a calibration split, numbers reported on the held-out test split.

    Every model is evaluated on the SAME split (derived from the manifest, not from the scores), so models are comparable.
    The per-model entry keeps the shape ``summarize`` produces (so the app panel, model card and slide keep working) and adds
    ``threshold``, ``protocol`` and ``ci``.
    """
    first_name = next(iter(predictions))
    base_rows = _stat_rows(predictions[first_name])
    assignment, info = eval_stats.assign_split(base_rows, calib_fraction, seed)
    models: dict[str, Any] = {}
    thresholds: dict[str, float] = {}
    for name, rows in predictions.items():
        srows = _stat_rows(rows)
        res = eval_stats.evaluate_protocol(srows, calib_fraction, seed, fixed_threshold, n_boot)
        assert res["assignment"] == assignment, "models must share one split"
        thr = res["protocol"]["threshold"]
        thresholds[name] = thr
        test_rows = [r for r in srows if assignment[r["group"]] == "test"]
        scored = [{"label": r["label"], "score": r["score"], "threshold": thr, "condition": r["condition"]}
                  for r in test_rows if r["score"] is not None]
        entry: dict[str, Any] = {"rows_total": len(test_rows), "unscored": len(test_rows) - len(scored), "threshold": thr}
        if scored:
            entry.update(phase34.evaluate_binary_predictions(scored))
        entry["ci"] = res["ci"]
        entry["protocol"] = res["protocol"]
        models[name] = entry
    test_rows_n = sum(1 for r in base_rows if assignment[r["group"]] == "test")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "threshold": thresholds[first_name],
        "thresholds": thresholds,
        "images": len(base_rows),
        "images_test": test_rows_n,
        "originals_test": info["groups"]["test"],
        "originals_calib": info["groups"]["calib"],
        "sources": sorted({r["source"] for r in base_rows}),
        "conditions": sorted({r["condition"] for r in base_rows}),
        "protocol": {**info, "name": "calibration/test split by original image", "n_boot": n_boot,
                     "threshold_source": "fixed" if fixed_threshold is not None else "calibration split"},
        "models": models,
        "warning": "Metrics describe only this labelled set and these degradations, on a held-out test split. They are not a "
                   "general benchmark, and new generators, heavy crops and low-resolution inputs are known weak spots.",
        "split": assignment,
    }


def to_markdown(report: dict[str, Any]) -> str:
    """A table that can be pasted into the deck or the model card."""
    proto = report.get("protocol")
    if proto:
        lines = [f"Held-out test split: {report.get('images_test')} of {report['images']} images "
                 f"({proto['groups']['test']} test / {proto['groups']['calib']} calibration originals, seed {proto['seed']}). "
                 f"Threshold: {proto['threshold_source']}. Generated {report['generated_at']}", ""]
    else:
        lines = [f"Evaluated {report['images']} images · threshold {report['threshold']}% · generated {report['generated_at']}", ""]
    for name, m in report["models"].items():
        lines += [f"### {name}" + (f" (threshold {m['threshold']}%)" if proto and "threshold" in m else ""), ""]
        if "accuracy" not in m:
            lines += [f"No image could be scored ({m['unscored']} unscored).", ""]
            continue
        lines += ["| Condition | n | Accuracy | Precision | Recall | F1 | ROC-AUC |", "|---|---|---|---|---|---|---|"]
        def row(label: str, x: dict[str, Any]) -> str:
            auc = "n/a" if x.get("roc_auc") is None else f"{x['roc_auc']:.3f}"
            return f"| {label} | {x['samples']} | {x['accuracy']}% | {x['precision']}% | {x['recall']}% | {x['f1']}% | {auc} |"
        lines.append(row("**all**", m))
        for cond, x in (m.get("by_condition") or {}).items():
            lines.append(row(cond, x))
        tn, fp = m["confusion_matrix"][0]; fn, tp = m["confusion_matrix"][1]
        lines += ["", f"Confusion matrix (rows actual, columns predicted): real→real {tn}, real→fake {fp}, fake→real {fn}, fake→fake {tp}.",
                  f"Unscored images: {m['unscored']}.", ""]
        ci = m.get("ci")
        if ci:
            def span(k: str) -> str:
                x = ci["metrics"][k]
                return "n/a" if x["low"] is None else f"{x['point']}% (95% CI {x['low']} to {x['high']})"
            lines += [f"Uncertainty ({ci['n_boot']} bootstrap resamples of {ci['n_groups']} original images): accuracy {span('accuracy')}; "
                      f"recall {span('recall')}; specificity {span('specificity')}.", ""]
    lines.append(report["warning"])
    return "\n".join(lines)


def save_report(report: dict[str, Any], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


PREDICTION_COLUMNS = ("model", "filename", "label", "source", "condition", "score", "split", "group")


def save_predictions(predictions: dict[str, list[dict[str, Any]]], path: Path, split: dict[str, str] | None = None) -> None:
    """Per-image scores, next to latest.json. Needed to explain WHERE a model fails, not only how often."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(PREDICTION_COLUMNS)
        for model, rows in predictions.items():
            for r in rows:
                w.writerow([model, r["filename"], r["label"], r["source"], r["condition"], "" if r["score"] is None else r["score"],
                            "" if not split else split.get((r.get("group") or "").strip() or eval_stats.group_of(r["filename"]), ""),
                            (r.get("group") or "").strip()])


def load_predictions(path: Path) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.setdefault(r["model"], []).append({**{k: r[k] for k in ("filename", "label", "source", "condition")},
                                                   "score": None if r["score"] == "" else float(r["score"]),
                                                   "split": r.get("split") or "", "group": r.get("group") or ""})
    return out


def load_latest(path: Path | None = None) -> dict[str, Any] | None:
    p = Path(path or settings.EVAL_RESULTS_PATH)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
