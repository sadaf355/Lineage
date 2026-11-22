#!/usr/bin/env python3
"""
One command to find out whether THIS machine runs LINEAGE cleanly.

    python scripts/first_run.py                 # install + backend tests + frontend tests + build, then a PASS/FAIL table
    python scripts/first_run.py --c2pa          # also install the optional C2PA signature validator
    python scripts/first_run.py --ml            # also install the optional ML models (needs Python 3.12)
    python scripts/first_run.py --skip-frontend # backend only
    python scripts/first_run.py --start         # after the checks pass, start API (8000) and web app (5173)
    python scripts/first_run.py --dry-run       # show what would run, change nothing

Works on Windows, macOS and Linux. Needs Python 3.11+ and (for the frontend) Node 20+, plus internet for package installs.
It stops at the first failed step and prints the command and the last lines of its output so the error is easy to report.
"""
from __future__ import annotations

import argparse
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
IS_WIN = os.name == "nt"
results: list[tuple[str, str, float, str]] = []


def venv_python() -> Path:
    return BACKEND / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python")


def run(label: str, cmd: list[str], cwd: Path, dry: bool, env: dict | None = None, tail: int = 25) -> bool:
    shown = " ".join(str(c) for c in cmd)
    print(f"\n=== {label}\n    $ {shown}   (in {cwd.relative_to(ROOT) if cwd != ROOT else '.'})", flush=True)
    if dry:
        results.append((label, "SKIP (dry run)", 0.0, ""))
        return True
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, text=True, capture_output=True, shell=False)
    except FileNotFoundError as e:
        results.append((label, "FAIL", time.time() - t0, f"command not found: {e.filename}"))
        print(f"    FAIL: command not found: {e.filename}")
        return False
    out = (p.stdout or "") + (p.stderr or "")
    dt = time.time() - t0
    if p.returncode == 0:
        results.append((label, "PASS", dt, ""))
        print(f"    PASS ({dt:.0f}s)")
        return True
    last = "\n".join(out.strip().splitlines()[-tail:])
    results.append((label, "FAIL", dt, last))
    print(f"    FAIL (exit {p.returncode}). Last lines:\n{last}")
    return False


def summary() -> None:
    print("\n" + "=" * 66)
    print(f"{'STEP':<44}{'RESULT':<10}{'TIME':>8}")
    for label, res, dt, _ in results:
        print(f"{label:<44}{res:<10}{dt:>7.0f}s")
    print("=" * 66)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--c2pa", action="store_true", help="install the optional Content Credentials validator (requirements-c2pa.txt)")
    ap.add_argument("--ml", action="store_true", help="install optional ML extras (requirements-ml.txt)")
    ap.add_argument("--skip-frontend", action="store_true")
    ap.add_argument("--skip-tests", action="store_true", help="install and build only")
    ap.add_argument("--start", action="store_true", help="start the API and web app after the checks pass")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    print(f"Python {sys.version.split()[0]} on {sys.platform}")
    if sys.version_info < (3, 11):
        print("FAIL: Python 3.11 or newer is required."); return 2
    if a.ml and sys.version_info >= (3, 13):
        print("FAIL: --ml needs Python 3.12 (torch 2.2.2 has no wheels for 3.13). Use Python 3.12, or run without --ml."); return 2
    dry = a.dry_run

    # ---- backend
    if not (BACKEND / ".venv").exists() or dry:
        if not run("backend: create virtualenv", [sys.executable, "-m", "venv", str(BACKEND / ".venv")], BACKEND, dry):
            summary(); return 1
    py = str(venv_python())
    pip = [py, "-m", "pip", "install", "--disable-pip-version-check", "-q"]
    if not run("backend: pip install (core)", pip + ["-r", "requirements.txt"], BACKEND, dry):
        summary(); return 1
    if a.ml and not run("backend: pip install (ML extras)", pip + ["-r", "requirements.txt", "-r", "requirements-ml.txt"], BACKEND, dry):
        summary(); return 1

    if a.c2pa and not run("backend: pip install (C2PA validator)", pip + ["-r", "requirements-c2pa.txt"], BACKEND, dry):
        summary(); return 1

    env_file = BACKEND / ".env"
    if not env_file.exists() and not dry:
        text = (BACKEND / ".env.example").read_text(encoding="utf-8")
        text = text.replace("dev-only-secret-change-me", secrets.token_hex(32))
        if a.ml:
            text = text.replace("PRELOAD_MODELS=false", "PRELOAD_MODELS=true")
        env_file.write_text(text, encoding="utf-8")
        print("\nCreated backend/.env with a fresh random JWT secret (never commit this file).")

    if not run("backend: compile all", [py, "-m", "compileall", "-q", "app", "tests", "eval", "scripts" if (BACKEND / "scripts").exists() else "app"], BACKEND, dry):
        summary(); return 1
    if not a.skip_tests and not run("backend: tests (pytest)", [py, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"], BACKEND, dry, env={"ENV": "test"}, tail=40):
        summary(); return 1
    if not run("backend: app imports + health route", [py, "-c",
        "from fastapi.testclient import TestClient; from app.main import app; "
        "c=TestClient(app); r=c.get('/health'); print(r.status_code, r.json()); assert r.status_code==200"],
        BACKEND, dry, env={"ENV": "test"}):
        summary(); return 1

    # ---- frontend
    if not a.skip_frontend:
        npm = shutil.which("npm") or ("npm.cmd" if IS_WIN else "npm")
        if not dry and not shutil.which("node"):
            results.append(("frontend: node present", "FAIL", 0.0, "Node 20+ is not installed")); print("FAIL: Node 20+ is required for the frontend."); summary(); return 1
        steps = [("frontend: npm install", [npm, "install", "--no-audit", "--no-fund"])]
        if not a.skip_tests:
            steps.append(("frontend: unit tests (vitest)", [npm, "run", "test"]))
        steps.append(("frontend: type-check + build", [npm, "run", "build"]))
        for label, cmd in steps:
            if not run(label, cmd, FRONTEND, dry, tail=40):
                summary(); return 1
        lock = ROOT / "scripts" / "check_lock_sync.py"
        run("frontend: lock file in sync", [sys.executable, str(lock)], ROOT, dry)

    summary()
    ok = all(r[1] in ("PASS", "SKIP (dry run)") for r in results)
    if dry:
        print("Dry run only: nothing was installed or executed.")
    else:
        print("ALL CHECKS PASSED. You have a clean, working install." if ok else "Some checks failed - see the output above.")
    if ok and a.start and not dry:
        print("\nStarting API on http://localhost:8000 and web app on http://localhost:5173  (Ctrl+C stops both)")
        api = subprocess.Popen([py, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"], cwd=BACKEND)
        web = subprocess.Popen([shutil.which("npm") or "npm", "run", "dev"], cwd=FRONTEND)
        try:
            api.wait()
        except KeyboardInterrupt:
            pass
        finally:
            for p in (api, web):
                p.terminate()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
