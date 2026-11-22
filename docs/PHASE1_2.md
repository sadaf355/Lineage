# Phases 1 and 2: measured credibility and demo readiness

## Added (Phase 1)
- `backend/eval/`: manifest format, `build_degraded.py` (JPEG q50, 50% resize, 80% crop, screenshot copies), `run_eval.py` (validates, scores, writes `results/latest.json` and `latest.md`).
- `app/services/eval_harness.py` and an extended `evaluate_binary_predictions`: precision, recall, F1, accuracy, ROC-AUC, confusion matrix, per condition, per model. Images a model cannot score are counted as `unscored`, never as correct.
- `GET /detection/evaluation/latest`, a **Detector evaluation** panel (Settings, Detector; compact copy on the Dashboard).
- Ensemble responses now list the per-model mean, so each score is attributed to its model.
- `docs/DETECTOR_MODEL_CARD.md`, a template with no invented numbers.

## Fixed along the way
- The single-model path ran `prithivMLmods/...` (hard-coded) while the config, the ensemble and the evaluation used `DETECTOR_MODEL_ID`, and `/health` reported the hard-coded one. All paths now use `DETECTOR_MODEL_ID`.
- The ensemble rebuilt its Hugging Face pipeline on every frame. Pipelines are now cached.

## Added (Phase 2)
- `docker-compose.demo.yml` and `scripts/demo.sh` (`--offline`, `--stop`, `--reset`): secrets, build, model prefetch, start, wait for health, seed, open.
- `backend/prefetch_models.py`, `OFFLINE_DEMO_MODE`, and an amber banner in the app when the real model is not loaded or the server is offline.
- `backend/demo_assets/`: synthetic sample images and clip, plus a trace page with a re-compressed copy of the case image and a decoy.
- `scripts/demo_check.py`: API-level end-to-end check, including trace then accept, tamper refusal, trace then reject, and private-URL refusal.
- `docs/DEMO_RUNBOOK.md`: click path, 5-minute, 2-minute and projector-fails scripts, recording checklist.

## Not done, because it cannot be done from here
- No dataset was downloaded and no model was run, so **there are no accuracy numbers yet**. Build the set and run the CLI.
- The trace page is not hosted; it needs a public URL.
- Nothing was rehearsed or recorded.
- Backend tests, the frontend build and Docker were not run in the build environment.
