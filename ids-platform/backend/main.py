"""
FastAPI application entrypoint.

Run with:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

This module only wires things together - configuration (core/config.py),
middleware (core/middleware.py), error handling (core/exception_handlers.py),
and routers (api/routes/) - and defines the one endpoint too trivial to earn
its own route module (GET /). All actual request handling lives in
backend/api/routes/, and all ML logic lives in backend/ml/ (Milestones 1-3),
untouched.
"""

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from backend.api.routes import api_router
from backend.api.schemas import RootResponse
from backend.auth.authentication import seed_default_data
from backend.auth.routes import router as auth_router
from backend.core.config import get_settings
from backend.core.exception_handlers import register_exception_handlers
from backend.core.logging import configure_logging
from backend.core.middleware import setup_middleware
from backend.database.connection import init_db, session_scope
from backend.database.models import ModelMetadataRecord
from backend.ml.artifacts import ArtifactNotFoundError
from backend.response_engine.response_service import response_service
from backend.services.alert_service import alert_service
from backend.services.prediction_service import prediction_service
from backend.threat_intelligence.enrichment import enrich_and_tag
from backend.threat_intelligence.feeds import LocalJSONFeedProvider
from backend.utils.logger import get_logger
from backend.websocket.broadcaster import broadcaster

logger = get_logger(__name__)
settings = get_settings()


def _seed_demo_threat_indicators() -> None:
    """
    Milestone 10: syncs the bundled demo feed (threat_intelligence/data/demo_feed.json)
    into ThreatIndicator so the platform has non-trivial "Known Malicious IP
    List" / "Known Bot Networks" data out of the box. Illustrative demo data,
    not a real threat feed - see feeds.py's docstring. Safe to call on every
    startup: LocalJSONFeedProvider.sync() upserts by value, never duplicates.
    """
    with session_scope() as db:
        count = LocalJSONFeedProvider().sync(db)
    logger.info("Seeded/refreshed %d demo threat indicator(s)", count)


def _on_alert_persisted(alert_summary: dict) -> None:
    """
    Composed callback for AlertService.on_alert_persisted (see that
    module's docstring - one slot, so Milestone 8's response trigger and
    Milestone 10's threat-intel tagging both run here rather than
    contending for the same attribute). Order matters only in that
    enrichment's tag isn't currently read by response_service - if a
    future milestone wants "tag influences response policy," this is
    where that ordering would be decided.
    """
    enrich_and_tag(alert_summary)
    response_service.handle_alert(alert_summary)


def _sync_model_metadata_to_db() -> None:
    """
    Milestone 6: copy the currently-loaded model's metadata.json into
    ModelMetadataRecord, so statistics_service can report detection_accuracy
    (and any Alert can be joined to its model version's training-time
    metrics) without reading files from disk on every query. Best-effort -
    same reasoning as prediction_service.startup(): no model yet shouldn't
    prevent the API from starting.
    """
    try:
        metadata = prediction_service.get_model_metadata()
    except ArtifactNotFoundError:
        logger.warning("No trained model available at startup; skipping model metadata DB sync")
        return

    with session_scope() as db:
        existing = db.execute(
            select(ModelMetadataRecord).where(ModelMetadataRecord.version == metadata.model_version_dir)
        ).scalars().first()
        if existing is not None:
            return  # already synced this version
        db.add(ModelMetadataRecord(
            version=metadata.model_version_dir or "unknown",
            model_name=metadata.model_name,
            training_date=metadata.training_date,
            accuracy=metadata.accuracy,
            precision=metadata.precision,
            recall=metadata.recall,
            f1_score=metadata.f1_score,
            num_features=len(metadata.features),
            pca_components=metadata.pca_components,
            sklearn_version=metadata.sklearn_version,
            project_version=metadata.project_version,
        ))
    logger.info("Synced model metadata (version=%s) to database", metadata.model_version_dir)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.LOG_LEVEL)
    app.state.start_time = time.time()
    init_db()
    with session_scope() as db:
        seed_default_data(db)  # Milestone 9: idempotent - creates default roles/permissions/admin only if none exist yet
    broadcaster.bind_loop(asyncio.get_running_loop())
    prediction_service.startup()  # warms the model cache; logs a warning (doesn't raise) if none is trained yet
    _sync_model_metadata_to_db()
    _seed_demo_threat_indicators()
    alert_service.on_alert_persisted = _on_alert_persisted  # Milestone 8+10: threat-intel tagging, then the response workflow, for every alert
    yield
    # No shutdown work needed: sklearn objects and DB connections need no explicit teardown here.


app = FastAPI(
    title="AI-Powered Network Threat Detection API",
    description=(
        "Serves real-time intrusion detection predictions from the trained "
        "Random Forest pipeline (StandardScaler -> IncrementalPCA -> "
        "RandomForestClassifier) built in Milestones 1-3."
    ),
    version=settings.API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

setup_middleware(app, settings)
register_exception_handlers(app)
app.include_router(auth_router, tags=["Auth"])
app.include_router(api_router)


@app.get("/", response_model=RootResponse, tags=["Root"], summary="API information")
async def root() -> RootResponse:
    return RootResponse(
        name="AI-Powered Network Threat Detection API",
        description="Real-time network intrusion detection and severity scoring.",
        version=settings.API_VERSION,
        docs_url="/docs",
    )
