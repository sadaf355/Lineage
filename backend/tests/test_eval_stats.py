"""Evaluation protocol: no leakage, calibration-only thresholds, honest intervals. Synthetic data only."""
import random
import subprocess
import sys
from pathlib import Path

import pytest

from app.services import eval_stats as es

BACKEND = Path(__file__).resolve().parent.parent


def _rows(n=60, conds=("original", "jpeg_q50", "crop_80"), seed=7):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        y = i % 2
        for c in conds:
            base = (70 if y else 30) - (8 if c != "original" and y else 0)
            out.append({"group": f"img{i:03d}", "y": y, "score": min(100, max(0, rnd.gauss(base, 15))), "condition": c, "source": f"s{i % 2}"})
    return out


def test_group_of_strips_degradation_suffix_and_directories():
    assert es.group_of("img_001__jpeg_q50.jpg") == "img_001"
    assert es.group_of("sub/dir/img_001.png") == "img_001"
    assert es.group_of("a__b__c.png") == "a"


def test_copies_of_one_original_never_cross_splits_and_split_is_deterministic():
    rows = _rows()
    a, info = es.assign_split(rows, 0.3, "s")
    b, _ = es.assign_split(rows, 0.3, "s")
    c, _ = es.assign_split(rows, 0.3, "other")
    assert a == b and a != c
    es.assert_no_leakage(rows, a)
    assert info["groups"] == {"calib": 18, "test": 42}
    # both labels appear in both splits
    for split in ("calib", "test"):
        assert {r["y"] for r in rows if a[r["group"]] == split} == {0, 1}


def test_group_with_mixed_labels_is_rejected_and_unknown_groups_are_caught():
    rows = _rows(4)
    mixed = [dict(rows[0], group="g"), dict(rows[3], group="g")]      # rows[0] is a real image, rows[3] a fake one
    assert rows[0]["y"] != rows[3]["y"]
    with pytest.raises(ValueError):
        es.assign_split(mixed, 0.3)
    with pytest.raises(KeyError):
        es.assert_no_leakage(rows, {"img000": "calib"})                # a row whose group has no split assignment


def test_metrics_and_auc_known_values():
    rows = [{"y": 1, "score": 90}, {"y": 1, "score": 80}, {"y": 0, "score": 20}, {"y": 0, "score": 60}]
    m = es.metrics(rows, 50)
    assert (m["tp"], m["fn"], m["fp"], m["tn"]) == (2, 0, 1, 1)
    assert m["accuracy"] == 75.0 and m["recall"] == 100.0 and m["specificity"] == 50.0
    assert m["roc_auc"] == 1.0
    tied = es.metrics([{"y": 1, "score": 5}, {"y": 0, "score": 5}], 50)
    assert tied["roc_auc"] == 0.5
    assert es.metrics([{"y": 1, "score": None}], 50)["n"] == 0


def test_threshold_is_picked_on_calibration_rows_only():
    calib = [{"y": 1, "score": s} for s in (70, 75, 80)] + [{"y": 0, "score": s} for s in (20, 25, 30)]
    thr, m = es.pick_threshold(calib)
    assert 30 < thr < 70 and m["f1"] == 100.0
    with pytest.raises(ValueError):
        es.pick_threshold([{"y": 1, "score": 90}])


def test_bootstrap_ci_is_deterministic_brackets_the_estimate_and_widens_with_less_data():
    rows = _rows(80, ("original",))
    ci1 = es.bootstrap_ci(rows, 50, n_boot=300, seed=5)
    ci2 = es.bootstrap_ci(rows, 50, n_boot=300, seed=5)
    assert ci1 == ci2
    a = ci1["metrics"]["accuracy"]
    assert a["low"] <= a["point"] <= a["high"]
    small = es.bootstrap_ci([r for r in rows if int(r["group"][3:]) < 16], 50, n_boot=300, seed=5)["metrics"]["accuracy"]
    assert (small["high"] - small["low"]) > (a["high"] - a["low"])
    one = es.bootstrap_ci([r for r in rows if r["group"] == "img000"], 50, n_boot=50)
    assert one["metrics"]["accuracy"]["low"] is not None and one["metrics"]["accuracy"]["low"] < 100   # never a bare 100


def test_a_perfect_small_sample_does_not_get_a_zero_width_interval():
    """0 mistakes in 16 originals must not read as '100% (CI 100 to 100)'."""
    rows = [{"group": f"g{i}", "y": i % 2, "score": 95 if i % 2 else 5, "condition": "original", "source": "s"} for i in range(16)]
    m = es.bootstrap_ci(rows, 50, n_boot=200)["metrics"]
    assert m["accuracy"]["point"] == 100.0
    assert m["accuracy"]["low"] < 85 and m["accuracy"]["high"] == 100.0       # Wilson for 16/16 is about 80.6 to 100
    assert m["recall"]["low"] < 70 and m["specificity"]["low"] < 70           # only 8 originals per class


def test_wilson_interval_known_values():
    lo, hi = es.wilson_interval(16, 16)
    assert 80 < lo < 81 and hi == 100.0
    lo, hi = es.wilson_interval(50, 100)
    assert 40 < lo < 41 and 59 < hi < 60
    assert es.wilson_interval(0, 0) is None


def test_evaluate_protocol_reports_test_split_only():
    rows = _rows()
    res = es.evaluate_protocol(rows, 0.3, "s", None, 100)
    assert res["protocol"]["rows"]["calib"] + res["protocol"]["rows"]["test"] == len(rows)
    assert res["test"]["n"] == res["protocol"]["rows"]["test"]
    assert res["protocol"]["threshold_source"] == "calibration split"
    fixed = es.evaluate_protocol(rows, 0.3, "s", 55.0, 50)
    assert fixed["protocol"]["threshold"] == 55.0 and fixed["protocol"]["threshold_source"] == "fixed"


def test_smoke_test_counts_originals_not_degraded_copies():
    assert es.is_smoke_test({"images": 5000, "originals_test": 60}) is True
    assert es.is_smoke_test({"images": 5000, "originals_test": 250}) is False
    assert es.is_smoke_test({"images": 100}) is True


def test_selftest_script_passes():
    done = subprocess.run([sys.executable, str(BACKEND / "eval" / "selftest.py")], capture_output=True, text=True, cwd=BACKEND)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "NOT A DETECTOR RESULT" in done.stdout
