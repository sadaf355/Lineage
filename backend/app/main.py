from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.db.session import Base, engine
import app.models  # noqa: F401 — ensures every model is registered on Base before create_all

from app.routers import auth, incidents, media, sources, evidence, attribution, reports, web_search, geo, graph, copilot, ml, automation, footprints
from app.routers import phase34, phase56
from app.routers import manifest as manifest_router
from app.routers import origin as origin_router
from app.routers import operations as operations_router

settings = get_settings()

if settings.OFFLINE_DEMO_MODE:
    # Never reach for the network: models must already be in the HF cache (scripts/prefetch_models.py).
    # Set before transformers is imported anywhere, so cached weights load and nothing tries to download.
    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

class RequestBodyLimitMiddleware:
    """ASGI body limiter that also covers chunked requests without Content-Length."""

    def __init__(self, app):
        self.app = app
        self.limit = settings.MAX_REQUEST_BODY_MB * 1024 * 1024

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        content_length = next((v for k, v in scope.get("headers", []) if k.lower() == b"content-length"), None)
        if content_length:
            try:
                if int(content_length) > self.limit:
                    await self._reject(send)
                    return
            except ValueError:
                await self._reject(send)
                return

        seen = 0
        too_large = False

        async def limited_receive():
            nonlocal seen, too_large
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                seen += len(body)
                if seen > self.limit:
                    too_large = True
                    # Do not forward an oversized chunk to application code.
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            if too_large and message.get("type") == "http.response.start":
                return
            await send(message)

        await self.app(scope, limited_receive, guarded_send)
        if too_large:
            await self._reject(send)

    async def _reject(self, send):
        body = b'{"detail":"Request body exceeds the configured limit."}'
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


def _migrate_additive_columns() -> None:
    """Apply small in-place compatibility/data migrations for existing installs."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        if "audit_events" in tables:
            idx = {i["name"] for i in insp.get_indexes("audit_events")}
            if "ux_audit_incident_seq" not in idx:
                try:
                    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_audit_incident_seq ON audit_events (incident_id, seq)"))
                except Exception as exc:  # noqa: BLE001  (existing duplicate seq numbers: a forked chain that needs manual repair)
                    import logging
                    logging.getLogger("uvicorn.error").error("Could not create the audit unique index: %s", exc)
        if "users" in tables:
            ucols = {c["name"] for c in insp.get_columns("users")}
            if "mfa_secret" not in ucols:
                conn.execute(text("ALTER TABLE users ADD COLUMN mfa_secret VARCHAR"))
            if "mfa_last_step" not in ucols:
                conn.execute(text("ALTER TABLE users ADD COLUMN mfa_last_step INTEGER"))
            if "mfa_recovery_hashes" not in ucols:
                conn.execute(text("ALTER TABLE users ADD COLUMN mfa_recovery_hashes TEXT"))
            if "mfa_enabled" not in ucols:
                conn.execute(text("ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN DEFAULT FALSE"))
        if "source_locations" in tables:
            have_locations = {c["name"] for c in insp.get_columns("source_locations")}
            for col in ("city", "region"):
                if col not in have_locations:
                    conn.execute(text(f"ALTER TABLE source_locations ADD COLUMN {col} VARCHAR"))
        if "detection_results" in tables:
            detection_columns = {c["name"] for c in insp.get_columns("detection_results")}
            if "explainability_json" not in detection_columns:
                conn.execute(text("ALTER TABLE detection_results ADD COLUMN explainability_json TEXT"))
        if "media_items" in tables:
            cols = {c["name"] for c in insp.get_columns("media_items")}
            if "sha256" not in cols:
                conn.execute(text("ALTER TABLE media_items ADD COLUMN sha256 VARCHAR"))
        if "fingerprints" in tables:
            cols = {c["name"] for c in insp.get_columns("fingerprints")}
            for col in ("perceptual_hash", "difference_hash"):
                if col not in cols:
                    conn.execute(text(f"ALTER TABLE fingerprints ADD COLUMN {col} VARCHAR"))
        if "sources" in tables:
            cols = {c["name"] for c in insp.get_columns("sources")}
            if "page_sha256" not in cols:
                conn.execute(text("ALTER TABLE sources ADD COLUMN page_sha256 VARCHAR"))
        if "evidence_items" in tables:
            cols = {c["name"] for c in insp.get_columns("evidence_items")}
            if "sha256" not in cols:
                conn.execute(text("ALTER TABLE evidence_items ADD COLUMN sha256 VARCHAR"))
        if "audit_events" in tables:
            cols = {c["name"] for c in insp.get_columns("audit_events")}
            if "seq" not in cols:
                conn.execute(text("ALTER TABLE audit_events ADD COLUMN seq INTEGER"))
            for col in ("prev_hash", "event_hash"):
                if col not in cols:
                    conn.execute(text(f"ALTER TABLE audit_events ADD COLUMN {col} VARCHAR"))
        if "users" in tables:
            # Registration now canonicalizes email addresses. Normalize legacy rows
            # once at startup so case-insensitive login works for existing accounts.
            rows = conn.execute(text("SELECT id, email FROM users WHERE email IS NOT NULL")).fetchall()
            normalized = {}
            for user_id, email in rows:
                canonical = email.strip().lower()
                if canonical in normalized and normalized[canonical] != user_id:
                    raise RuntimeError(
                        f"Cannot normalize user emails: multiple accounts map to {canonical!r}. Resolve the duplicate before startup."
                    )
                normalized[canonical] = user_id
            for user_id, email in rows:
                canonical = email.strip().lower()
                if email != canonical:
                    conn.execute(text("UPDATE users SET email = :email WHERE id = :id"), {"email": canonical, "id": user_id})


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Simple create_all for now — fine for a hackathon/portfolio build.
    # A real deployment should switch to Alembic migrations before this
    # schema needs to evolve without dropping data.
    if settings.REQUIRE_DATABASE_MIGRATIONS:
        from alembic.config import Config
        from alembic import command
        cfg=Config("alembic.ini")
        command.upgrade(cfg, "head")
    else:
        Base.metadata.create_all(bind=engine)
    from app.services.file_storage import cleanup_decrypted_tempfiles
    cleanup_decrypted_tempfiles()
    _migrate_additive_columns()

    # Warm the ML models at startup rather than on the first user request.
    # Loading them lazily meant the first upload paid a multi-second penalty
    # (and two concurrent first-calls contended badly). Failures here are
    # non-fatal: the detect/fingerprint endpoints each fall back cleanly, so
    # the API still starts on a machine with no model access at all.
    if settings.PRELOAD_MODELS:
        import logging
        log = logging.getLogger("uvicorn.error")
        try:
            from app.services.face_embedding import _get_models
            _get_models()
            log.info("Face detection/embedding models loaded.")
        except Exception as e:
            log.warning("Face models unavailable (%s) — /fingerprint will report no face.", e)
        try:
            from app.services.deepfake_model import _get_pipeline
            _get_pipeline()
            log.info("Deepfake detection model loaded.")
        except Exception as e:
            log.warning(
                "Deepfake model unavailable (%s) — /detect will use the labelled pixel-heuristic fallback.", e
            )

    # Phase 3A: create the Neo4j constraints/indexes up front when Neo4j is reachable. Non-fatal —
    # without Neo4j every graph endpoint serves the in-memory KnowledgeGraph.
    import logging
    from app.services.graph_store import Neo4jGraphRepository
    from app.services.neo4j_service import Neo4jQueryError, Neo4jUnavailable, close_neo4j_service, get_neo4j_service
    neo = get_neo4j_service()
    if neo.configured:
        try:
            Neo4jGraphRepository(neo).ensure_schema()
            logging.getLogger("uvicorn.error").info("Neo4j connected; graph constraints ensured.")
        except (Neo4jUnavailable, Neo4jQueryError) as e:
            logging.getLogger("uvicorn.error").warning("Neo4j unavailable at startup (%s); using the in-memory graph.", e)

    # Phase E: with no Redis worker, run the abandoned-capture sweep in-process on a timer.
    # (With JOB_QUEUE_ENABLED + REDIS_URL the worker schedules it instead, so it never runs twice.)
    sweep_task = None
    if settings.CAPTURE_SWEEP_ENABLED and not (settings.JOB_QUEUE_ENABLED and settings.REDIS_URL):
        import asyncio

        async def _sweep_loop():
            from app.db.session import SessionLocal
            from app.services.capture_sweep import sweep_abandoned_captures
            interval = max(1, settings.CAPTURE_SWEEP_INTERVAL_HOURS) * 3600
            while True:
                await asyncio.sleep(60)  # let startup finish before the first pass

                def _run():
                    db = SessionLocal()
                    try:
                        sweep_abandoned_captures(db)
                    finally:
                        db.close()
                try:
                    await asyncio.to_thread(_run)
                except Exception:  # noqa: BLE001 - a failed pass must never take the API down
                    logging.getLogger("uvicorn.error").exception("Capture sweep failed")
                await asyncio.sleep(interval)

        sweep_task = asyncio.create_task(_sweep_loop())

    yield

    if sweep_task:
        sweep_task.cancel()
    close_neo4j_service()


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "LINEAGE — AI-powered synthetic identity abuse investigation platform. "
        "See the PRD/TRD/Project Flow docs for the full product spec; this API "
        "implements the Phase 1 backend foundations: auth, the real data model, "
        "encrypted file storage, and a genuine (heuristic, non-ML) detection + "
        "fingerprinting pipeline."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestBodyLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


@app.middleware("http")
async def security_headers(request, call_next):
    """Defensive headers for every API response. The CSP is deliberately narrow (framing and base-URI only)
    so the interactive API docs and blob-based media previews keep working."""
    response = await call_next(request)
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if not request.url.path.startswith(_DOC_PATHS):
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Content-Security-Policy", "frame-ancestors 'none'; base-uri 'none'")
    if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.get("/health", tags=["meta"])
def health():
    from app.services.graph_sync import graph_health
    from app.services import deepfake_model
    g = graph_health()
    detector = deepfake_model.model_status()
    return {
        "status": "ok",
        "env": settings.ENV,
        "neo4j": g["status"],
        "graph_backend": g["graph_backend"],
        "detector": detector,
        "offline_demo": settings.OFFLINE_DEMO_MODE,
        "storage_backend": settings.STORAGE_BACKEND,
        "database": "postgresql" if settings.DATABASE_URL.startswith("postgres") else "sqlite",
        "jobs": {"enabled": settings.JOB_QUEUE_ENABLED, "redis_configured": bool(settings.REDIS_URL)},
    }


app.include_router(auth.router)
app.include_router(incidents.router)
app.include_router(media.router)
app.include_router(sources.router)
app.include_router(evidence.router)
app.include_router(attribution.router)
app.include_router(reports.router)
app.include_router(web_search.router)
app.include_router(geo.router)
app.include_router(graph.router)  # Phase 3A: investigation knowledge graph (derived view; no new tables)
app.include_router(graph.health_router)  # Phase 3A: Neo4j status (connected | fallback)
app.include_router(copilot.router)  # Phase 3B: Investigation Copilot (Graph RAG)
app.include_router(ml.router)  # Phase 4: ML Intelligence (similarity, anomalies, clusters)
app.include_router(footprints.router)
app.include_router(automation.router)  # Phase 5: summary, gaps, timeline, reports, alert drafts, export, workflow, audit
app.include_router(phase34.router)
app.include_router(phase34.detector_router)
app.include_router(phase56.router)
app.include_router(manifest_router.router)  # Phase E: signed integrity manifests
app.include_router(origin_router.router)
app.include_router(operations_router.router)  # Phase 2-4: metadata-change report, origin report, legal packs, case bundle
