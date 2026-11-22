#!/usr/bin/env bash
# One command to a ready demo on a fresh laptop.
#
#   ./scripts/demo.sh             # first run: needs internet once, to build images and download models
#   ./scripts/demo.sh --offline   # later runs: no network; uses cached models and bundled sample media
#   ./scripts/demo.sh --stop      # stop the stack (data and cached models are kept)
#   ./scripts/demo.sh --reset     # stop AND delete the demo database, uploads and cached models
#
# Needs: Docker with the compose plugin, and python3 (only to generate secrets). Local use only: http, no hardening.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ENV_FILE="deploy/.env.demo"
COMPOSE=(docker compose -f docker-compose.demo.yml --env-file "$ENV_FILE")
OFFLINE=false
APP_URL="http://localhost:5173"
API_URL="http://localhost:8000"

say()  { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
fail() { printf '\n\033[31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

for arg in "$@"; do
  case "$arg" in
    --offline) OFFLINE=true ;;
    --stop)  [ -f "$ENV_FILE" ] || fail "Nothing to stop (no $ENV_FILE)."; "${COMPOSE[@]}" down; exit 0 ;;
    --reset) [ -f "$ENV_FILE" ] || fail "Nothing to reset (no $ENV_FILE)."
             read -r -p "Delete the demo database, uploads and cached models? [y/N] " yn
             [ "$yn" = "y" ] && "${COMPOSE[@]}" down -v; exit 0 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) fail "Unknown option: $arg" ;;
  esac
done

say "1/6 Checking tools"
command -v docker >/dev/null || fail "Docker is not installed or not on PATH."
docker compose version >/dev/null 2>&1 || fail "The Docker compose plugin is missing (need 'docker compose')."
docker info >/dev/null 2>&1 || fail "Docker is installed but not running. Start Docker and retry."
command -v python3 >/dev/null || fail "python3 is needed once, to generate secrets."

say "2/6 Preparing secrets ($ENV_FILE)"
if [ ! -f "$ENV_FILE" ]; then
  JWT="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  # A Fernet key is 32 random bytes, url-safe base64 encoded.
  FKEY="$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  umask 077
  { echo "JWT_SECRET_KEY=$JWT"; echo "FILE_ENCRYPTION_KEY=$FKEY"; echo "OFFLINE_DEMO_MODE=false"; } > "$ENV_FILE"
  echo "Generated new secrets. Keep $ENV_FILE: losing FILE_ENCRYPTION_KEY makes stored demo uploads unreadable."
else
  echo "Reusing existing $ENV_FILE"
fi
# Offline flag is applied per run without rewriting the secrets file.
export OFFLINE_DEMO_MODE="$OFFLINE"

say "3/6 Building images"
# Offline runs only work if the images were built online once before (Docker reuses the cached layers).
"${COMPOSE[@]}" build || fail "Build failed. If you are offline, run ./scripts/demo.sh once with internet first."

if [ "$OFFLINE" = false ]; then
  say "4/6 Downloading and caching ML models (first run can take several minutes)"
  "${COMPOSE[@]}" run --rm --no-deps -e OFFLINE_DEMO_MODE=false api python prefetch_models.py \
    || echo "WARNING: model prefetch failed. The demo will fall back to the labelled pixel heuristic; the in-app banner will say so."
else
  say "4/6 Offline mode: skipping model download (using the cache from a previous online run)"
  # Fail here, in rehearsal, rather than on stage: forces Hugging Face offline and loads every model from the cache.
  "${COMPOSE[@]}" run --rm --no-deps -e OFFLINE_DEMO_MODE=true api python offline_check.py \
    || fail "Offline check failed. Run ./scripts/demo.sh once WITH internet to cache the models, then retry."
fi

say "5/6 Starting the stack"
"${COMPOSE[@]}" up -d
printf 'Waiting for the API'
for i in $(seq 1 120); do
  if curl -fsS "$API_URL/health" >/dev/null 2>&1; then echo " ready."; break; fi
  printf '.'; sleep 5
  [ "$i" = 120 ] && { echo; "${COMPOSE[@]}" logs --tail 40 api; fail "API did not become healthy within 10 minutes."; }
done
echo "Detector status: $(curl -fsS "$API_URL/health" | python3 -c 'import json,sys; d=json.load(sys.stdin)["detector"]; print("model loaded" if d["loaded"] else "MODEL NOT LOADED (fallback heuristic will be used)")')"

say "6/6 Seeding the demo case"
"${COMPOSE[@]}" exec -T api python seed_riya_case.py --media demo_assets/sample_case_image.jpg \
  || echo "WARNING: seeding failed; you can still register a fresh account in the app."

cat <<MSG

Demo ready.
  App:      $APP_URL
  Login:    demo@lineage.app / demo-access     (local demo account, created by the seed script)
  API docs: $API_URL/docs
  Runbook:  docs/DEMO_RUNBOOK.md
Sample media is synthetic (backend/demo_assets). Stop with: ./scripts/demo.sh --stop
MSG

if command -v xdg-open >/dev/null 2>&1; then xdg-open "$APP_URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then open "$APP_URL" || true
elif command -v start >/dev/null 2>&1; then start "$APP_URL" || true
fi
