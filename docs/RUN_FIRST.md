# Run-first guide and verification record

## The one command
```
python scripts/first_run.py            # install, test, build, PASS/FAIL table
python scripts/first_run.py --start    # then start API :8000 and web app :5173
python scripts/first_run.py --ml       # add the optional ML models (Python 3.12 only)
```
Needs Python 3.11+, Node 20+, internet. It stops at the first failure and prints the failing command and its last lines.

## What changed in this build (vs Lineage-PhaseBC.zip)
1. **Install no longer depends on the ML stack.** `requirements.txt` is the core set (Python 3.11-3.13, loose Pillow/numpy/opencv ranges, `psycopg2-binary>=2.9.10`). The heavy, version-locked ML set moved to `requirements-ml.txt` (Python 3.12 only; torch 2.2.2 has no 3.13 wheel). The earlier single file could not install on Python 3.13 at all.
2. `PRELOAD_MODELS` defaults to `false` in `.env.example` (fast start; the labelled pixel-heuristic fallback is used until the ML extras are installed). `first_run.py --ml` flips it on.
3. `Dockerfile`: `--build-arg INSTALL_ML=false` builds a small image without ML.
4. `scripts/first_run.py` added (cross-platform self-check and launcher).
5. Fixed a wrong assertion in `tests/test_eval_protocol_harness.py` (expected 240 images; the data has 120 per model).

## What was verified in the build environment (no package-registry access)
* Every Python file compiles; an AST check found no unresolved imports between project modules and no undefined names; ruff (F821, F811, syntax) clean.
* **175 tests in 19 test files pass** (manifest, feature matching, evaluation statistics and leakage, capture sweep, geo, knowledge graph, Neo4j service, source-tracing security, threat-model consistency, release hygiene, demo-check, rehearsal timer, phase B/C wiring). These ran against a small stand-in for `pydantic-settings`.
* The detector self-test (`eval/selftest.py`) passes. It uses toy data and is **not** a detector result.
* Alembic migrations and SQLAlchemy models agree on all 22 tables and columns.
* Frontend: no syntax errors and no broken relative imports (TypeScript parse). The remaining compiler messages only come from third-party packages not being installed here.

## What could NOT be verified here (do these on your machine)
* 18 test files need FastAPI, SQLAlchemy or httpx (API, database, upload, consent, report and evidence tests). They have not been executed.
* `npm install`, `tsc -b`, `vite build`, vitest and Playwright/axe have not been executed. `package-lock.json` is still out of sync until your first `npm install`; commit the regenerated file.
* The API has not been started; no load numbers; the real ML models have not been downloaded or run; no real TSA; detector accuracy is unmeasured (`backend/eval/images` is empty).
* If `first_run.py` reports a failure, send the printed last lines; that is the fastest route to a fix.
