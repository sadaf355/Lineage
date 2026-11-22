#!/usr/bin/env python3
"""A cue-sheet timer for demo rehearsals. Press Enter at the start of each step; it tells you where you ran over.

    python scripts/rehearsal_timer.py 5min          # run the 5-minute script
    python scripts/rehearsal_timer.py 2min
    python scripts/rehearsal_timer.py projector     # the "no screen" drill
    python scripts/rehearsal_timer.py --status      # how many clean runs you have, per script

Each run is appended to rehearsal_log.csv (git-ignored). A script counts as READY after three runs in a row that finish within
10% of the time budget. Steps mirror docs/DEMO_RUNBOOK.md section D.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "rehearsal_log.csv"
TOLERANCE = 0.10
REQUIRED_CLEAN_RUNS = 3

# (step label, seconds budgeted for the step). The cue is what you say or do.
SCRIPTS: dict[str, dict] = {
    "5min": {"title": "5-minute demo", "steps": [
        ("Problem in one sentence (a harmful image spreads; nobody can show where it came from or that it was altered)", 30),
        ("Dashboard + Detector evaluation panel; read the weakest condition aloud", 45),
        ("Upload and detect. Say: a likelihood, not proof", 45),
        ("Fingerprint, then trace the URL, review the match, Accept", 75),
        ("Lineage Map, evidence integrity, sign and verify the manifest", 45),
        ("Report, then the limits slide: what LINEAGE refuses to claim", 60),
    ]},
    "2min": {"title": "2-minute demo", "steps": [
        ("Upload + detect (a likelihood, not proof)", 30),
        ("Trace + Accept", 50),
        ("Integrity + report, one sentence on limits", 40),
    ]},
    "projector": {"title": "'Projector fails' drill (no screen)", "steps": [
        ("Say the problem and the idea in two sentences", 20),
        ("Talk through the click path from memory (printed one-pager)", 60),
        ("Hand over the backup recording; say what they will see", 20),
        ("Name the three limits out loud (not proof, public sources only, audio not scored)", 20),
    ]},
}


def budget(script: str) -> int:
    return sum(s for _, s in SCRIPTS[script]["steps"])


def evaluate(script: str, step_seconds: list[float]) -> dict:
    """Pure summary of one run: per-step overrun and whether the total is within tolerance."""
    steps = SCRIPTS[script]["steps"]
    if len(step_seconds) != len(steps):
        raise ValueError("step_seconds must have one entry per step")
    total, allowed = sum(step_seconds), budget(script)
    over = [round(t - b, 1) for t, (_, b) in zip(step_seconds, steps)]
    worst = max(range(len(steps)), key=lambda i: over[i])
    return {"script": script, "total": round(total, 1), "budget": allowed, "clean": total <= allowed * (1 + TOLERANCE),
            "overrun_by_step": over, "worst_step": steps[worst][0] if over[worst] > 0 else None, "worst_over": max(over[worst], 0)}


def read_log(path: Path = LOG) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def append_log(result: dict, path: Path = LOG) -> None:
    new = not path.is_file()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["when", "script", "total_seconds", "budget_seconds", "clean", "worst_step"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), result["script"], result["total"], result["budget"],
                    int(result["clean"]), result["worst_step"] or ""])


def readiness(rows: list[dict]) -> dict[str, dict]:
    """Per script: runs so far, and READY once the last REQUIRED_CLEAN_RUNS runs were all clean."""
    out: dict[str, dict] = {}
    for name in SCRIPTS:
        mine = [r for r in rows if r["script"] == name]
        last = mine[-REQUIRED_CLEAN_RUNS:]
        ready = len(last) == REQUIRED_CLEAN_RUNS and all(r["clean"] == "1" for r in last)
        out[name] = {"runs": len(mine), "ready": ready, "last_total": float(mine[-1]["total_seconds"]) if mine else None,
                     "budget": budget(name)}
    return out


def fmt(sec: float) -> str:
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def print_status(path: Path = LOG) -> None:
    for name, st in readiness(read_log(path)).items():
        flag = "READY" if st["ready"] else "not ready"
        last = "no runs yet" if st["last_total"] is None else f"last {fmt(st['last_total'])} of {fmt(st['budget'])}"
        print(f"{SCRIPTS[name]['title']:<40} {st['runs']:>2} run(s)  {last:<22} {flag}")
    print(f"\nREADY = last {REQUIRED_CLEAN_RUNS} runs each finished within {int(TOLERANCE * 100)}% of the budget.")


def run_interactive(script: str, log: Path = LOG) -> dict:
    info = SCRIPTS[script]
    print(f"\n{info['title']}  (budget {fmt(budget(script))}).  Press Enter to start; Enter again at the start of each next step.")
    input()
    marks = [time.monotonic()]
    for i, (label, secs) in enumerate(info["steps"], start=1):
        print(f"\n[{i}/{len(info['steps'])}] {label}   (about {secs}s)")
        input("   Enter when this step is done > ")
        marks.append(time.monotonic())
    seconds = [b - a for a, b in zip(marks, marks[1:])]
    result = evaluate(script, seconds)
    print(f"\nTotal {fmt(result['total'])} of {fmt(result['budget'])}: {'within budget' if result['clean'] else 'OVER BUDGET'}.")
    for (label, b), t in zip(info["steps"], seconds):
        print(f"  {fmt(t)} / {fmt(b)}  {'  <-- over' if t > b * (1 + TOLERANCE) else ''}  {label[:70]}")
    if result["worst_step"]:
        print(f"\nBiggest overrun: {result['worst_step'][:90]} (+{result['worst_over']:.0f}s). Cut words there first.")
    append_log(result, log)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", nargs="?", choices=sorted(SCRIPTS))
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--log", default=str(LOG), help="CSV log path (default: rehearsal_log.csv)")
    a = ap.parse_args()
    if a.status or not a.script:
        print_status(Path(a.log))
        return 0
    try:
        run_interactive(a.script, Path(a.log))
    except (KeyboardInterrupt, EOFError):
        print("\nStopped; this run was not logged.")
        return 1
    print_status(Path(a.log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
