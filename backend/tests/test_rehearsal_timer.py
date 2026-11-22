import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "rehearsal_timer.py"


def _load():
    spec = importlib.util.spec_from_file_location("rehearsal_timer", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rehearsal_timer"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_budgets_match_the_runbook_scripts():
    rt = _load()
    assert rt.budget("5min") == 300 and rt.budget("2min") == 120 and rt.budget("projector") == 120


def test_evaluate_flags_overruns_and_names_the_worst_step():
    rt = _load()
    steps = [b for _, b in rt.SCRIPTS["2min"]["steps"]]
    ok = rt.evaluate("2min", [float(s) for s in steps])
    assert ok["clean"] and ok["worst_step"] is None
    slow = rt.evaluate("2min", [steps[0], steps[1] + 40.0, steps[2]])
    assert not slow["clean"] and "Trace" in slow["worst_step"] and slow["worst_over"] == 40.0
    near = rt.evaluate("2min", [s * 1.08 for s in steps])
    assert near["clean"]                                  # within the 10% tolerance


def test_ready_needs_three_clean_runs_in_a_row(tmp_path):
    rt = _load()
    log = tmp_path / "log.csv"
    clean = rt.evaluate("2min", [30.0, 50.0, 40.0])
    dirty = rt.evaluate("2min", [60.0, 80.0, 70.0])
    for r in (clean, clean, dirty):
        rt.append_log(r, log)
    assert rt.readiness(rt.read_log(log))["2min"]["ready"] is False
    for r in (clean, clean, clean):
        rt.append_log(r, log)
    st = rt.readiness(rt.read_log(log))["2min"]
    assert st["ready"] is True and st["runs"] == 6
    assert rt.readiness(rt.read_log(log))["5min"]["runs"] == 0


def test_interactive_run_logs_and_prints_status(tmp_path):
    log = tmp_path / "log.csv"
    n_steps = len(_load().SCRIPTS["2min"]["steps"])
    done = subprocess.run([sys.executable, str(SCRIPT), "2min", "--log", str(log)], input="\n" * (n_steps + 1),
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "within budget" in done.stdout and "run(s)" in done.stdout
    rows = list(csv.DictReader(log.open()))
    assert len(rows) == 1 and rows[0]["script"] == "2min" and rows[0]["clean"] == "1"


def test_interrupted_run_is_not_logged(tmp_path):
    log = tmp_path / "log.csv"
    done = subprocess.run([sys.executable, str(SCRIPT), "5min", "--log", str(log)], input="\n", capture_output=True, text=True, timeout=60)
    assert done.returncode == 1 and not log.exists()
