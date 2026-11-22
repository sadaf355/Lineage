"""Evaluation statistics that keep a detector report honest. Pure standard library (no model, no database).

Three problems this solves:

1. **Leakage.** ``build_degraded.py`` makes ``<name>__jpeg_q50.jpg`` etc. from every original. If the original is in one
   split and its degraded copy in another, the model has effectively seen the test image. Rows are therefore grouped by the
   original's name and a whole group always lands in a single split.
2. **Threshold tuning on the reported data.** The decision threshold is chosen on the *calibration* split only; every number
   that is reported comes from the *test* split.
3. **False precision.** A few hundred images cannot support "93.2%". ``bootstrap_ci`` resamples whole groups (not single
   rows, which would understate the uncertainty because copies of one image are correlated) and returns a 95% interval.

Rows are dicts: ``{"group": str, "y": 0|1 (1 = fake), "score": float|None (0-100), "condition": str, "source": str}``.
"""
from __future__ import annotations

import hashlib
import math
import random
from collections import defaultdict
from typing import Any, Iterable, Sequence

DERIVED_SEP = "__"
SPLITS = ("calib", "test")


def group_of(filename: str) -> str:
    """``img_001__jpeg_q50.jpg`` -> ``img_001``; an original ``img_001.jpg`` -> ``img_001``."""
    name = str(filename).replace("\\", "/").rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return stem.split(DERIVED_SEP, 1)[0]


def _rank_key(seed: str, group: str) -> str:
    return hashlib.sha256(f"{seed}|{group}".encode("utf-8")).hexdigest()


def assign_split(rows: Iterable[dict[str, Any]], calib_fraction: float = 0.3, seed: str = "lineage-eval") -> tuple[dict[str, str], dict[str, Any]]:
    """Deterministic, stratified-by-label split of GROUPS. Returns ({group: 'calib'|'test'}, info).

    Each label keeps about ``calib_fraction`` of its groups for calibration, at least one group on each side when a label
    has two or more groups. The same seed always gives the same split, so a rerun is comparable.
    """
    if not 0.0 < calib_fraction < 1.0:
        raise ValueError("calib_fraction must be between 0 and 1 (exclusive).")
    label_of: dict[str, int] = {}
    for r in rows:
        g, y = r["group"], int(r["y"])
        if label_of.setdefault(g, y) != y:
            raise ValueError(f"Group '{g}' has rows with different labels; copies of one image must share a label.")
    by_label: dict[int, list[str]] = defaultdict(list)
    for g, y in label_of.items():
        by_label[y].append(g)
    assignment: dict[str, str] = {}
    warnings: list[str] = []
    for y, groups in by_label.items():
        ordered = sorted(groups, key=lambda g: _rank_key(seed, g))
        n = len(ordered)
        if n < 2:
            warnings.append(f"Only {n} group with label {'fake' if y else 'real'}: nothing can be held out for calibration.")
            n_calib = 0
        else:
            n_calib = min(n - 1, max(1, round(calib_fraction * n)))
        for i, g in enumerate(ordered):
            assignment[g] = "calib" if i < n_calib else "test"
    info = {
        "seed": seed, "calib_fraction": calib_fraction, "warnings": warnings,
        "groups": {s: sum(1 for v in assignment.values() if v == s) for s in SPLITS},
    }
    return assignment, info


def assert_no_leakage(rows: Sequence[dict[str, Any]], assignment: dict[str, str]) -> None:
    """Raises if any group is split across calibration and test (it cannot be, by construction; this is the guard)."""
    seen: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        seen[r["group"]].add(assignment[r["group"]])
    bad = sorted(g for g, s in seen.items() if len(s) > 1)
    if bad:
        raise AssertionError(f"Leakage: groups in both splits: {bad[:5]}")


def _auc(pos: list[float], neg: list[float]) -> float | None:
    """ROC-AUC as P(score_fake > score_real), ties counted as one half. Rank-sum with average ranks."""
    if not pos or not neg:
        return None
    pooled = sorted([(s, 1) for s in pos] + [(s, 0) for s in neg])
    ranks = [0.0] * len(pooled)
    i = 0
    while i < len(pooled):
        j = i
        while j + 1 < len(pooled) and pooled[j + 1][0] == pooled[i][0]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    rank_sum_pos = sum(rk for rk, (_, lab) in zip(ranks, pooled) if lab == 1)
    return (rank_sum_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def _pct(num: float, den: float) -> float | None:
    return None if den == 0 else round(100.0 * num / den, 1)


def metrics(rows: Sequence[dict[str, Any]], threshold: float) -> dict[str, Any]:
    """Confusion-matrix metrics in percent at ``threshold`` (score >= threshold means 'fake'). Unscored rows are skipped."""
    scored = [r for r in rows if r.get("score") is not None]
    tp = sum(1 for r in scored if r["y"] == 1 and r["score"] >= threshold)
    fn = sum(1 for r in scored if r["y"] == 1 and r["score"] < threshold)
    fp = sum(1 for r in scored if r["y"] == 0 and r["score"] >= threshold)
    tn = sum(1 for r in scored if r["y"] == 0 and r["score"] < threshold)
    recall, spec = _pct(tp, tp + fn), _pct(tn, tn + fp)
    precision = _pct(tp, tp + fp)
    f1 = None if (precision is None or recall is None or precision + recall == 0) else round(2 * precision * recall / (precision + recall), 1)
    auc = _auc([r["score"] for r in scored if r["y"] == 1], [r["score"] for r in scored if r["y"] == 0])
    return {
        "n": len(scored), "unscored": len(rows) - len(scored), "threshold": threshold,
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "accuracy": _pct(tp + tn, len(scored)), "precision": precision, "recall": recall, "specificity": spec, "f1": f1,
        "balanced_accuracy": None if recall is None or spec is None else round((recall + spec) / 2, 1),
        "roc_auc": None if auc is None else round(auc, 4),
    }


def pick_threshold(calib_rows: Sequence[dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    """Threshold that maximises F1 on the calibration rows (ties: higher balanced accuracy, then closest to 50).

    Raises ValueError when the calibration rows do not contain both classes, because then no threshold is meaningful.
    """
    scored = [r for r in calib_rows if r.get("score") is not None]
    if not any(r["y"] == 1 for r in scored) or not any(r["y"] == 0 for r in scored):
        raise ValueError("Calibration rows need at least one scored real and one scored fake image.")
    values = sorted({float(r["score"]) for r in scored})
    candidates = [values[0] - 0.01] + [(a + b) / 2 for a, b in zip(values, values[1:])] + [values[-1] + 0.01]
    best: tuple[tuple[float, float, float], float, dict[str, Any]] | None = None
    for t in candidates:
        m = metrics(scored, t)
        key = (m["f1"] if m["f1"] is not None else -1.0, m["balanced_accuracy"] or 0.0, -abs(t - 50.0))
        if best is None or key > best[0]:
            best = (key, t, m)
    assert best is not None
    return round(best[1], 2), best[2]


def wilson_interval(successes: float, n: int, level: float = 0.95) -> tuple[float, float] | None:
    """Wilson score interval for a proportion, in percent. Unlike a plain bootstrap it never collapses to a single point when
    a small sample happens to contain no errors (0 mistakes in 16 images is NOT evidence of a perfect detector)."""
    if n <= 0:
        return None
    z = {0.90: 1.6449, 0.95: 1.96, 0.99: 2.5758}.get(round(level, 2), 1.96)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return 100.0 * max(0.0, centre - half), 100.0 * min(1.0, centre + half)


def _quantile(sorted_vals: list[float], q: float) -> float:
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def bootstrap_ci(rows: Sequence[dict[str, Any]], threshold: float, names: Sequence[str] = ("accuracy", "recall", "specificity"),
                 n_boot: int = 1000, seed: int = 1234, level: float = 0.95) -> dict[str, Any]:
    """Cluster bootstrap: resample GROUPS with replacement, recompute each metric, take the percentile interval.

    Deterministic for a given seed. With fewer than 2 groups an interval is not defined, so ``low``/``high`` are None.
    """
    scored = [r for r in rows if r.get("score") is not None]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in scored:
        groups[r["group"]].append(r)
    keys = sorted(groups)
    point = metrics(scored, threshold)
    out: dict[str, Any] = {"level": level, "n_boot": n_boot, "n_groups": len(keys), "metrics": {}}
    rng = random.Random(seed)
    draws: dict[str, list[float]] = {n: [] for n in names}
    if len(keys) >= 2:
        for _ in range(n_boot):
            sample: list[dict[str, Any]] = []
            for _k in range(len(keys)):
                sample.extend(groups[keys[rng.randrange(len(keys))]])
            m = metrics(sample, threshold)
            for n in names:
                if m[n] is not None:
                    draws[n].append(m[n])
    alpha = (1 - level) / 2
    fake_groups = {g for g, rs in groups.items() if rs[0]["y"] == 1}
    real_groups = {g for g, rs in groups.items() if rs[0]["y"] == 0}
    n_eff = {"accuracy": len(keys), "recall": len(fake_groups), "specificity": len(real_groups)}
    for n in names:
        vals = sorted(draws[n])
        low = _quantile(vals, alpha) if vals else None
        high = _quantile(vals, 1 - alpha) if vals else None
        # Floor: the interval is never narrower than a Wilson interval that treats each ORIGINAL image as one trial.
        # (Rows are correlated copies of the same original, so the number of originals is the honest sample size.)
        point_val = point[n]
        if point_val is not None and n in n_eff and n_eff[n] > 0:
            w = wilson_interval(point_val / 100.0 * n_eff[n], n_eff[n], level)
            if w is not None:
                low = w[0] if low is None else min(low, w[0])
                high = w[1] if high is None else max(high, w[1])
        out["metrics"][n] = {
            "point": point_val,
            "low": None if low is None else round(low, 1),
            "high": None if high is None else round(high, 1),
        }
    out["method"] = ("Cluster bootstrap over original images, widened to at least a Wilson interval that counts each original "
                     "image once. Copies of an original (JPEG, crop, ...) are not independent evidence.")
    return out


def evaluate_protocol(rows: Sequence[dict[str, Any]], calib_fraction: float = 0.3, seed: str = "lineage-eval",
                      fixed_threshold: float | None = None, n_boot: int = 1000) -> dict[str, Any]:
    """Split by group, pick the threshold on the calibration split (or use ``fixed_threshold``), report on the test split."""
    assignment, info = assign_split(rows, calib_fraction, seed)
    assert_no_leakage(rows, assignment)
    calib = [r for r in rows if assignment[r["group"]] == "calib"]
    test = [r for r in rows if assignment[r["group"]] == "test"]
    notes = list(info["warnings"])
    if fixed_threshold is not None:
        thr, calib_metrics = float(fixed_threshold), (metrics(calib, float(fixed_threshold)) if calib else None)
        notes.append("Threshold was fixed by the operator, not calibrated.")
    else:
        try:
            thr, calib_metrics = pick_threshold(calib)
        except ValueError as exc:
            raise ValueError(f"Cannot calibrate: {exc} Add more images or pass a fixed threshold.") from exc
    overall = metrics(test, thr)
    conditions = sorted({str(r.get("condition", "")) for r in test if r.get("condition")})
    return {
        "protocol": {**info, "threshold": thr, "threshold_source": "fixed" if fixed_threshold is not None else "calibration split",
                     "calibration_metrics": calib_metrics, "notes": notes,
                     "rows": {"calib": len(calib), "test": len(test)}},
        "test": overall,
        "by_condition": {c: metrics([r for r in test if str(r.get("condition")) == c], thr) for c in conditions},
        "ci": bootstrap_ci(test, thr, n_boot=n_boot),
        "assignment": assignment,
    }


MIN_TEST_ORIGINALS = 200   # about 300 original images at the default 30% calibration share


def is_smoke_test(report: dict[str, Any]) -> bool:
    """True when a report is too small to quote. Degraded copies are not independent images, so only originals count."""
    if "originals_test" in report:
        return report["originals_test"] < MIN_TEST_ORIGINALS
    return report["images"] < 300


# ---- near-duplicate handling -------------------------------------------------------------------------------------
# Public datasets often contain the same picture twice under different names. If one copy is used to calibrate and the
# other to test, the test number is inflated. We cluster near-duplicates and keep each cluster in a single split.

def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def cluster(names: Sequence[str], is_near) -> list[set[str]]:
    """Connected components of the graph whose edges are ``is_near(a, b)``. Only clusters with 2+ members are returned."""
    names = sorted(names)
    parent = {n: n for n in names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if is_near(a, b):
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    comps: dict[str, set[str]] = defaultdict(set)
    for n in names:
        comps[find(n)].add(n)
    return [c for c in comps.values() if len(c) > 1]


def near_duplicate_clusters(hashes: dict[str, int], max_dist: int = 6) -> list[set[str]]:
    """Cluster by bit distance between integer hashes (convenience wrapper around ``cluster``)."""
    return cluster(list(hashes), lambda a, b: hamming(hashes[a], hashes[b]) <= max_dist)


def color_layout_distance(a: Sequence[float], b: Sequence[float]) -> float:
    """Mean absolute difference between two colour-layout vectors (0-255 scale)."""
    return sum(abs(x - y) for x, y in zip(a, b)) / max(1, len(a))


def merged_groups(filename_to_group: dict[str, str], clusters: list[set[str]]) -> dict[str, str]:
    """Give every member of a near-duplicate cluster the same group (the alphabetically first), so they share a split.

    ``clusters`` contain ORIGINAL filenames; derived copies follow their original's group because they share its name prefix.
    """
    canon: dict[str, str] = {}
    for cluster in clusters:
        target = min(filename_to_group[f] for f in cluster)
        for f in cluster:
            canon[filename_to_group[f]] = target
    return {fn: canon.get(g, g) for fn, g in filename_to_group.items()}
