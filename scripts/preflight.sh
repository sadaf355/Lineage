#!/usr/bin/env bash
# Run this on your own machine (needs Python 3.12+, Node 20+, internet) BEFORE deploying.
# Every step must pass. Stop and fix the first failure.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "== 1/5 Backend: install =="
cd "$ROOT/backend"
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

echo "== 2/5 Backend: compile + tests =="
python -m compileall -q app tests eval prefetch_models.py
pytest -q

echo "== 3/5 Frontend: install =="
cd "$ROOT/frontend"
# Test tools are now devDependencies. The first install regenerates package-lock.json;
# commit that file, after which "npm ci" can be used instead.
npm install --no-audit --no-fund
python3 "$ROOT/scripts/check_lock_sync.py" || echo "NOTE: commit the regenerated frontend/package-lock.json, then CI can use npm ci."

echo "== 4/5 Frontend: unit tests + production build =="
npm run test
npm run build

echo "== Shell scripts: syntax =="
bash -n "$ROOT/scripts/demo.sh"
python3 -m py_compile "$ROOT/scripts/demo_check.py"

echo "== 5/5 Secrets check =="
cd "$ROOT"
if git rev-parse --git-dir >/dev/null 2>&1; then
  if git ls-files | grep -E '(^|/)(\.env$|data/|\.file_encryption_key)'; then
    echo "FAIL: secrets or data are tracked by git (listed above)"; exit 1
  fi
fi
echo "PREFLIGHT PASSED. (Playwright e2e: run 'npm run test:e2e' in frontend/ after 'npx playwright install chromium'.)"
