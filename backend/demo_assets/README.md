# Demo assets

Everything here is **synthetic**: abstract generated images and a test-pattern clip. No real person
appears in them, so they are safe to bundle, commit and show. Regenerate with `python demo_assets/make_samples.py`.

| File | Use |
|---|---|
| `sample_case_image.jpg` | The case image. Upload this to the demo case. |
| `sample_image_b/c/d.jpg` | Extra uploads, and unrelated images for the "no match" check. |
| `sample_clip.mp4` | 3-second clip to show the video path. |
| `trace_page/` | A tiny page holding a re-compressed copy of the case image plus an unrelated decoy. |

## Limits of synthetic media
- There is no face, so face-embedding steps report "no face". That is correct behaviour, not a bug.
- The detector's score on synthetic art means little. Do not present it as a detection result.
- For a convincing live demo, add your own **consented** images here and point `seed_riya_case.py --media` at them.
  Never use a real victim's content.

## Hosting the trace page (needed for the real URL test)
LINEAGE refuses to fetch private or local addresses on purpose, so the page must be on a **public** URL.
Free options: GitHub Pages (put the `trace_page/` folder in a repo and enable Pages), or Netlify Drop
(drag the folder onto app.netlify.com/drop). Use the address **with a trailing slash**, for example
`https://yourname.github.io/lineage-trace-demo/`. Keep it in `docs/DEMO_RUNBOOK.md` once it works.

Check it end to end with `python scripts/demo_check.py --trace-url <that address>` (see the runbook).
