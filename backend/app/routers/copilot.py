"""
Investigation Copilot API (Phase 3B — Graph RAG).

POST /incidents/{id}/copilot           {"question": "..."}  -> grounded answer + structured context
GET  /incidents/{id}/copilot/status                         -> whether an LLM is configured + which graph backend is used

The graph comes from graph_sync.load_graph (Neo4j when reachable, in-memory otherwise). Works without any LLM.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.deps import get_current_user
from app.models.user import User
from app.routers.incidents import _get_owned_incident
from app.schemas.copilot import CopilotQuestion
from app.services import consent, graph_rag, graph_sync, redis_rate_limit


def _llm_needs_consent(question: str, context: dict):
    return None, graph_rag._llm_status(
        False, "consent_required",
        f"Record {consent.PURPOSE_LLM} consent for this investigation to let the Copilot use an external language model. "
        "The answer below is built from the investigation records only.")

router = APIRouter(prefix="/incidents", tags=["copilot"])


@router.post("/{incident_id}/copilot")
def ask_copilot(
    incident_id: str, payload: CopilotQuestion,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    incident = _get_owned_incident(incident_id, db, current_user)
    if not redis_rate_limit.allow(f"copilot:{current_user.id}:{incident.id}", get_settings().RATE_LIMIT_COPILOT_PER_MINUTE):
        from fastapi import HTTPException
        raise HTTPException(status_code=429, detail="Copilot rate limit reached. Please wait before asking another question.")
    g, source = graph_sync.load_graph(incident, db)
    if graph_rag.llm_configured() and not consent.has_granted_consent(db, incident.id, current_user.id, consent.PURPOSE_LLM):
        # Case facts would be sent to a third-party LLM. Without consent, answer from the graph alone.
        return graph_rag.answer_question(g, payload.question.strip(), source, llm=_llm_needs_consent)
    return graph_rag.answer_question(g, payload.question.strip(), source)


@router.get("/{incident_id}/copilot/status")
def copilot_status(incident_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_owned_incident(incident_id, db, current_user)
    s = get_settings()
    return {
        "llm_configured": graph_rag.llm_configured(),
        "provider": (s.COPILOT_LLM_PROVIDER or "none").lower(),
        "model": s.COPILOT_MODEL if graph_rag.llm_configured() else None,
        "graph": graph_sync.graph_health(),
    }
