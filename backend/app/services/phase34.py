from __future__ import annotations

import hashlib
import io
import json
import math
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.core.config import get_settings

settings = get_settings()


@dataclass
class ModelScore:
    model_id: str
    score: float | None
    loaded: bool
    error: str | None = None


@lru_cache(maxsize=4)
def _image_pipeline(model_id: str):
    # Cached: building a pipeline per frame reloaded the weights on every call.
    from transformers import pipeline
    return pipeline("image-classification", model=model_id)


def ensemble_image_classification(raw: bytes) -> dict[str, Any]:
    """Run configured image detectors. A second model is optional and never silently invented."""
    from PIL import Image
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    model_ids = [settings.DETECTOR_MODEL_ID]
    if settings.DETECTOR_SECOND_MODEL_ID and settings.DETECTOR_SECOND_MODEL_ID not in model_ids:
        model_ids.append(settings.DETECTOR_SECOND_MODEL_ID)
    fake_labels = {"fake", "deepfake", "manipulated", "synthetic", "ai-generated", "ai generated"}
    scores: list[ModelScore] = []
    for model_id in model_ids:
        try:
            clf = _image_pipeline(model_id)
            labels = clf(image)
            score = next((float(x["score"]) * 100 for x in labels if str(x["label"]).strip().lower() in fake_labels), None)
            scores.append(ModelScore(model_id, round(score, 2) if score is not None else None, True,
                                     None if score is not None else "Model returned no recognized manipulation label."))
        except Exception as exc:
            scores.append(ModelScore(model_id, None, False, str(exc)))
    valid = [s.score for s in scores if s.loaded and s.score is not None]
    combined = round(sum(valid) / len(valid), 2) if valid else None
    return {
        "scores": [s.__dict__ for s in scores],
        "combined_score": combined,
        "ensemble": len(valid) >= 2,
        "confidence_band": {"low": round(min(valid), 2), "high": round(max(valid), 2)} if valid else None,
    }


def extract_audio_wav(video_or_audio: bytes, suffix: str) -> bytes:
    """Extract PCM mono audio with ffmpeg. Raises a clear error if ffmpeg is unavailable."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / f"input{suffix or '.mp4'}"
        out = Path(td) / "audio.wav"
        src.write_bytes(video_or_audio)
        try:
            subprocess.run(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(src),
                 "-ac", "1", "-ar", "16000", "-f", "wav", str(out)],
                check=True, timeout=settings.AUDIO_EXTRACTION_TIMEOUT_SECONDS,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("ffmpeg is not installed; audio analysis is unavailable on this host.") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError("No decodable audio stream was found.") from exc
        return out.read_bytes()


def audio_spectrogram_fingerprint(wav_bytes: bytes) -> str:
    """Deterministic spectrogram fingerprint for provenance/matching, not a deepfake verdict."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        channels, width, rate, frames = wf.getnchannels(), wf.getsampwidth(), wf.getframerate(), wf.getnframes()
        if width not in (1, 2, 4):
            raise ValueError("Unsupported PCM width")
        data = wf.readframes(frames)
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[width]
    samples = np.frombuffer(data, dtype=dtype).astype(np.float32)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if width == 1:
        samples -= 128
    if samples.size == 0:
        raise ValueError("Audio stream is empty")
    # Compact spectral landmarks; stable enough for exact/re-encoded provenance checks.
    nfft = 1024
    hop = 512
    frames_out = []
    window = np.hanning(nfft)
    for start in range(0, max(1, len(samples) - nfft + 1), hop):
        chunk = samples[start:start+nfft]
        if len(chunk) < nfft:
            chunk = np.pad(chunk, (0, nfft-len(chunk)))
        spec = np.abs(np.fft.rfft(chunk * window))
        bins = spec[:128]
        top = np.argpartition(bins, -8)[-8:]
        frames_out.append("-".join(map(str, sorted(top))))
        if len(frames_out) >= 128:
            break
    return hashlib.sha256("|".join(frames_out).encode()).hexdigest()


@lru_cache(maxsize=2)
def _audio_pipeline(model_id: str):
    from transformers import pipeline
    return pipeline("audio-classification", model=model_id)


def audio_deepfake_score(wav_bytes: bytes) -> dict[str, Any]:
    """Optional configured Hugging Face audio classifier; blank model means no claim is made."""
    model_id = settings.AUDIO_DEEPFAKE_MODEL_ID.strip()
    if not model_id:
        return {"configured": False, "score": None, "model_id": None,
                "message": "No validated audio-deepfake model is configured; fingerprinting remains available."}
    try:
        clf = _audio_pipeline(model_id)
        labels = clf(wav_bytes)
        fake_labels = {"fake", "deepfake", "synthetic", "spoof", "generated", "ai-generated"}
        score = next((float(x["score"]) * 100 for x in labels if str(x["label"]).lower() in fake_labels), None)
        return {"configured": True, "score": round(score, 2) if score is not None else None,
                "model_id": model_id, "labels": labels}
    except Exception as exc:
        return {"configured": True, "score": None, "model_id": model_id, "error": str(exc)}


FAKE_LABELS = {"fake", "deepfake", "manipulated", "synthetic", "ai-generated", "ai generated"}


def score_with_model(model_id: str, raw: bytes) -> float | None:
    """Manipulation likelihood (0-100) from one named model, or None if it cannot score.

    None means "could not score" and is never replaced by a default, so evaluation reports
    an unscored count instead of silently counting failures as correct or incorrect.
    """
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    labels = _image_pipeline(model_id)(image)
    score = next((float(x["score"]) * 100 for x in labels if str(x["label"]).strip().lower() in FAKE_LABELS), None)
    return round(score, 2) if score is not None else None


def roc_auc(labels: list[bool], scores: list[float]) -> float | None:
    """ROC-AUC via the Mann-Whitney rank statistic (ties get half credit). None if one class is missing."""
    pos = [s for l, s in zip(labels, scores) if l]
    neg = [s for l, s in zip(labels, scores) if not l]
    if not pos or not neg:
        return None
    wins = 0.0
    for p in pos:
        for n in neg:
            wins += 1.0 if p > n else 0.5 if p == n else 0.0
    return wins / (len(pos) * len(neg))


def _parse_label(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value) != 0
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "fake", "deepfake", "manipulated", "synthetic", "ai-generated"}:
        return True
    if normalized in {"0", "false", "no", "real", "genuine", "authentic"}:
        return False
    raise ValueError(f"Unsupported label value: {value!r}. Use 0/1, true/false, real/fake, or an equivalent binary label.")


def _binary_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tp = tn = fp = fn = 0
    labels: list[bool] = []
    scores: list[float] = []
    for row in rows:
        actual = _parse_label(row.get("label"))
        score = float(row.get("score", 0))
        predicted = score >= float(row.get("threshold", settings.DETECTOR_EVAL_THRESHOLD))
        labels.append(actual)
        scores.append(score)
        if predicted and actual: tp += 1
        elif predicted and not actual: fp += 1
        elif not predicted and actual: fn += 1
        else: tn += 1
    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    auc = roc_auc(labels, scores)
    return {"samples": total, "true_positive": tp, "true_negative": tn, "false_positive": fp,
            "false_negative": fn, "accuracy": round(accuracy * 100, 2),
            "precision": round(precision * 100, 2), "recall": round(recall * 100, 2), "f1": round(f1 * 100, 2),
            "roc_auc": round(auc, 4) if auc is not None else None,
            "confusion_matrix": [[tn, fp], [fn, tp]],  # rows = actual real/fake, cols = predicted real/fake
            "threshold": settings.DETECTOR_EVAL_THRESHOLD}


def evaluate_binary_predictions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate a labelled manifest without claiming an external benchmark.

    Rows are {label, score[, threshold][, condition]}. When rows carry a `condition`
    (original, jpeg_q50, resize_50 ...), metrics are also broken down per condition.
    """
    result = _binary_metrics(rows)
    conditions = sorted({str(r["condition"]) for r in rows if r.get("condition") not in (None, "")})
    if conditions:
        result["by_condition"] = {c: _binary_metrics([r for r in rows if str(r.get("condition")) == c]) for c in conditions}
    return result


def licensed_reverse_image_search(raw: bytes) -> dict[str, Any]:
    """Optional Google Cloud Vision Web Detection adapter.

    It is disabled unless REVERSE_SEARCH_PROVIDER=google_vision and credentials are configured.
    The result is always returned as candidate evidence requiring investigator confirmation.
    """
    if settings.REVERSE_SEARCH_PROVIDER != "google_vision":
        return {"configured": False, "provider": settings.REVERSE_SEARCH_PROVIDER or None,
                "message": "No licensed reverse-image provider is configured."}
    try:
        from google.cloud import vision
        client = vision.ImageAnnotatorClient()
        response = client.web_detection(image=vision.Image(content=raw))
        web = response.web_detection
        pages = [{"url": p.url, "title": p.page_title} for p in web.pages_with_matching_images]
        entities = [{"description": e.description, "score": e.score} for e in web.web_entities]
        return {"configured": True, "provider": "google_vision", "pages": pages, "entities": entities,
                "message": "Reverse-image candidates returned by the licensed provider; investigator confirmation required."}
    except Exception as exc:
        return {"configured": True, "provider": "google_vision", "error": str(exc), "pages": [], "entities": []}
