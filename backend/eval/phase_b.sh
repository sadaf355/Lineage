#!/usr/bin/env bash
# Phase B in one command, after you have staged licensed images in eval/incoming/<source>/{real,fake}/
# and described each source (url, licence, fake kind) in eval/sources.csv.
#
#   cd backend && bash eval/phase_b.sh
#
# Set DETECTOR_SECOND_MODEL_ID first to also evaluate a second model and the ensemble.
set -euo pipefail
cd "$(dirname "$0")/.."
MODELS="primary"; [ -n "${DETECTOR_SECOND_MODEL_ID:-}" ] && MODELS="primary second ensemble"
python eval/selftest.py          # proves the evaluation tooling works (toy data; not a result)
python eval/build_manifest.py
python eval/build_degraded.py --manifest eval/manifest.csv
python eval/check_leakage.py --apply   # near-duplicates share a split; mixed real/fake duplicates stop the run
python eval/run_eval.py --check-only
python eval/model_info.py || echo "model_info.py needs internet; fill licence/training data by hand from the Hugging Face page if this failed."
python eval/run_eval.py --models $MODELS
python eval/analyze_failures.py
python eval/fill_model_card.py
python eval/make_slide.py
echo "Done. Review docs/DETECTOR_MODEL_CARD.md, write your own reading of the limitations, and commit eval/results/."
