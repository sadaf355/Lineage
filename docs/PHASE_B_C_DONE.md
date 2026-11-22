# Phase B and Phase C: what is built, what it proves, and what is still yours

## Phase B: measured detection (tooling complete; the measurement itself needs your data)

**Built and tested**
- **Leakage-safe protocol** (`app/services/eval_stats.py`, `eval_harness.summarize_protocol`). Originals are split into a calibration
  and a test share; every degraded copy follows its original; the threshold is chosen on calibration only; everything reported
  comes from the held-out test split. All models are scored on the same test images.
- **Honest uncertainty.** 95% intervals from a bootstrap over original images, never narrower than a Wilson interval that counts
  each original once. (A first version let a small error-free sample report "100%, CI 100 to 100"; the Wilson floor fixes that and
  has a regression test.)
- **Near-duplicate check** (`eval/check_leakage.py`): a 256-bit structure hash plus a colour layout, both must agree. Duplicates
  share one split; a cluster that mixes real and fake images stops the run.
- **Smoke-test stamp by originals, not files.** Degraded copies are not new images, so a report needs about 200 test originals
  before it stops being stamped a smoke test (slide, model card and in-app panel all use the same rule).
- **Self-test** (`eval/selftest.py`, runs first in `phase_b.sh`): builds toy data, runs the real degradation script and the
  protocol, checks no leakage, calibration-only thresholds, reproducible splits, intervals that bracket the estimate.
  **Its numbers are not a detector result.**
- **In-app panel** shows "Smoke test, not a result" instead of a green "Measured" badge for small sets, the held-out test count,
  and the intervals.
- `eval/DATASETS.md`: a checklist for choosing and documenting data. It lists no dataset as approved, because I cannot verify
  licences for you.

**Still yours**
1. Pick datasets, read each licence yourself, fill `eval/sources.csv`, stage images in `eval/incoming/`.
2. `cd backend && bash eval/phase_b.sh` (needs the detector models; `model_info.py` needs the internet).
3. Write your own reading of the weak spots in `docs/DETECTOR_MODEL_CARD.md`. Do not quote a number while the report is stamped smoke test.

## Phase C: demo hardening (tooling complete; the rehearsals are yours)

**Built and tested**
- `scripts/trial_feature_match.py`: edits YOUR demo photo (crops, resize, JPEG, rotation, mirror, brightness, pasted bar,
  screenshot) and checks the tracer's matcher on each, plus unrelated images for false positives. Says what to keep on and what not
  to promise. Run on the bundled sample: 11 of 11 expected edits matched, 0 of 3 unrelated images matched.
- `scripts/demo_check.py` now also checks security headers, the CSRF guard, that a renamed executable is refused, that a manifest
  signs and verifies, that the report job finishes without a worker, and that the BSA certificate is marked draft. Its logic is tested
  against a stand-in server (it cannot be tested against your real stack from here).
- `backend/offline_check.py`, run automatically by `demo.sh --offline`: forces Hugging Face offline and loads every model from the
  cache, checks ffmpeg and OpenCV, and confirms every bundled demo asset passes upload content checks (verified here: all pass, a
  renamed executable is refused).
- `scripts/rehearsal_timer.py`: cue sheets for the 5-minute, 2-minute and "projector fails" scripts, a run log, and a READY rule
  (three runs in a row within 10% of budget).
- `docs/DEMO_RUNBOOK.md` updated with every new command and checklist item.

**Still yours (cannot be done from a build environment)**
1. Run `./scripts/demo.sh`, then `python scripts/demo_check.py --trace-url <your hosted page>` against the real stack.
2. Run `trial_feature_match.py` on the exact photo you will upload, with a folder of unrelated photos as negatives.
3. Cache the models, turn Wi-Fi off, run `./scripts/demo.sh --offline`.
4. Do each rehearsal script three times with the timer, record the backup video, and store it in three places.
