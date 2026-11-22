"""Phase B and C wiring: the pieces exist, are connected, and are documented. Static checks, no network."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _t(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_phase_b_pipeline_runs_selftest_then_leakage_check_before_scoring():
    sh = _t("backend/eval/phase_b.sh")
    order = [sh.index(x) for x in ("eval/selftest.py", "eval/build_manifest.py", "eval/build_degraded.py",
                                   "eval/check_leakage.py --apply", "eval/run_eval.py --models")]
    assert order == sorted(order)


def test_eval_readme_documents_the_protocol_and_intervals():
    readme = _t("backend/eval/README.md")
    for needle in ("calibration split only", "held-out", "95% interval", "smoke test", "--protocol fixed"):
        assert needle in readme, needle
    assert "Licences and terms change" in _t("backend/eval/DATASETS.md")


def test_demo_launcher_runs_the_offline_check_in_offline_mode():
    demo = _t("scripts/demo.sh")
    assert "offline_check.py" in demo and demo.index("offline_check.py") < demo.index("Starting the stack")


def test_runbook_references_every_phase_c_tool_and_each_exists():
    book = _t("docs/DEMO_RUNBOOK.md")
    for tool, rel in (("trial_feature_match.py", "scripts/trial_feature_match.py"), ("offline_check.py", "backend/offline_check.py"),
                      ("rehearsal_timer.py", "scripts/rehearsal_timer.py"), ("demo_check.py", "scripts/demo_check.py")):
        assert tool in book, tool
        assert (ROOT / rel).is_file(), rel
    assert "rehearsal_log.csv" in _t(".gitignore")


def test_in_app_panel_never_shows_a_smoke_test_as_measured():
    panel = _t("frontend/src/components/DetectorEvaluationPanel.tsx")
    assert "Smoke test, not a result" in panel and "data.smoke_test" in panel and "95% intervals" in panel
    api = _t("frontend/src/lib/api.ts")
    assert "smoke_test?: boolean" in api and "originals_test?: number" in api


cv2 = pytest.importorskip("cv2")


def _load_trial():
    spec = importlib.util.spec_from_file_location("trial_feature_match", ROOT / "scripts" / "trial_feature_match.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["trial_feature_match"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_trial_reports_insufficient_features_for_a_flat_image(tmp_path):
    from PIL import Image
    trial = _load_trial()
    flat = tmp_path / "flat.png"
    Image.new("RGB", (300, 300), (120, 130, 140)).save(flat)
    res = trial.run(flat, [])
    assert res["verdict"] == "insufficient_features"
    assert "too little texture" in trial.render(res)


def test_trial_flags_a_false_positive_when_an_unrelated_file_is_really_the_same_image():
    trial = _load_trial()
    sample = ROOT / "backend" / "demo_assets" / "sample_case_image.jpg"
    res = trial.run(sample, [sample.with_name("sample_case_image.jpg")])   # a "negative" that is actually the same photo
    assert res["verdict"] == "false_positive"
    assert "TRACE_FEATURE_MATCH_ENABLED=false" in trial.render(res)


def test_trial_passes_on_the_bundled_sample_with_the_other_samples_as_negatives():
    trial = _load_trial()
    sample = ROOT / "backend" / "demo_assets" / "sample_case_image.jpg"
    res = trial.run(sample, trial.negatives_from(None, sample))
    assert res["verdict"] == "ok"
    expected = [v for v in res["variants"] if v["expected"]]
    assert sum(v["status"] == "match" for v in expected) >= len(expected) - 1
