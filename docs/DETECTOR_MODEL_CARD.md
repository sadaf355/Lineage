# Detector model card

<!-- BEGIN:auto:status -->
Status: **results not yet measured.** The marked blocks below are filled in by `backend/eval/fill_model_card.py`
after you run the evaluation (`backend/eval/phase_b.sh`); nothing here is a claim until that has happened. Do not
present this detector's accuracy anywhere (deck, README, UI) until it has.
<!-- END:auto:status -->

## 1. What the detector is
LINEAGE does not train its own deepfake classifier. It runs pretrained image classifiers from Hugging Face and
reports a **manipulation likelihood (0 to 100)**, never a verdict.

| Role | Setting | Default |
|---|---|---|
| Primary detector | `DETECTOR_MODEL_ID` | `dima806/deepfake_vs_real_image_detection` |
| Second detector (optional) | `DETECTOR_SECOND_MODEL_ID` | unset (no ensemble) |
| Ensemble | automatic when a second model is set | mean of the scores the models produced |
| Fallback | automatic if the model cannot load or score | pixel heuristic, labelled `fallback` in the UI and report |

Video is scored on up to `DETECTOR_VIDEO_FRAME_COUNT` sampled frames and averaged. The app shows which model
produced each score. The evaluation uses the same model ids and the same score-to-label rule as the app.

Licence and declared training data, read from each model's Hugging Face metadata by `eval/model_info.py`:

<!-- BEGIN:auto:model-info -->
Not filled in yet. Run `python eval/model_info.py` (needs internet), then `python eval/fill_model_card.py`.
<!-- END:auto:model-info -->

Still to do by hand: open each Hugging Face page, read the stated limitations and intended use, and summarise
them in section 6. Do not copy claims you have not read.

## 2. Evaluation data
Filled in from your manifest and `backend/eval/sources.csv` (`backend/eval/README.md`).

<!-- BEGIN:auto:data -->
- Images: ___ real, ___ fake
- Sources and their licences: ___ (one line per dataset, with link)
- Kinds of fake covered: ___ (face swap / fully generated face / fully generated scene / other)
- Conditions: original, JPEG quality 50, resized to 50%, 80% centre crop, screenshot-style re-encode
- Decision threshold: 50% (`DETECTOR_EVAL_THRESHOLD`), not tuned on this set
<!-- END:auto:data -->

## 3. Results
Pasted from `backend/eval/results/latest.md` by `fill_model_card.py`: one table per model (primary, second, ensemble).

<!-- BEGIN:auto:results -->
No results yet.
<!-- END:auto:results -->

## 4. Intended use
- A triage signal that tells an investigator which media deserves a closer look.
- One input among several (hashes, source tracing, provenance), shown with its uncertainty.

## 5. Not intended for
- Proving that media is authentic or fake. A likelihood is not proof.
- Accusing a person, or making any decision about a person, from the score alone.
- Audio (no audio deepfake model is configured by default) and non-face content the models were not tested on.

## 6. Known failure modes
The list below is what is expected from how this class of detector works. The measured section after it is computed
from your own run (`eval/analyze_failures.py`) and is what you should quote.
- **New generators.** Detectors trained on older generators often miss newer ones. Expect false negatives.
- **Heavy crops and very low resolution.** Less signal reaches the model. See the crop and resize rows.
- **Re-compression and screenshots.** Content shared through messaging apps loses the traces detectors rely on. See the JPEG and screenshot rows.
- **Real photos that look manipulated.** Heavy retouching, filters and beauty modes can raise the score on genuine images (false positives).
- **Dataset bias.** Performance on this set says little about faces, skin tones, lighting or cameras that are rare in it.
- **Fallback is not a classifier.** When the real model is unavailable the heuristic is used and labelled as such. Treat that score as nearly meaningless.

### Measured failure modes and single-versus-ensemble comparison

<!-- BEGIN:auto:failure-modes -->
No results yet.
<!-- END:auto:failure-modes -->

### Our reading of the measurements
___ (write this yourself after reading the tables: which condition hurts most, which source is hardest, whether the
ensemble helps, and what you would not trust this detector with).

## 7. How to reproduce
    cd backend
    # stage licensed images in eval/incoming/<source>/{real,fake}/ and describe each source in eval/sources.csv
    bash eval/phase_b.sh          # manifest -> degraded copies -> eval -> failure analysis -> this card -> slide
Or step by step:
    python eval/build_manifest.py
    python eval/build_degraded.py --manifest eval/manifest.csv
    python eval/run_eval.py --check-only
    python eval/model_info.py
    python eval/run_eval.py --models primary second ensemble
    python eval/analyze_failures.py
    python eval/fill_model_card.py
    python eval/make_slide.py
Results are saved to `backend/eval/results/latest.json` (shown in the app under Settings, Detector, and compactly on the Dashboard), `predictions.csv`, `failure_modes.md` and `detector_slide.pptx`.
