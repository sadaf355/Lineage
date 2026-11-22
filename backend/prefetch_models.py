"""Download and cache every model the app needs, so the demo can run with Wi-Fi off.

Run ONCE while online:
    python prefetch_models.py
or inside the stack:
    docker compose -f docker-compose.demo.yml --env-file deploy/.env.demo run --rm --no-deps api python prefetch_models.py

Then set OFFLINE_DEMO_MODE=true. Models live in HF_HOME / TORCH_HOME, which the demo compose file keeps
on a persistent volume. Exit code is non-zero if the PRIMARY detector could not be cached.
"""
from __future__ import annotations

import sys

from app.core.config import get_settings

settings = get_settings()


def _try(label: str, fn) -> bool:
    try:
        fn()
        print(f"OK    {label}")
        return True
    except Exception as exc:  # report and continue so one failure does not hide the others
        print(f"FAIL  {label}: {exc}")
        return False


def main() -> int:
    from app.services import deepfake_model, face_embedding, phase34

    primary_ok = _try(f"primary detector {settings.DETECTOR_MODEL_ID}", lambda: deepfake_model._get_pipeline())
    if settings.DETECTOR_SECOND_MODEL_ID:
        _try(f"second detector {settings.DETECTOR_SECOND_MODEL_ID}", lambda: phase34._image_pipeline(settings.DETECTOR_SECOND_MODEL_ID))
    else:
        print("SKIP  second detector (DETECTOR_SECOND_MODEL_ID not set)")
    _try("face detection + embedding models", lambda: face_embedding._get_models())
    if settings.AUDIO_DEEPFAKE_MODEL_ID:
        print("NOTE  AUDIO_DEEPFAKE_MODEL_ID is set; it is loaded lazily and is not prefetched here.")
    print("\nDone. You can now run with OFFLINE_DEMO_MODE=true." if primary_ok else "\nPrimary detector NOT cached; do not rely on offline mode yet.")
    return 0 if primary_ok else 1


if __name__ == "__main__":
    sys.exit(main())
