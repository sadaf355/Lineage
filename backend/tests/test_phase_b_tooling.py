"""Phase B tooling. Uses synthetic images and fake scores: it checks the machinery, never claims detector accuracy."""
import csv
import json
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "eval"))
import analyze_failures as af   # noqa: E402
import build_manifest as bm     # noqa: E402
import fill_model_card as fmc   # noqa: E402
import make_slide as ms         # noqa: E402
import model_info as mi         # noqa: E402
from app.services import eval_harness  # noqa: E402


def _img(path: Path, shade: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), (shade, shade, 10)).save(path)


def _write_sources(path: Path, rows):
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["source", "url", "licence", "fake_kind"]); w.writeheader(); w.writerows(rows)


def test_manifest_refuses_source_without_licence(tmp_path):
    _img(tmp_path / "inc" / "ds" / "real" / "a.png", 10)
    _write_sources(tmp_path / "sources.csv", [{"source": "ds", "url": "https://x", "licence": "TODO", "fake_kind": ""}])
    with pytest.raises(bm.BuildError, match="licence"):
        bm.build(tmp_path / "inc", tmp_path / "img", tmp_path / "sources.csv", tmp_path / "m.csv")


def test_manifest_refuses_source_missing_from_sources_csv(tmp_path):
    _img(tmp_path / "inc" / "mystery" / "fake" / "a.png", 10)
    _write_sources(tmp_path / "sources.csv", [])
    with pytest.raises(bm.BuildError, match="no row"):
        bm.build(tmp_path / "inc", tmp_path / "img", tmp_path / "sources.csv", tmp_path / "m.csv")


def test_manifest_builds_dedupes_drops_conflicts_and_warns(tmp_path):
    inc = tmp_path / "inc"
    _img(inc / "a" / "real" / "r1.png", 10); _img(inc / "a" / "real" / "r1_copy.png", 10)    # exact duplicate
    _img(inc / "a" / "real" / "r2.png", 20)
    _img(inc / "b" / "fake" / "f1.png", 200)
    _img(inc / "b" / "fake" / "both.png", 99); _img(inc / "a" / "real" / "both.png", 99)    # same pixels, both labels
    (inc / "b" / "fake" / "notes.txt").write_text("hi"); (inc / "b" / "fake" / "bad.png").write_bytes(b"not an image")
    _write_sources(tmp_path / "sources.csv", [
        {"source": "a", "url": "https://a", "licence": "CC-BY-4.0", "fake_kind": ""},
        {"source": "b", "url": "https://b", "licence": "research-only", "fake_kind": "face swap"}])
    s = bm.build(inc, tmp_path / "img", tmp_path / "sources.csv", tmp_path / "m.csv")
    assert s["by_label"] == {"real": 2, "fake": 1}
    assert s["skipped"]["duplicate"] >= 1 and s["skipped"]["not a readable image"] == 1 and s["skipped"]["unsupported extension"] == 1
    assert any("same file under both labels" in k for k in s["skipped"])
    rows = list(csv.DictReader((tmp_path / "m.csv").open()))
    assert {r["condition"] for r in rows} == {"original"} and all((tmp_path / "img" / r["filename"]).is_file() for r in rows)
    assert any("smoke test" in w for w in s["warnings"]) and any("Fewer than two kinds" in w for w in s["warnings"])
    eval_harness.load_manifest(tmp_path / "m.csv", tmp_path / "img")   # the harness accepts what we wrote


def test_model_info_reports_missing_fields_instead_of_guessing():
    full = mi.summarize_model("o/m", {"cardData": {"license": "apache-2.0", "datasets": ["ds1"]}, "sha": "abc123def456789"})
    assert full["licence"] == "apache-2.0" and full["training_datasets"] == ["ds1"]
    bare = mi.summarize_model("o/n", {"tags": ["transformers"]})
    assert bare["licence"] == mi.NOT_STATED and bare["training_datasets"] == [mi.NOT_STATED] and bare["revision"] == mi.NOT_STATED
    md = mi.to_markdown([full, bare])
    assert "apache-2.0" in md and mi.NOT_STATED in md
    from_tags = mi.summarize_model("o/t", {"tags": ["license:mit", "dataset:foo/bar"]})
    assert from_tags["licence"] == "mit" and from_tags["training_datasets"] == ["foo/bar"]


def _preds():
    rows = lambda scores: [  # noqa: E731
        {"filename": f"{lab}{i}_{cond}.png", "label": lab, "source": src, "condition": cond, "score": sc}
        for (lab, i, cond, src), sc in scores]
    keys = [("real", 1, "original", "s1"), ("real", 2, "original", "s2"), ("fake", 3, "original", "s1"), ("fake", 4, "original", "s2"),
            ("real", 1, "screenshot", "s1"), ("fake", 3, "screenshot", "s1")]
    good = rows(list(zip(keys, [10, 20, 90, 80, 30, 40])))        # screenshot fake missed
    ens_worse = rows(list(zip(keys, [10, 60, 90, 80, 30, 40])))   # one extra false positive
    return {"A": good, "ensemble (A + B)": ens_worse}


def test_failure_analysis_computes_from_scores_and_calls_out_worse_ensemble():
    md = af.analyze(_preds(), 50.0)
    assert "Largest drop: **screenshot**" in md
    assert "WORSE than the best single model" in md
    assert "s2" in md and "False-positive" in md


def test_predictions_roundtrip(tmp_path):
    eval_harness.save_predictions(_preds(), tmp_path / "p.csv")
    again = eval_harness.load_predictions(tmp_path / "p.csv")
    assert again["A"][0]["score"] == 10.0 and len(again["ensemble (A + B)"]) == 6


REPORT = {"generated_at": "2026-10-02T10:00:00+00:00", "threshold": 50.0, "images": 12, "sources": ["s1"], "conditions": ["original"],
          "warning": "w", "models": {"A": {"samples": 12, "accuracy": 91.7, "precision": 90.0, "recall": 88.0, "f1": 89.0, "roc_auc": 0.95,
                                           "confusion_matrix": [[5, 1], [1, 5]], "unscored": 0, "rows_total": 12,
                                           "by_condition": {"original": {"samples": 6, "accuracy": 100.0, "precision": 100.0, "recall": 100.0, "f1": 100.0, "roc_auc": 1.0}}}}}


def test_model_card_blocks_are_filled_and_smoke_test_is_flagged(tmp_path):
    card = tmp_path / "card.md"
    shutil.copy(ROOT.parent / "docs" / "DETECTOR_MODEL_CARD.md", card)
    res = tmp_path / "results"; res.mkdir()
    (res / "latest.json").write_text(json.dumps(REPORT))
    (res / "latest.md").write_text("| table |")
    (res / "failure_modes.md").write_text("FAILURES-HERE")
    sys.argv = ["x", "--card", str(card), "--results", str(res), "--manifest", str(tmp_path / "none.csv")]
    assert fmc.main() == 0
    text = card.read_text()
    assert "| table |" in text and "FAILURES-HERE" in text and "SMOKE TEST ONLY" in text
    assert "results not yet measured" not in text and text.count("BEGIN:auto") == 5     # markers survive for re-runs
    assert fmc.main() == 0                                                              # idempotent


def test_model_card_stays_unmeasured_without_results(tmp_path):
    card = tmp_path / "card.md"; shutil.copy(ROOT.parent / "docs" / "DETECTOR_MODEL_CARD.md", card)
    sys.argv = ["x", "--card", str(card), "--results", str(tmp_path / "empty")]
    assert fmc.main() == 2 and "results not yet measured" in card.read_text()


def test_slide_is_built_from_results_and_stamped_when_small(tmp_path):
    from pptx import Presentation
    out = tmp_path / "s.pptx"
    ms.build(REPORT, out)
    prs = Presentation(str(out))
    texts = " ".join(sh.text_frame.text for sh in prs.slides[0].shapes if sh.has_text_frame)
    assert "SMOKE TEST" in texts and "not proof" in texts
    table = next(sh for sh in prs.slides[0].shapes if sh.has_table).table
    assert table.cell(1, 3).text == "91.7%"
    assert "SMOKE TEST" in ms.to_markdown(REPORT)
    big = dict(REPORT, images=400)
    assert "SMOKE TEST" not in ms.to_markdown(big)


def test_slide_refuses_when_nothing_measured(tmp_path):
    sys.argv = ["x", "--results", str(tmp_path / "nope.json")]
    assert ms.main() == 2
