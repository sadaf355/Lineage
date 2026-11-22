# Phase D / E / F — what was built, what was measured, what was not done

Status key: **Verified** = executed here and passed. **Written** = code exists, not executed. **Not done** = absent.

## Phase D — UI polish
| Item | Status |
|---|---|
| `Reveal` / `Stagger` / `AnimatedNumber` on every app screen; `AnimatePresence` page transitions | Written (syntax-checked; screens wrapped by an AST script, so review layouts visually). Landing/Login keep their own entrance animations. |
| Ctrl/Cmd+K command palette (real investigations listed) | Written |
| Detection scanner driven by `analysisStage` and request flags, ring gauge, sequenced evidence reveal | Written. No fake progress: the scanner is indeterminate. |
| Case-wide progress rail (`lib/caseProgress.ts`) | Pure logic **Verified** (Node). Component Written. |
| Animated Fingerprint page drawing the real pHash/dHash/aHash bits | Pure logic **Verified**. Component Written. |
| Lineage Map node dimming + detail panel, keyboard-operable nodes | Logic **Verified**. UI Written. |
| axe accessibility pass | **Not run.** `tests/e2e/a11y.spec.ts` (mocked API) is written. What *was* done: contrast ratios computed and failing text tokens darkened; ~30 unnamed controls labelled; click-only elements made keyboard-operable. Automated axe finds only part of real issues; a manual screen-reader and keyboard pass is still required. |

Needs `npm install` (refreshes `package-lock.json` for `@axe-core/playwright`), then `npm run build`, `npm test`, `npm run test:e2e`.

## Phase E — Evidence and legal depth
See `EVIDENCE_INTEGRITY.md` and `LEGAL_REVIEW.md`. Ed25519 manifest + optional RFC 3161: 16 unit tests **Verified**; request DER **Verified** against `openssl ts -query`; timestamp reply parsing tested only on a synthetic reply, **not against a real TSA**. Capture sweep: decision logic **Verified**; S3 listing and DB queries Written. Lawyer review: **Not done** (cannot be); a package for counsel is provided and the app cannot claim a review that has not happened.

## Phase F
| Item | Status |
|---|---|
| Crop-robust matching in the main pipeline | Implemented (`services/feature_match.py`, wired into `source_tracing.py`, setting `TRACE_FEATURE_MATCH_ENABLED`). 9 unit tests + the existing tracing security tests **Verified** locally. Measured numbers below. |
| Load test with recorded numbers | Tool written and its harness verified against a stub server (`scripts/load_test.py`). **No API numbers exist**: the API could not be started here. Service-level benchmarks below are real but are not an API load test. |
| Coverage gate | Backend gate (70%) already existed in CI; **not re-measured**. Frontend gate: **Not done** (needs `@vitest/coverage-v8` added and a lock refresh). |
| Hindi and regional-language reports | **Not done.** Needs bundled Devanagari/regional fonts and a text-shaping path (ReportLab does not shape complex scripts), plus reviewed translations of legal wording. |
| Licensed platform discovery | **Not done.** Needs a provider contract; nothing was built that scrapes platforms. |
| Blender `.glb` hero | Loader Written (`ForensicScene.tsx`, `HERO_ASSET.md`); **no asset ships**; untested against a real file. |

## Crop-robust matching: measured results
Method: ORB features, ratio test, RANSAC partial-affine fit; a match needs ≥30 inliers, ≥35% inlier ratio and a matched region ≥8% of the image; mirrored candidates are also tried. Reproduce: `python scripts/eval_crop_matching.py <folder>`.

Real photographs (19 usable images bundled with scikit-image/matplotlib; `results/crop_matching_19_photos.json`):
| Transform | Recall |
|---|---|
| crop 90% / 75% / 60% / 50% / 35% (3 random positions each) | 96.5% / 100% / 82.5% / 49.1% / 7.0% |
| resize 50% / rotate 8° / mirror / JPEG q35 | 78.9% / 94.7% / 100% / 100% |
| **Different-image pairs wrongly matched** | **0 of 171** |

Caveats you must keep when quoting these:
* **Small sample.** 19 images, 171 pairs. Zero errors in 171 trials is consistent with a true rate up to about 1.7% (95% bound). This is not a measured error rate for real-world pages.
* Small crops (≤50%) are often missed, and below ~35% many images have too few features to judge; the matcher reports `insufficient_features` rather than a verdict. Recall at 50% crop is about one in two.
* 50% downscaling missed 21% of these photos (some had little texture).
* On a second set of 44 hazard-sign pictograms, 34 of 780 different pairs (4.4%) matched (`results/crop_matching_44_pictograms.json`). Inspection showed these share a diamond border template or are near-identical icons, so it reflects template similarity, but it shows the matcher can match images that merely share large structure. Logos, templates and repeated patterns are a known failure mode.
* A match means "contains a region of the reference", not "same source" or "same person". The investigator still confirms every trace; a feature-matched result is accepted through its own signed `orb+ransac;` method label, and the original two-agreeing-hashes rule is unchanged.
* The reported "similarity" for a feature match is a confidence band (85–100) from the inlier count, not a percentage, and is not comparable to hash similarity.
* An earlier attempt at sliding-window hashing was measured (12% recall at 75% crop, ~10% false matches) and removed.

## Service benchmarks (1 vCPU Xeon 2.1 GHz, Python 3.12; `results/bench_services_1cpu.json`)
| Operation | Median |
|---|---|
| Build + sign manifest, 100 / 1,000 / 10,000 entries | 0.5 ms / 4.1 ms / 46 ms (10,000 entries = 1.8 MB envelope) |
| Verify manifest, same sizes | 0.6 ms / 3.9 ms / 39 ms |
| Feature extraction, 1280×960 image | 11 ms |
| Match one candidate against one reference (no mirror) | 6–7 ms |
| Worst case per candidate image incl. mirror re-extraction | ~45 ms |

Tracing is bounded by `TRACE_MAX_IMAGES` (12), up to 5 case images and `TRACE_MAX_SECONDS`, so the added worst case is roughly 12 × 5 × 45 ms ≈ 2.7 s of CPU per trace on this machine. Measured in isolation; not measured under concurrent API load.

## To run the real load test
```bash
python scripts/load_test.py --base http://127.0.0.1:8000 --email demo@lineage.app --password '…' --users 20 --duration 60 --json docs/results/load_YYYYMMDD.json
```
Record commit, machine, database, worker count and Redis on/off beside the result. Do not run it against production.
