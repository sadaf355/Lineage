from __future__ import annotations
from dataclasses import dataclass
from app.core.config import get_settings

settings = get_settings()

@dataclass
class SafetyDecision:
    allowed: bool
    reason: str


def review_required(action: str, face_similarity: float | None = None) -> SafetyDecision:
    if action in {"face_search", "trace_accept", "takedown"} and settings.REQUIRE_REVIEW_FOR_SENSITIVE_ACTIONS:
        return SafetyDecision(False, "Human review is required before this sensitive action can proceed.")
    if face_similarity is not None and face_similarity >= settings.FACE_SIMILARITY_REVIEW_THRESHOLD:
        return SafetyDecision(False, "High face-similarity results require explicit investigator review and must not be treated as identity proof.")
    return SafetyDecision(True, "Allowed")
