"""Evaluation harness tests. They use fake scorers, so no model download is needed."""
import csv
import sys
from pathlib import Path

import pytest
from PIL import Image

from app.services import eval_harness, phase34

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
import build_degraded  # noqa: E402


def _make_set(tmp_path: Path, n_each: int = 6) -> Path:
    images = tmp_path / "images"
    images.mkdir()
    rows = []
    for i in range(n_each):
        for label, shade in (("real", 40 + i), ("fake", 200 - i)):
            name = f"{label}_{i}.png"
            Image.new("RGB", (64, 48), (shade, shade, shade)).save(images / name)
            rows.append({"filename": name, "label": label, "source": "synthetic-test", "condition": "original"})
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["filename", "label", "source", "condition"])
        w.writeheader(); w.writerows(rows)
    return manifest


def test_roc_auc_known_values():
    assert phase34.roc_auc([True, True, False, False], [0.9, 0.8, 0.2, 0.1]) == 1.0
    assert phase34.roc_auc([True, True, False, False], [0.1, 0.2, 0.8, 0.9]) == 0.0
    assert phase34.roc_auc([True, False], [0.5, 0.5]) == 0.5
    assert phase34.roc_auc([True, True], [0.5, 0.9]) is None  # one class only


def test_metrics_include_confusion_matrix_and_conditions():
    rows = [
        {"label": "fake", "score": 90, "condition": "original"},
        {"label": "real", "score": 10, "condition": "original"},
        {"label": "fake", "score": 30, "condition": "jpeg_q50"},   # missed after compression
        {"label": "real", "score": 20, "condition": "jpeg_q50"},
    ]
    r = phase34.evaluate_binary_predictions(rows)
    assert r["samples"] == 4 and r["confusion_matrix"] == [[2, 0], [1, 1]]
    assert r["by_condition"]["original"]["accuracy"] == 100.0
    assert r["by_condition"]["jpeg_q50"]["recall"] == 0.0
    assert r["roc_auc"] is not None


def test_degraded_copies_are_added_once(tmp_path):
    manifest = _make_set(tmp_path, 2)
    import subprocess
    cmd = [sys.executable, str(ROOT / "eval" / "build_degraded.py"), "--manifest", str(manifest)]
    subprocess.run(cmd, check=True, capture_output=True)
    rows = eval_harness.load_manifest(manifest)
    assert len(rows) == 4 * 5  # 4 originals + 4 conditions each
    assert {r["condition"] for r in rows} == {"original", *build_degraded.CONDITIONS}
    subprocess.run(cmd, check=True, capture_output=True)  # idempotent
    assert len(eval_harness.load_manifest(manifest)) == 20


def test_manifest_validation_reports_problems(tmp_path):
    manifest = _make_set(tmp_path, 1)
    text = manifest.read_text().replace("real,", "maybe,", 1)
    manifest.write_text(text)
    with pytest.raises(eval_harness.ManifestError) as exc:
        eval_harness.load_manifest(manifest)
    assert "Unsupported label" in str(exc.value)


def test_missing_file_is_reported(tmp_path):
    manifest = _make_set(tmp_path, 1)
    (tmp_path / "images" / "real_0.png").unlink()
    with pytest.raises(eval_harness.ManifestError) as exc:
        eval_harness.load_manifest(manifest)
    assert "file not found" in str(exc.value)


def test_unscored_images_are_excluded_not_counted(tmp_path):
    manifest = _make_set(tmp_path, 3)
    rows = eval_harness.load_manifest(manifest)
    def flaky(raw: bytes):
        # brightness decides the "score"; one specific image fails to score at all
        img = Image.open(__import__("io").BytesIO(raw)).convert("L")
        v = img.getpixel((0, 0))
        return None if v == 40 else float(v) / 255 * 100
    preds = eval_harness.score_manifest(rows, tmp_path / "images", {"flaky": flaky})
    report = eval_harness.summarize(preds, threshold=50)
    m = report["models"]["flaky"]
    assert m["unscored"] == 1 and m["samples"] == 5
    assert m["accuracy"] == 100.0
    md = eval_harness.to_markdown(report)
    assert "Unscored images: 1" in md and "not a general benchmark" in md


def test_save_and_load_latest_roundtrip(tmp_path):
    report = {"generated_at": "x", "models": {}}
    p = tmp_path / "r" / "latest.json"
    eval_harness.save_report(report, p)
    assert eval_harness.load_latest(p) == report
    assert eval_harness.load_latest(tmp_path / "missing.json") is None
