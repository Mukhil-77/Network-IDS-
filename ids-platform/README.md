# AI-Powered SOC Platform

A modular, production-ready security operations center (SOC) system for
real-time network threat detection, automated incident response, and
security workflow management. Uses a Random Forest classifier trained on
the CIC-IDS2017 dataset (78 network flow features, reduced via
IncrementalPCA) to detect multi-class network attacks.

> Reference structure: `originalsetup.pdf` documents the original setup for
> this project (Milestone 3 baseline: Python 3.14, React 19, FastAPI).

## Key capabilities

- Real-time packet capture (Scapy or PyShark) with per-flow feature extraction
- ML-based threat classification with sub-millisecond inference
- WebSocket-based live alert streaming to the dashboard
- Automated response engine with 11 actions (firewall block, rate-limit, quarantine, etc.)
- Full incident management lifecycle (create -> assign -> investigate -> close)
- Role-based access control (admin/analyst/viewer) with JWT authentication
- Threat intelligence aggregation (IP reputation, IOC management)
- Report generation (daily, weekly, monthly, incident, executive) in PDF/CSV/JSON
- Analytics, trend analysis, and threat forecasting
- Notification routing (email, Telegram, webhook) per severity
- Prometheus/Grafana monitoring and ELK stack logging (see deployment/)
- Docker Compose deployment with horizontal scaling support

## Technology stack

| Layer               | Technology                                            |
| ------------------- | ----------------------------------------------------- |
| Backend framework   | FastAPI (Python 3.14)                                 |
| Database            | PostgreSQL 16 (SQLite for tests) via SQLAlchemy async |
| ML model            | scikit-learn Random Forest via joblib                 |
| Packet capture      | Scapy / PyShark (tshark)                              |
| Auth                | JWT (HS256) via PyJWT + bcrypt via passlib            |
| Frontend            | React + TypeScript + Vite + Tailwind CSS              |
| Server state        | TanStack React Query, Axios, Recharts, React Router   |
| Reverse proxy       | nginx 1.27 (TLS, rate limiting)                       |
| Monitoring/logging  | Prometheus + Grafana, ELK stack (optional profile)    |
| Testing             | pytest + pytest-asyncio, Vitest (frontend)            |

## Project structure

```
ids-platform/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── core/                      # config, logging, middleware
│   ├── api/                       # router.py + routes/ (auth, alerts, flows,
│   │                              # statistics, health, predictions, detection,
│   │                              # capture, model, incidents, responses,
│   │                              # reports, analytics, threat_intel,
│   │                              # notifications, testing, system)
│   ├── database/                  # connection, models, migrations, repositories
│   ├── auth/                      # JWT, RBAC, password hashing, audit, seed
│   ├── ml/                        # predictor, inference, artifacts, training,
│   │                              # evaluation, feature engineering, severity...
│   ├── detection/                 # detection_service (capture -> predict -> alert)
│   ├── packet_capture/            # capture, flow_manager, flow_features,
│   │                              # packet_parser, tshark_capture...
│   ├── response_engine/           # 11 actions, rules, executor, registry, recovery
│   ├── incidents/                 # incident_service
│   ├── websocket/                 # ws_manager (channels, heartbeat)
│   ├── notifications/             # email / telegram / webhook services
│   ├── reports/                   # report_service, pdf_generator, csv_export
│   ├── threat_intelligence/       # reputation, indicators, enrichment, feeds
│   ├── analytics/                 # analytics_service, trends, forecasting
│   ├── services/                  # prediction, alert, history, capture,
│   │                              # statistics, testing services
│   ├── utils/                     # logger
│   └── scripts/                   # train_pipeline (end-to-end training CLI)
├── frontend/                      # React dashboard (22 pages)
├── tests/                         # backend test suite (pytest)
├── deployment/                    # Docker, nginx, monitoring, logging
├── docs/                          # documentation
├── examples/                      # sample prediction input / output
├── models/                        # versioned ML model artifacts (v1...)
├── .env / .env.example            # environment configuration
├── requirements.txt               # Python dependencies
├── pytest.ini                     # pytest configuration
└── README.md
```

## Quick start

### Backend

```bash
cd ids-platform
python -m venv venv
venv\Scripts\activate          # Windows (or source venv/bin/activate on Linux/macOS)
pip install -r requirements.txt
copy .env.example .env         # then edit DB settings as needed
python scripts\train_model.py  # train the initial model into models/v1
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

API docs: http://localhost:8000/docs (Swagger UI) or /redoc.

Default admin account (seeded on first startup): `admin` / `admin123`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # point VITE_API_BASE at your backend if not localhost
npm run dev
```

### Tests

```bash
cd ids-platform
venv\Scripts\activate
python -m pytest            # backend suite
cd frontend && npm test     # frontend suite (vitest)
```

## Deployment

See `deployment/` for Docker Compose (backend, frontend, PostgreSQL,
Prometheus, Grafana; optional Redis and ELK profiles), Dockerfiles, nginx
configuration, and Prometheus alert rules.

## Known limitations

1. Notification services (email/Telegram/webhook) log to console only - no
   real SMTP/Telegram/HTTP client integration yet.
2. Threat intelligence feeds return demo data; no real AlienVault OTX /
   VirusTotal API keys are configured.
3. Response actions kill_process, isolate_host, quarantine_host,
   restart_service, revoke_session, vpn_isolation are simulation-only.
4. Tables are created via `Base.metadata.create_all()` on startup; Alembic
   migrations are not configured yet.
5. The default JWT secret must be overridden with `JWT_SECRET_KEY` in
   production.
