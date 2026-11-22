"""Create degraded copies of every 'original' image and append them to the manifest.

    python eval/build_degraded.py --manifest eval/manifest.csv

For each row whose condition is 'original' this writes four copies into eval/images/ and adds
manifest rows with the same label and source:

    jpeg_q50     JPEG re-encode at quality 50
    resize_50    downscale to 50% then back up (loses fine detail, keeps pixel size)
    crop_80      80% centre crop
    screenshot   downscale 75%, JPEG q80, then PNG, mimicking a screenshot shared in chat apps

Re-running is safe: existing degraded rows and files are skipped.
"""
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path

from PIL import Image

CONDITIONS = ("jpeg_q50", "resize_50", "crop_80", "screenshot")


def _jpeg(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def degrade(img: Image.Image, condition: str) -> tuple[Image.Image, str]:
    """Return (image, file extension) for one degradation."""
    img = img.convert("RGB")
    w, h = img.size
    if condition == "jpeg_q50":
        return _jpeg(img, 50), ".jpg"
    if condition == "resize_50":
        small = img.resize((max(1, w // 2), max(1, h // 2)), Image.LANCZOS)
        return small.resize((w, h), Image.BICUBIC), ".png"
    if condition == "crop_80":
        cw, ch = int(w * 0.8), int(h * 0.8)
        left, top = (w - cw) // 2, (h - ch) // 2
        return img.crop((left, top, left + cw, top + ch)), ".png"
    if condition == "screenshot":
        small = img.resize((max(1, int(w * 0.75)), max(1, int(h * 0.75))), Image.BILINEAR)
        return _jpeg(small, 80), ".png"
    raise ValueError(condition)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="eval/manifest.csv")
    ap.add_argument("--images", default=None, help="images folder (default: <manifest dir>/images)")
    args = ap.parse_args()
    manifest = Path(args.manifest)
    images = Path(args.images) if args.images else manifest.parent / "images"

    with manifest.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    existing = {r["filename"] for r in rows}
    added = 0
    for row in [r for r in rows if r["condition"] == "original"]:
        src = images / row["filename"]
        if not src.is_file():
            print(f"skip (missing file): {src}")
            continue
        base = Path(row["filename"]).stem
        with Image.open(src) as im:
            im.load()
            for cond in CONDITIONS:
                out_img, ext = degrade(im, cond)
                name = f"{base}__{cond}{ext}"
                if name in existing:
                    continue
                out_img.save(images / name)
                rows.append({"filename": name, "label": row["label"], "source": row["source"], "condition": cond,
                             **({"group": row["group"]} if row.get("group") else {})})
                existing.add(name)
                added += 1
    with manifest.open("w", newline="", encoding="utf-8") as fh:
        fields = ["filename", "label", "source", "condition"] + (["group"] if any(r.get("group") for r in rows) else [])
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"Added {added} degraded rows. Manifest now has {len(rows)} rows.")


if __name__ == "__main__":
    main()
