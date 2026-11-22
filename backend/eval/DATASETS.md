# Choosing and documenting evaluation data

This file is a checklist, not a list of approved datasets. **Licences and terms change, and I cannot verify them for you.**
Read the current terms on each dataset's own page before you download or use it.

## Before you use any dataset
- [ ] Open the dataset's page and read the licence AND any access agreement. Note the exact wording of what it allows.
- [ ] Is use for evaluating a detector and showing aggregate numbers allowed? Some datasets are research-only, some forbid
      redistribution, some require a signed agreement or an institutional email, and some restrict commercial use.
- [ ] Are the people in it consenting subjects (a consented research set) or scraped public figures? Prefer consented sets.
      Do not use images of real people who have not consented, and never use content from a real victim.
- [ ] Do the fakes cover **more than one method** (face swap, fully generated faces, fully generated scenes, edited real photos)?
      A set made with one generator mostly measures that generator.
- [ ] Do the real images come from a **different source** than the fakes? If all fakes are PNG and all reals are JPEG, the
      detector may just be learning the file format. Compare format, size and compression across labels in `manifest.csv`.
- [ ] Does the set contain near-duplicates? Run `python eval/check_leakage.py` (it also catches real/fake pairs of the same face).

## Where to look
Search for datasets on Hugging Face Datasets, Kaggle, and the project pages of published deepfake-detection benchmarks. Use the
search results as a starting list only. For each candidate, fill one row in `eval/sources.csv`: the exact dataset page URL, the
licence as written there, and what kind of fakes it contains. `build_manifest.py` refuses a source with no licence recorded.

## How much is enough
About 300 original images in total (roughly half real, half fake) is the minimum for the report not to be stamped a smoke test;
more is better, and more than one source is better still. Report the number of **originals**, not the number of files.

## What to write in the model card
Which datasets (with URLs and licences), what they do and do not cover, the date of the evaluation, the threshold and how it was
chosen (calibration split), and the weak spots the per-condition and per-source rows show. If a model's training data is not
stated on its page, say "not stated", not a guess.
