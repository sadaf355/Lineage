"""Generate the bundled SYNTHETIC sample media. Deterministic (fixed seeds), no network needed.

    python demo_assets/make_samples.py

These are abstract placeholder images, not photographs of anyone. They let the whole pipeline
(upload, hashes, detection, tracing, integrity, report) run offline without using real people's
content. For a convincing live demo, put your own CONSENTED images in this folder and re-seed.
Never demo with a real victim's content.
"""
from __future__ import annotations

import io
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent


def make_image(seed: int, size=(960, 640)) -> Image.Image:
    rng = np.random.default_rng(seed)
    w, h = size
    layers = []
    for sigma in (90, 40, 16):
        noise = rng.random((h // 4, w // 4, 3))
        im = Image.fromarray((noise * 255).astype("uint8")).resize((w, h), Image.BICUBIC)
        layers.append(np.asarray(im.filter(ImageFilter.GaussianBlur(sigma / 4)), dtype=float))
    base = 0.55 * layers[0] + 0.3 * layers[1] + 0.15 * layers[2]
    base = (base - base.min()) / (base.max() - base.min())
    img = Image.fromarray((base * 255).astype("uint8"))
    d = ImageDraw.Draw(img)
    for _ in range(7):
        x0, y0 = int(rng.integers(0, w - 200)), int(rng.integers(0, h - 200))
        x1, y1 = x0 + int(rng.integers(80, 320)), y0 + int(rng.integers(80, 260))
        colour = tuple(int(c) for c in rng.integers(20, 235, 3))
        (d.ellipse if rng.random() < 0.5 else d.rectangle)((x0, y0, x1, y1), fill=colour, outline=(255, 255, 255), width=3)
    d.text((14, h - 22), "SYNTHETIC SAMPLE - not a real photo", fill=(255, 255, 255))
    return img


def main() -> None:
    names = ["sample_case_image.jpg", "sample_image_b.jpg", "sample_image_c.jpg", "sample_image_d.jpg"]
    for i, name in enumerate(names):
        make_image(seed=1000 + i).save(HERE / name, "JPEG", quality=92)
    # The 'found on the web' copy: same picture, re-encoded and slightly resized, the way a re-upload looks.
    case = Image.open(HERE / "sample_case_image.jpg").convert("RGB")
    web = case.resize((int(case.width * 0.9), int(case.height * 0.9)), Image.LANCZOS)
    web.save(HERE / "trace_page" / "case-image-reupload.jpg", "JPEG", quality=70)
    # A short silent clip (3 s) so the video path can be shown without a real person.
    clip = HERE / "sample_clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=480x320:rate=15:duration=3",
                    "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "30", str(clip)], check=True)
    print("Wrote", ", ".join(names + ["trace_page/case-image-reupload.jpg", "sample_clip.mp4"]))


if __name__ == "__main__":
    main()
