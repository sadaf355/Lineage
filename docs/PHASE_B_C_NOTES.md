# Phase B and C: what is done and what you still have to do

## Done in code (tested)
- Upload content sniffing, consent for LLM and reverse search, audit-action registry fix, consent revocation fix.
- `pip-audit` / `npm audit` / Dependabot / 70% coverage gate in CI.
- `docs/THREAT_MODEL.md` plus `tests/test_threat_model.py`, which fails if a reference goes stale.
- Phase B tooling in `backend/eval/` (manifest builder, model info, failure analysis, model-card filler, slide builder).
- Frontend: consent toggle for external language-model use (Copilot and Report screens).

## Still yours (needs data or internet this build did not have)
1. Collect licensed real and fake images into `backend/eval/incoming/<source>/{real,fake}/` and fill `backend/eval/sources.csv`.
2. `cd backend && bash eval/phase_b.sh` (needs the detector models and, for `model_info.py`, huggingface.co).
3. Read each model's Hugging Face page and write your own reading of the limitations in `docs/DETECTOR_MODEL_CARD.md`.
4. Add `eval/results/detector_slide.pptx` (or its table) to the deck. Do not quote numbers from fewer than 300 images.
5. Before the demo run: `python -m app.services.upload_sniff <your demo files>` from `backend/`.
6. Review the dated ML-stack audit exceptions in `scripts/audit_python.py` before 2026-12-31.
