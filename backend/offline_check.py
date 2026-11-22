"""Can this install run the demo with the network OFF?  Run it while online AND once with Wi-Fi off.

    cd backend && python offline_check.py
    # in the demo stack:
    docker compose -f docker-compose.demo.yml --env-file deploy/.env.demo run --rm --no-deps api python offline_check.py

It forces Hugging Face into offline mode BEFORE loading anything, so a model that is not already on disk fails here, in your
rehearsal, instead of silently downloading (or hanging) on stage. Exit code 1 means do not rely on offline mode yet.

Checks: primary detector, second detector (if configured), face models, OpenCV matcher, ffmpeg (video/audio), every demo
asset passes content sniffing, and the data folder is writable.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"          # must be set before transformers / huggingface_hub are imported
os.environ["TRANSFORMERS_OFFLINE"] = "1"

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

results: list[tuple[str, str, str]] = []


def record(status: str, label: str, detail: str = "") -> None:
    results.append((status, label, detail))
    colour = {"OK": "32", "FAIL": "31", "WARN": "33", "SKIP": "90"}[status]
    print(f"\033[{colour}m{status:<5}\033[0m {label}" + (f"  ({detail})" if detail else ""))


def attempt(label: str, fn, *, required: bool) -> bool:
    try:
        fn()
        record("OK", label)
        return True
    except Exception as exc:
        short = str(exc).strip().splitlines()[0][:160] if str(exc).strip() else exc.__class__.__name__
        record("FAIL" if required else "WARN", label, short)
        return False


def main() -> int:
    from app.core.config import get_settings
    settings = get_settings()

    def primary():
        from app.services import deepfake_model
        deepfake_model._get_pipeline()

    primary_ok = attempt(f"primary detector {settings.DETECTOR_MODEL_ID} loads offline", primary, required=True)

    if settings.DETECTOR_SECOND_MODEL_ID:
        def second():
            from app.services import phase34
            phase34._image_pipeline(settings.DETECTOR_SECOND_MODEL_ID)
        attempt(f"second detector {settings.DETECTOR_SECOND_MODEL_ID} loads offline", second, required=False)
    else:
        record("SKIP", "second detector", "DETECTOR_SECOND_MODEL_ID not set")

    def faces():
        from app.services import face_embedding
        face_embedding._get_models()
    attempt("face detection + embedding models load offline", faces, required=False)

    def matcher():
        import cv2  # noqa: F401
        from app.services import feature_match
        from PIL import Image
        feature_match.extract(Image.new("RGB", (64, 64), (120, 120, 120)))
    attempt("OpenCV feature matcher runs", matcher, required=False)

    if shutil.which("ffmpeg"):
        record("OK", "ffmpeg is installed (video frames, non-WAV audio)")
    else:
        record("WARN", "ffmpeg is not installed", "video and non-WAV audio analysis will say so in the app; the Docker image includes it")

    def assets():
        from app.services.upload_sniff import sniff_media
        kinds = {".jpg": "image", ".jpeg": "image", ".png": "image", ".mp4": "video", ".wav": "audio"}
        bad = []
        files = [p for p in sorted((HERE / "demo_assets").iterdir()) if p.suffix.lower() in kinds]
        if not files:
            raise RuntimeError("no demo assets found in backend/demo_assets")
        for p in files:
            r = sniff_media(p.read_bytes()[:4096], kinds[p.suffix.lower()], p.name, mode="enforce")
            if not r.ok:
                bad.append(f"{p.name}: {r.reason}")
        if bad:
            raise RuntimeError("; ".join(bad))
    attempt("every demo asset passes upload content checks", assets, required=True)

    def writable():
        d = Path(settings.DATA_DIR) if hasattr(settings, "DATA_DIR") else HERE / "data"
        d.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=d):
            pass
    attempt("data folder is writable", writable, required=True)

    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]
    print(f"\n{sum(1 for r in results if r[0] == 'OK')} ok, {len(warns)} warnings, {len(fails)} failed.")
    if not primary_ok:
        print("The primary detector is NOT cached. Connect to the internet and run `python prefetch_models.py` once, then re-run this.\n"
              "Until then the demo uses the labelled pixel-heuristic fallback; do not call it a deepfake detector on stage.")
    elif warns:
        print("Warnings are optional features. Know which ones are off before you demo.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
