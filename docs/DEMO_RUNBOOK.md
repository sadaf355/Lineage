# Demo runbook

Everything below is a checklist to run, not a record of what has been run. Tick items off as you do them.

## A. Setup (once, with internet)
1. `./scripts/demo.sh` builds the stack, downloads and caches the models, starts it, seeds "Riya's Case" and opens the app.
   Login: `demo@lineage.app` / `demo-access` (local demo account only; never expose this stack to the internet).
2. Host `backend/demo_assets/trace_page/` on a public URL (see `backend/demo_assets/README.md`). Write the URL here: `______________`
3. `python scripts/demo_check.py --trace-url <that URL>` must finish with **0 failed** and you must have read every WARN. It also checks
   security headers, the CSRF guard, that a renamed executable is refused, signing and verifying a manifest, that the report job
   finishes without a worker, and that the BSA certificate is marked draft.
3b. `python scripts/trial_feature_match.py --image <your demo photo> --negatives <folder of unrelated photos>`. Keep
   `TRACE_FEATURE_MATCH_ENABLED=true` only if it says RESULT: good. Demo the edits it shows as `match`; do not promise crops of 50% or less.
4. For a stronger demo, replace the synthetic samples with your own **consented** images (never a real victim's content).

## B. Offline path (Wi-Fi off)
1. After step A, stop the stack, then turn Wi-Fi off.
2. `./scripts/demo.sh --offline`. It first runs `offline_check.py`, which forces Hugging Face offline and loads every model from the
   cache, so a missing model fails in rehearsal, not on stage. The app shows an amber "Offline demo mode" banner if the real model is not loaded.
3. Run `python scripts/demo_check.py` (no `--trace-url`: tracing needs the internet, so skip it offline and show the saved case instead).
4. Offline limits to say out loud: no source tracing, no web discovery, no LLM summary. The case, detection, fingerprint, evidence, integrity and report all work.

## C. Fixed click path
Dashboard (point at the Detector evaluation panel) → Investigations → Riya's Case → Detection (upload `sample_case_image.jpg`, run detection) → Fingerprint → Add Source → paste the trace URL → review the pending match → **Accept** → Lineage Map → Evidence (verify integrity) → Report (generate).
Reject variant: repeat Add Source, trace the same URL, press **Dismiss and delete capture**.

## D. Scripts (practise each three times, with a timer)
Use the cue-sheet timer: `python scripts/rehearsal_timer.py 5min` (also `2min`, `projector`). It logs each run and
`python scripts/rehearsal_timer.py --status` shows which scripts are READY (three runs in a row within 10% of the budget).
**5 minutes**
- 0:00 Problem in one sentence: a harmful image spreads and nobody can show where it came from or that it was altered.
- 0:30 Dashboard and the Detector evaluation panel: "here is what the detector gets right and where it fails" (read the weakest condition aloud).
- 1:15 Upload and detect. Say it is a likelihood, not proof.
- 2:00 Fingerprint, then trace the URL, show the match, accept it.
- 3:15 Lineage Map, evidence integrity, then sign and verify the manifest (Evidence Locker).
- 4:00 Report. Close with the limits slide: what LINEAGE refuses to claim.

**2 minutes**
- Upload + detect (0:30), trace + accept (0:50), integrity + report (0:40). Skip the dashboard. One sentence on limits at the end.

**"Projector fails" (no screen, 2 minutes)**
- Talk through the click path from memory using the printed one-page click path and the screenshots in the deck.
- Have the backup recording on a phone or USB stick, ready to hand over.

## E. Record the backup
Screen-record one clean 5-minute run (OBS or the OS recorder) at 1080p with the offline stack, narrate as you would live, and keep the file on the laptop, a USB stick and cloud storage: `______________`

## F. Before you go on
- [ ] `demo_check.py` shows 0 failed, and you have read every WARN
- [ ] `trial_feature_match.py` says RESULT: good on the exact image you will upload (or tracing is set to hash-only)
- [ ] `offline_check.py` shows 0 failed with Wi-Fi off (if you will demo offline)
- [ ] `rehearsal_timer.py --status` shows READY for every script you plan to give
- [ ] Battery charged, laptop on power, notifications off, browser zoom 100%
- [ ] Trace URL still loads in a browser
- [ ] Backup recording opens
- [ ] You have said, in each script, that scores are probabilities and the tool does not make accusations
