#!/usr/bin/env bash
# Build a clean release zip. Refuses if the lock file drifted, and never includes local data, keys,
# caches or build output (a shipped .file_encryption_key would be a shared secret).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/../lineage-release.zip}"
python3 "$ROOT/scripts/check_lock_sync.py"
cd "$ROOT/.."
NAME="$(basename "$ROOT")"
rm -f "$OUT"
zip -qr "$OUT" "$NAME" \
  -x "$NAME/backend/data/*" "$NAME/**/node_modules/*" "$NAME/**/__pycache__/*" "$NAME/**/.pytest_cache/*" \
     "$NAME/**/.venv/*" "$NAME/frontend/dist/*" "$NAME/**/*.tsbuildinfo" "$NAME/**/.env" "$NAME/.git/*" \
     "$NAME/**/.file_encryption_key" "$NAME/**/.manifest_signing_key" "$NAME/**/*.db" "$NAME/**/*.sqlite*"
if unzip -l "$OUT" | grep -qE "file_encryption_key|manifest_signing_key|/data/uploads/"; then
  echo "A secret or data file slipped into the zip; aborting."; rm -f "$OUT"; exit 1
fi
echo "Built $OUT"
