# Detector evaluation set

Goal: a measured, reproducible accuracy table for the deck, with weak spots stated.

## 1. Gather images (300 to 1000, roughly half real, half fake)
Use public datasets and **read each dataset's licence and terms first**. Some forbid redistribution,
require a signed agreement, or restrict use to research. Keep a record of what you used in the
`source` column and in `docs/DETECTOR_MODEL_CARD.md`. Do not commit the images (they are git-ignored).

Mix more than one source and more than one kind of fake (face swaps, fully generated faces,
fully generated scenes). A set built from one generator mostly measures that generator.
Do not use images of real people who have not consented to this use.

Put files in `eval/images/`.

## 2. Build the manifest
Easiest: stage downloads as `eval/incoming/<source>/real/` and `eval/incoming/<source>/fake/`, copy
`sources.example.csv` to `sources.csv` and write each source's URL, licence and kind of fake (commit this file: it is
your licence record), then run:

    python eval/build_manifest.py

It refuses a source with no licence, skips unreadable files, removes duplicates, and warns about a small, unbalanced or
single-source set. Or write `manifest.csv` by hand (copy `manifest.example.csv`), one row per image:

| column | meaning |
|---|---|
| filename | file inside `eval/images/` |
| label | `real` or `fake` |
| source | dataset or origin name |
| condition | `original` for the files you gathered |

## 3. Add degraded copies
    python eval/build_degraded.py --manifest eval/manifest.csv
Adds `jpeg_q50`, `resize_50`, `crop_80` and `screenshot` copies of every original.

## 4. Check for duplicates, validate, then run
    python eval/selftest.py                # proves the tooling works on toy data (NOT a result)
    python eval/check_leakage.py --apply   # near-duplicate originals share one split; a real+fake duplicate stops the run
    python eval/run_eval.py --check-only
    python eval/run_eval.py --models primary second ensemble
Set `DETECTOR_SECOND_MODEL_ID` first if you want the second model and ensemble (any Hugging Face
image-classification model whose labels include a fake/manipulated class).

### How the numbers are produced (the default `--protocol split`)
1. Originals are split into a **calibration** share (30%) and a **test** share (70%), stratified by label and deterministic for a
   seed. **Every degraded copy follows its original**, and near-duplicates found by `check_leakage.py` share a group, so nothing
   the threshold was tuned on is also tested.
2. The decision threshold is chosen **on the calibration split only** (maximises F1). Each model gets its own.
3. Everything reported (accuracy, precision, recall, F1, ROC-AUC, per-condition rows, the confusion matrix) comes from the **test
   split only**, and every model is scored on the same test images.
4. Each headline rate carries a **95% interval**: a bootstrap over original images, never narrower than a Wilson interval that
   counts each original once. Degraded copies are correlated with their original and are not extra evidence.
5. A report is a **smoke test**, and is stamped that way, until the test split has about 200 original images (roughly 300 in all).
   Degraded copies do not count towards that.

`--protocol fixed` scores everything at one threshold with no held-out data. Use it for a quick look, never for a number you quote.

Results go to `eval/results/latest.json` (shown in the app) and `latest.md` (paste into the deck); `predictions.csv` records each
image's split. Commit `results/`; the app container reads it.

## 5. After the run
    python eval/model_info.py          # licence + declared training data from each Hugging Face model page
    python eval/analyze_failures.py    # where it fails: by source, by condition, worst mistakes, ensemble vs single
    python eval/fill_model_card.py     # writes the measured blocks into docs/DETECTOR_MODEL_CARD.md
    python eval/make_slide.py          # deck slide from the same numbers (stamped SMOKE TEST under 300 images)
`bash eval/phase_b.sh` runs the whole chain.

## Reading the numbers
- Look at the per-condition rows, not only the overall row. A detector that is strong on `original`
  and weak on `screenshot` is not strong on content that has been shared.
- Quote the interval, not just the point: "accuracy 91% (95% CI 86 to 95)". A wide interval means the set is too small to say more.
- `unscored` counts images a model failed to score. They are excluded, not counted as correct.
- Never quote a threshold-tuned number from the calibration split, and never re-run with a new seed until the number looks better.
  If you change the threshold, seed or data, say so.
- A set from one source mostly measures that source. Report per-source rows and say which fake generators are missing.
