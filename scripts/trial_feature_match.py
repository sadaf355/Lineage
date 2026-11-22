#!/usr/bin/env python3
"""Try crop/rotation-robust matching on YOUR demo image before you present.

    python scripts/trial_feature_match.py --image path/to/your_demo_photo.jpg
    python scripts/trial_feature_match.py --image a.jpg --negatives some_folder_of_other_photos/

It makes edited copies of your image (crops, resize, JPEG, rotation, mirror, brightness, a pasted box) and checks the same
matcher the tracer uses (backend/app/services/feature_match.py). It also checks that UNRELATED images do not match.

Read the result like this:
  * "insufficient features" means the image has too little texture (flat colour, a plain face crop, a logo). The matcher
    says "no evidence" for it, in both directions. Pick a more detailed photo for the demo.
  * Any unrelated image that matches is a FALSE POSITIVE. Set TRACE_FEATURE_MATCH_ENABLED=false for the demo.
  * Misses on 50% crops or smaller are expected (see docs/results/); do not promise them on stage.

Exit code: 0 fine; 1 an unrelated image matched; 2 the image is unsuitable (too few features / unreadable).
Needs: pip install opencv-python-headless pillow numpy   (already in backend/requirements.txt)
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
FM_PATH = ROOT / "backend" / "app" / "services" / "feature_match.py"
DEMO_ASSETS = ROOT / "backend" / "demo_assets"


def load_matcher():
    spec = importlib.util.spec_from_file_location("feature_match_trial", FM_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["feature_match_trial"] = mod   # dataclasses need the module registered before exec
    spec.loader.exec_module(mod)
    return mod


def _crop(img: Image.Image, frac: float, anchor: str = "center") -> Image.Image:
    w, h = img.size
    cw, ch = max(8, int(w * frac)), max(8, int(h * frac))
    left = (w - cw) // 2 if anchor == "center" else 0
    top = (h - ch) // 2 if anchor == "center" else 0
    return img.crop((left, top, left + cw, top + ch))


def _jpeg(img: Image.Image, q: int) -> Image.Image:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=q)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def _pasted_box(img: Image.Image) -> Image.Image:
    out = img.copy()
    d = ImageDraw.Draw(out)
    w, h = out.size
    d.rectangle((int(w * .05), int(h * .80), int(w * .45), int(h * .95)), fill=(15, 15, 15))   # a caption / censor bar
    return out


def _screenshot(img: Image.Image) -> Image.Image:
    w, h = img.size
    canvas = Image.new("RGB", (int(w * 1.3), int(h * 1.5)), (245, 245, 245))
    canvas.paste(img.resize((int(w * 0.9), int(h * 0.9))), (int(w * 0.2), int(h * 0.3)))
    return _jpeg(canvas.resize((canvas.width // 2, canvas.height // 2)), 55)


def variants(img: Image.Image) -> list[tuple[str, Image.Image, bool]]:
    """(name, image, expected_to_match_in_principle). The last column marks edits the matcher is not expected to survive."""
    return [
        ("identical copy", img, True),
        ("JPEG quality 30", _jpeg(img, 30), True),
        ("resize 50%", img.resize((max(8, img.width // 2), max(8, img.height // 2))), True),
        ("crop 90% (centre)", _crop(img, .90), True),
        ("crop 75% (centre)", _crop(img, .75), True),
        ("crop 60% (centre)", _crop(img, .60), True),
        ("crop 50% (corner)", _crop(img, .50, "corner"), False),
        ("crop 35% (centre)", _crop(img, .35), False),
        ("rotate 10 degrees", img.rotate(10, expand=True, fillcolor=(0, 0, 0)), True),
        ("mirror (flip left-right)", img.transpose(Image.Transpose.FLIP_LEFT_RIGHT), True),
        ("brightness +25% / contrast -15%", ImageEnhance.Contrast(ImageEnhance.Brightness(img).enhance(1.25)).enhance(0.85), True),
        ("black bar pasted over 15%", _pasted_box(img), True),
        ("screenshot (border + shrink + JPEG 55)", _screenshot(img), True),
    ]


def negatives_from(args_negatives: str | None, own: Path) -> list[Path]:
    if args_negatives:
        d = Path(args_negatives)
        files = sorted(p for p in (d.iterdir() if d.is_dir() else [d]) if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    else:
        files = sorted(DEMO_ASSETS.glob("sample_image_*.jpg"))
    return [p for p in files if p.resolve() != own.resolve()]


def run(image: Path, negatives: list[Path], fm=None) -> dict:
    fm = fm or load_matcher()
    ref_img = Image.open(image).convert("RGB")
    ref = fm.extract(ref_img)
    out = {"image": str(image), "features": ref.count, "min_features": fm.MIN_FEATURES, "variants": [], "negatives": []}
    if ref.count < fm.MIN_FEATURES:
        out["verdict"] = "insufficient_features"
        return out
    for name, im, expected in variants(ref_img):
        m = fm.best_match(ref, im)
        out["variants"].append({"name": name, "status": m.status, "inliers": m.inliers, "region": m.area_fraction,
                                "mirrored": m.mirrored, "expected": expected})
    for p in negatives:
        try:
            cand = Image.open(p).convert("RGB")
        except Exception:
            continue
        m = fm.best_match(ref, cand)
        out["negatives"].append({"name": p.name, "status": m.status, "inliers": m.inliers})
    false_pos = [n for n in out["negatives"] if n["status"] == "match"]
    out["verdict"] = "false_positive" if false_pos else "ok"
    return out


def render(res: dict) -> str:
    lines = [f"Image: {res['image']}", f"Features found: {res['features']} (need at least {res['min_features']})", ""]
    if res["verdict"] == "insufficient_features":
        lines += ["RESULT: insufficient features. This image has too little texture for the matcher, so it can neither match nor",
                  "        be matched. Choose a more detailed photo (a scene with edges and texture) for the demo."]
        return "\n".join(lines)
    lines += [f"{'Edit':<42}{'Result':<12}{'Inliers':>8}  Note"]
    for v in res["variants"]:
        ok = v["status"] == "match"
        note = ""
        if v["expected"] and not ok:
            note = "MISSED (expected to match)"
        elif not v["expected"] and not ok:
            note = "missed (known limit)"
        elif not v["expected"] and ok:
            note = "matched (bonus)"
        if v["mirrored"]:
            note = (note + " mirrored").strip()
        lines.append(f"{v['name']:<42}{'match' if ok else v['status']:<12}{v['inliers']:>8}  {note}")
    expected = [v for v in res["variants"] if v["expected"]]
    hit = sum(1 for v in expected if v["status"] == "match")
    lines += ["", f"Edits expected to match: {hit} of {len(expected)} matched."]
    if res["negatives"]:
        fp = [n for n in res["negatives"] if n["status"] == "match"]
        lines += [f"Unrelated images that matched: {len(fp)} of {len(res['negatives'])}" + (f"  <-- {', '.join(n['name'] for n in fp)}" if fp else "")]
    else:
        lines += ["No unrelated images were checked (pass --negatives <folder>). A false-positive check is part of the trial."]
    if res["verdict"] == "false_positive":
        lines += ["", "RESULT: FALSE POSITIVE. Set TRACE_FEATURE_MATCH_ENABLED=false for the demo and tell judges tracing uses hash comparison."]
    elif hit < len(expected) - 2:
        lines += ["", "RESULT: works, but misses several edits. Demo only the edits that show 'match' above."]
    else:
        lines += ["", "RESULT: good. Keep TRACE_FEATURE_MATCH_ENABLED=true. Show the edits that matched; do not promise crops of 50% or less."]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", default=str(DEMO_ASSETS / "sample_case_image.jpg"))
    ap.add_argument("--negatives", default=None, help="folder (or file) of unrelated photos; default: the other demo_assets samples")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    image = Path(a.image)
    if not image.is_file():
        print(f"ERROR: image not found: {image}")
        return 2
    try:
        res = run(image, negatives_from(a.negatives, image))
    except Exception as exc:
        print(f"ERROR: could not analyse {image}: {exc}")
        return 2
    print(json.dumps(res, indent=2) if a.json else render(res))
    return {"ok": 0, "false_positive": 1, "insufficient_features": 2}[res["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
