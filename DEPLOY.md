# Running and deploying LINEAGE

## 0. Before anything else
Run the preflight script on your machine. It installs dependencies, runs the backend tests, the frontend
tests and the production build, and checks that no secrets are tracked by git.

    ./scripts/preflight.sh

Do not deploy until it passes. Push to GitHub as well and confirm the CI workflow is green.

## 1. Run locally (development)
Backend:

    cd backend
    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env
    uvicorn app.main:app --reload

Frontend (second terminal):

    cd frontend
    cp .env.example .env
    npm install && npm run dev

The first backend start downloads the ML models, so it needs internet and can take several minutes.

## 2. Deploy on a single server (Docker + HTTPS)
Needs a server with Docker, and a domain with two DNS records (`app.<domain>` and `api.<domain>`)
pointing at the server. Two hostnames under one domain are required so the refresh cookie stays same-site.

    cp deploy/.env.production.example deploy/.env      # fill in every value
    docker compose --env-file deploy/.env -f deploy/docker-compose.prod.yml up -d --build

Caddy obtains HTTPS certificates automatically. Only ports 80 and 443 are published.
The first start downloads ML models into the persistent volume; allow a few minutes before the API is healthy.

## 3. After deploying
- Open `https://app.<domain>`, register, upload a test image, verify integrity, generate a report.
- Check `https://api.<domain>/health` and `/security/status`.
- Back up the `lineage_data` volume, the Postgres volume, and **FILE_ENCRYPTION_KEY** together.
  Losing the key means stored evidence can never be decrypted.

## Detector configuration and evaluation
`DETECTOR_MODEL_ID` selects the one primary model used everywhere (detection, `/health`, evaluation). Optionally set
`DETECTOR_SECOND_MODEL_ID` to enable the two-model ensemble. Run `backend/eval/run_eval.py` and commit
`backend/eval/results/` so the in-app Detector panel shows measured numbers (see `docs/PHASE1_2.md`).
For a local rehearsal use `./scripts/demo.sh`; that stack is http-only and must not be exposed publicly.

## Known limits (be honest with users)
- Detection results are probabilities, not proof. New generators can evade the detector.
- Tracing works on public pages and user-submitted links; it cannot see private or encrypted apps.
- The creator's IP cannot be read from a file. Hosting footprints describe the server, not the creator.
- Secrets-manager key storage is planned; the key currently comes from an environment variable.
- Neo4j is disabled in the production template (the app falls back to its in-memory graph).
- The deployment files in `deploy/` are templates that have not been run by the author of this package.
  Expect to adjust them on first deploy.
