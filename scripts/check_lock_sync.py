#!/usr/bin/env python3
"""Fail if frontend/package-lock.json does not list every dependency in frontend/package.json.
`npm ci` (and any reproducible build) breaks when they drift. Fix: cd frontend && npm install, then commit the lock."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent / "frontend"
pkg = json.loads((root / "package.json").read_text())
lock = json.loads((root / "package-lock.json").read_text())
want = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
have = lock.get("packages", {}).get("", {})
have = {**have.get("dependencies", {}), **have.get("devDependencies", {})}
missing = sorted(set(want) - set(have))
stale = sorted(n for n in want if n in have and want[n] != have[n])
if missing or stale:
    print("package-lock.json is out of sync with package.json.")
    if missing: print("  missing from lock:", ", ".join(missing))
    if stale: print("  version differs:", ", ".join(stale))
    print("Fix: cd frontend && npm install && commit package-lock.json")
    sys.exit(1)
print("package-lock.json is in sync.")
