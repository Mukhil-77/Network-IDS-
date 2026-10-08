# SOC Platform - AI-Powered Network Intrusion Detection System

A production-ready Network Intrusion Detection System (IDS) combining machine learning-based threat detection with a modern SOC dashboard. Built with scientific rigor and operational practicality.

## Overview

SOC Platform provides real-time network threat detection using a trained **RandomForest multi-class classifier** with MinMaxScaler, served via FastAPI with a React/TypeScript frontend dashboard. The system detects **21 attack types** from the NF-UQ-NIDS-v2 dataset, includes automated response capabilities, threat intelligence enrichment, and comprehensive monitoring.

## Key Features

### ML Detection Engine
- **RandomForest Classifier** (200 trees) with MinMaxScaler + categorical encoding + imputation pipeline
- **Multi-class classification**: 21 attack types including Benign, DDoS, DoS, scanning, reconnaissance, XSS, password attacks, injection, botnet, brute force, infiltration, exploits, fuzzers, backdoor, generic, MITM, ransomware, theft, analysis, shellcode, worms
- **Model performance**: Accuracy 89.2% | F1 Macro 70.5% | F1 Weighted 92.3%
- **Real-time inference** via FastAPI with WebSocket streaming
- **Severity mapping**: LOW/MEDIUM/HIGH/CRITICAL per attack type

### SOC Dashboard (React + TypeScript + Tailwind)
- **Real-time dashboard** with live packet stream and detection badges
- **Alert management** with P1-P4 priority system and threat tagging
- **Incident management** with automatic grouping by source IP/attack type/time window
- **System health monitoring** (CPU, memory, disk, network, GPU telemetry)
- **Response center** with policy-based automated actions
- **Threat intelligence** enrichment and reputation scoring
- **Analytics & reporting** with PDF/CSV export
- **Dark/Light theme** with zoom controls (0.6x-2.0x)

### Automated Response Engine
- **Policy-driven actions**: LOG_ONLY, CREATE_ALERT, NOTIFY_SOC, QUARANTINE_HOST, BLOCK_IP, RATE_LIMIT, ISOLATE_NETWORK
- **Dry-run mode** for safe testing
- **Approval workflows** and rollback timers
- **Response history** with audit trail

### Threat Intelligence
- **Multi-source feeds** with indicator enrichment (IP reputation, ASN, geo)
- **Known malicious** / suspicious / trusted tagging
- **Local demo feed** bundled for immediate use

### Authentication & Authorization
- **JWT-based auth** with access/refresh tokens
- **Role-based access control** (Admin, Analyst, Viewer)
- **Audit logging** for all security-relevant actions

### Deployment Options
- **Local development** with `run_app.bat` (Windows) or manual commands
- **Docker Compose** with profiles for monitoring (Prometheus/Grafana), ELK stack, Redis caching
- **Desktop app** packaging via Electron + Vite

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SOC Platform                              │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (React + TypeScript + Vite + Tailwind)               │
│  ├── Dashboard, Alerts, Incidents, Response Center             │
│  ├── System Health, Threat Intel, Analytics, Reports           │
│  └── WebSocket → Real-time alerts & packets                    │
├─────────────────────────────────────────────────────────────────┤
│  Backend (FastAPI + Python)                                    │
│  ├── REST API + WebSocket (/ws/alerts)                         │
│  ├── ML Pipeline: Categorical Encoding → Imputer → MinMaxScaler → RandomForest │
│  ├── Packet Capture (scapy) → Flow Manager → Detection         │
│  ├── Automated Response Engine (policy-based)                  │
│  ├── Threat Intelligence (feeds, enrichment, reputation)       │
│  ├── Auth (JWT, RBAC, audit)                                   │
│  └── PostgreSQL (SQLAlchemy 2.0)                               │
├─────────────────────────────────────────────────────────────────┤
│  Infrastructure                                                 │
│  ├── PostgreSQL 16 (primary data)                              │
│  ├── Redis 7 (caching, optional)                               │
│  ├── Prometheus + Grafana (monitoring, optional)               │
│  └── ELK Stack (logging, optional)                             │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL 16+ (or use Docker)
- Windows 10/11 (primary), Linux/macOS supported

### Option 1: Local Development (Windows)

```bash
# Clone and navigate
cd ids-platform

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..

# Set up environment
copy .env.example .env
# Edit .env with your DATABASE_URL, JWT_SECRET_KEY, etc.

# Start PostgreSQL (or use Docker: docker compose up -d postgres)
# Run database migrations
python -m backend.database.migrations.create_tables

# Start the application
.\run_app.bat
```

**Access points:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option 2: Docker Compose (Recommended for Production)

```bash
cd ids-platform

# Configure environment
copy deployment\.env.example .env
# Edit .env with secure passwords and secrets

# Start core services (backend + frontend + postgres)
docker compose up -d --build

# With monitoring stack
docker compose --profile monitoring up -d --build

# With ELK logging stack
docker compose --profile with-elk up -d --build

# With Redis caching
docker compose --profile with-cache up -d --build
```

**Access points:**
- Frontend: http://localhost (port 80/443)
- Backend API: http://localhost:8000
- Grafana: http://localhost:3001 (admin/admin)
- Prometheus: http://localhost:9090
- Kibana: http://localhost:5601

### Default Login
- Username: `admin`
- Email: `admin@example.com`
- Password: `ChangeMe123!` (change immediately on first login)

## Project Structure

```
ids-platform/
├── backend/                    # FastAPI backend
│   ├── api/                    # API routes (auth, alerts, flows, incidents, etc.)
│   ├── auth/                   # JWT auth, RBAC, audit logging
│   ├── core/                   # Config, middleware, logging, exceptions
│   ├── database/               # SQLAlchemy models, connections, migrations
│   ├── detection/              # Detector, detection service, alerts
│   ├── ml/                     # ML pipeline (training, inference, etc.)
│   │   ├── encoders.py         # Shared LabelEncoderExt for persistence
│   │   ├── predictor.py        # Model loading & inference singleton
│   │   ├── artifacts.py        # Model artifact I/O
│   │   ├── inference.py        # Prediction pipeline
│   │   ├── validator.py        # Input validation
│   │   ├── severity.py         # Severity mapping
│   │   ├── confidence.py       # Confidence scoring
│   │   └── scripts/
│   │       └── train_v1_model.py  # v1 multi-class training script
│   ├── response_engine/        # Automated response policies & actions
│   ├── threat_intelligence/    # Feeds, enrichment, reputation
│   ├── analytics/              # Forecasting, trends, analytics
│   ├── reports/                # PDF/CSV report generation
│   ├── services/               # Alert, prediction, capture services
│   ├── websocket/              # WebSocket manager & broadcaster
│   ├── main.py                 # FastAPI app entrypoint
│   └── scripts/                # Training scripts
├── frontend/                   # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/         # Reusable UI components
│   │   ├── pages/              # Page components (Dashboard, Alerts, etc.)
│   │   ├── hooks/              # Custom React hooks
│   │   ├── services/           # API client & domain services
│   │   ├── context/            # React context providers
│   │   ├── types/              # TypeScript types
│   │   └── auth/               # Auth pages
│   ├── package.json
│   └── vite.config.ts
├── deployment/                 # Docker & infrastructure
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   ├── docker-compose.yml
│   ├── prometheus.yml
│   ├── nginx/
│   └── logging/
├── models/                     # Trained model artifacts
│   └── v1/                     # RandomForest multi-class model
│       ├── rf_model.pkl        # RandomForestClassifier (200 trees)
│       ├── scaler.pkl          # MinMaxScaler
│       ├── imputer.pkl         # SimpleImputer (mean strategy)
│       ├── label_encoder.pkl   # LabelEncoder for target classes
│       ├── cat_encoders.pkl    # Categorical feature encoders (13 cols)
│       ├── feature_names.json  # Raw feature names (41 features)
│       └── metadata.json       # Model metrics, classes, severity mapping
├── data/                       # Datasets
│   └── raw/NF-UQ-NIDS-v2/      # Training dataset (~13GB)
├── scripts/                    # Build & utility scripts
├── run_app.bat                 # Windows startup script
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Configuration

Key configuration files:
- `.env` - Environment variables (database, JWT secrets, API keys)
- `backend/core/config.py` - Pydantic Settings (all config with defaults)
- `frontend/tailwind.config.js` - Tailwind theme configuration
- `deployment/docker-compose.yml` - Service definitions
- `backend/response_engine/response_rules.yaml` - Response policies

### Important Environment Variables

```env
# Database
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/ids_soc

# Security (REQUIRED - change in production!)
JWT_SECRET_KEY=your-random-256-bit-secret-key

# ML Model
MODEL_PATH=./models

# Live Response Safety Gate (must be explicitly enabled)
ENABLE_LIVE_RESPONSE_ACTIONS=false

# Optional: Notification channels
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=alerts@example.com
SMTP_PASSWORD=***
ALERT_EMAIL_TO=soc@example.com

TELEGRAM_BOT_TOKEN=***
TELEGRAM_CHAT_ID=***

RESPONSE_WEBHOOK_URL=https://webhook.example.com/alerts
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |
| GET | `/system/health` | Extended health (model, DB, alerts/min) |
| GET | `/system/stats` | OS telemetry (CPU, mem, disk, net, GPU) |
| GET | `/alerts` | Paginated alerts with filters |
| GET | `/alerts/latest` | Latest N alerts |
| GET | `/incidents` | Paginated incidents |
| GET | `/flows` | Network flows with pagination |
| GET | `/statistics` | Threat counts, trends, accuracy |
| GET | `/deployment/metrics` | Latency, throughput, detection metrics |
| GET | `/threat-intelligence/indicators` | Threat indicators with pagination |
| GET | `/threat-intelligence/stats` | Feed statistics |
| POST | `/predict` | Single flow prediction |
| POST | `/predict/batch` | Batch flow predictions |
| WS | `/ws/alerts` | Real-time alerts & packets stream |
| POST | `/auth/login` | User login |
| POST | `/auth/refresh` | Refresh access token |
| GET | `/users/me` | Current user profile |

See `/docs` (Swagger UI) or `/redoc` for full API documentation.

## ML Pipeline Details

### Training v1 Multi-Class Model

```bash
# Train new v1 model (2M sample, ~10-15 min)
cd ids-platform
python -m backend.scripts.train_v1_model

# For full dataset training (much longer)
# Edit SAMPLE_SIZE = None in train_v1_model.py
```

### Model Artifacts (models/v1/)

| File | Description |
|------|-------------|
| `rf_model.pkl` | RandomForestClassifier (200 trees, max_depth=20, balanced class weights) |
| `scaler.pkl` | MinMaxScaler fitted on training data |
| `imputer.pkl` | SimpleImputer (mean strategy) for missing values |
| `label_encoder.pkl` | LabelEncoder for 21 attack classes |
| `cat_encoders.pkl` | LabelEncoderExt for 13 categorical features |
| `feature_names.json` | 41 raw feature names (exact order for scaler) |
| `metadata.json` | Model metrics, classes, severity mapping, training params |

### Pipeline Flow

```
Raw Flow Features (41)
    → Categorical Encoding (13 columns: ports, protocol, flags, etc.)
    → SimpleImputer (mean)
    → MinMaxScaler (0-1 range)
    → RandomForestClassifier
    → Prediction: 1 of 21 attack classes
    → Confidence (max probability)
    → Severity Mapping (LOW/MEDIUM/HIGH/CRITICAL)
```

### Supported Attack Types (21 classes)

| Attack Type | Severity | Description |
|-------------|----------|-------------|
| Benign | LOW | Normal traffic |
| DDoS | CRITICAL | Distributed Denial of Service |
| DoS | CRITICAL | Denial of Service |
| scanning | MEDIUM | Port/service scanning |
| Reconnaissance | LOW | Network reconnaissance |
| xss | HIGH | Cross-site scripting |
| password | HIGH | Password attacks |
| injection | HIGH | SQL/command injection |
| Bot | CRITICAL | Botnet traffic |
| Brute Force | HIGH | Brute force login |
| Infilteration | CRITICAL | Network infiltration |
| Exploits | CRITICAL | Exploit attempts |
| Fuzzers | MEDIUM | Fuzzing attacks |
| Backdoor | CRITICAL | Backdoor communication |
| Generic | MEDIUM | Generic anomalies |
| mitm | HIGH | Man-in-the-middle |
| ransomware | CRITICAL | Ransomware activity |
| Theft | HIGH | Data exfiltration |
| Analysis | LOW | Analysis tools |
| Shellcode | CRITICAL | Shellcode execution |
| Worms | CRITICAL | Worm propagation |

## Development

### Running Tests
```bash
# Backend tests (if available)
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

### Code Quality
```bash
# Python linting (if configured)
ruff check backend/

# TypeScript type checking
cd frontend
npx tsc --noEmit
```

## Deployment Notes

### Production Checklist
- [ ] Set strong `JWT_SECRET_KEY` (256-bit random)
- [ ] Set `ENABLE_LIVE_RESPONSE_ACTIONS=true` only after testing
- [ ] Configure PostgreSQL with strong passwords
- [ ] Set up SSL/TLS (nginx reverse proxy included)
- [ ] Configure notification channels (email, Telegram, webhook)
- [ ] Set up log aggregation (ELK stack profile)
- [ ] Enable monitoring (Prometheus/Grafana profile)
- [ ] Configure backup strategy for PostgreSQL
- [ ] Review and customize `response_rules.yaml`

### Model Updates
1. Train new model version in `models/v{N}/`
2. Update `MODEL_PATH` or symlink to new version
3. Restart backend to load new artifacts
4. Metadata auto-syncs to database on startup

## License

MIT License - see LICENSE file for details.

## Security

Report vulnerabilities to security@example.com (replace with actual contact).

---

**Built for security operations teams who need reliable, explainable, and actionable network threat detection.**