# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows the milestone-based development history below.

## [Unreleased]

### Added
- Documented router aggregation entry point (`backend/api/router.py`).
- `backend/api/routes/auth.py` and `backend/api/routes/predictions.py`
  re-export shims so the documented module names resolve to real routers.
- Detection control endpoints (`backend/api/routes/detection.py`):
  start/stop/status/recent-alerts for the capture -> predict -> alert pipeline.
- Auth data-access layer (`backend/auth/repositories.py`): user, session and
  audit-log repositories.
- Seeding entry point (`backend/auth/seed.py`).
- Batch training CLI (`backend/ml/train_all_models.py`): trains every model
  variant and saves each as its own versioned artifact.
- Response-engine documented modules (`executor.py`, `registry.py`,
  `registrations.py`, `rules.py`) re-exporting the engine's public API.
- Attack simulation service (`backend/services/testing_service.py`) with
  realistic per-attack-type profiles; testing routes now delegate to it.
- Incident service documented entry point (`backend/incidents/incident_service.py`).
- PyShark/TShark capture manager (`backend/packet_capture/tshark_capture.py`).
- Channel-aware WebSocket manager with heartbeat
  (`backend/websocket/ws_manager.py`); `manager.py` kept as an alias.
- End-to-end training CLI under `backend/scripts/train_pipeline.py`.
- Project documentation (`README.md`, `CHANGELOG.md`, `pytest.ini`).
- Deployment assets (`deployment/`): docker-compose, Dockerfiles, nginx,
  Prometheus + Grafana configuration.
- Frontend (React dashboard) integrated into `frontend/`.

## [Milestone 10] - Reports, Analytics, Threat Intelligence, Incidents, Notifications

- Report generation in PDF/CSV/JSON via `backend/reports/`.
- Analytics, trend computation and threat forecasting via `backend/analytics/`.
- Threat indicator cache, reputation and enrichment via
  `backend/threat_intelligence/`.
- Incident lifecycle management (create/assign/notes/timeline/status).
- Notification manager with email/Telegram/webhook channels (log-only stubs).

## [Milestone 9] - Authentication & RBAC

- JWT access/refresh tokens, session revocation, audit logging.
- Roles and granular permissions; default admin seeding.
- WebSocket endpoints require a valid access token.

## [Milestone 8] - Automated Response Engine

- 11 built-in response actions, severity-based policy rules, rollback support.
- Automatic trigger wired to alert persistence.

## [Milestone 7] - Database + Services Layer

- SQLAlchemy models, repositories and service layer
  (prediction, alert, history, capture, statistics).

## [Milestone 6] - SOC Backend

- Alert/flow/statistics APIs, health checks, WebSocket alert streaming.

## [Milestone 5] - Live Packet Capture

- Scapy/PyShark capture backends, flow manager, feature extraction.

## [Milestone 4] - FastAPI Backend

- REST API around the prediction pipeline, structured logging, middleware.

## [Milestone 3] - Prediction Service

- Inference pipeline, model artifacts, confidence and severity scoring.

## [Milestone 2] - Feature Engineering & Training

- StandardScaler + IncrementalPCA, Random Forest training, evaluation.

## [Milestone 1] - Dataset Preprocessing

- CIC-IDS2017 loading, cleaning, label mapping, memory optimization.
