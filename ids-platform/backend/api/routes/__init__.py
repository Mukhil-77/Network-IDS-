"""
Aggregates every route module into one APIRouter so main.py has a single
`from backend.api.routes import api_router` to include.
"""

from fastapi import APIRouter

from backend.api.routes import (
    admin,
    alerts,
    analytics,
    attacks,
    capture,
    detection,
    flows,
    health,
    incidents,
    model,
    notifications,
    predict,
    reports,
    responses,
    statistics,
    system,
    testing,
    threat_intelligence,
    websocket,
)

api_router = APIRouter()
api_router.include_router(testing.router)
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(model.router, prefix="/model", tags=["Model"])
api_router.include_router(predict.router, tags=["Prediction"])
api_router.include_router(admin.router, tags=["Admin"])

# Milestone 6: SOC backend
api_router.include_router(alerts.router, tags=["Alerts"])
api_router.include_router(flows.router, tags=["Flows"])
api_router.include_router(statistics.router, tags=["Statistics"])
api_router.include_router(attacks.router, tags=["Attacks"])
api_router.include_router(system.router, prefix="/system", tags=["System"])
api_router.include_router(websocket.router, tags=["WebSocket"])
api_router.include_router(capture.router, prefix="/capture", tags=["Capture"])
api_router.include_router(detection.router, tags=["Detection"])

# Milestone 8: Automated Response Engine
api_router.include_router(responses.router, tags=["Response Engine"])

# Milestone 10: Reports, Analytics, Threat Intelligence, Incidents, Notifications
api_router.include_router(reports.router, tags=["Reports"])
api_router.include_router(analytics.router, tags=["Analytics"])
api_router.include_router(threat_intelligence.router, tags=["Threat Intelligence"])
api_router.include_router(incidents.router, tags=["Incidents"])
api_router.include_router(notifications.router, tags=["Notifications"])
