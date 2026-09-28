# SOC Platform - AI-Powered Network Intrusion Detection System

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)]()
[![Python Version](https://img.shields.io/badge/python-3.12+-blue)]()
[![Frontend](https://img.shields.io/badge/frontend-React%2BTypeScript-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

## Overview

SOC Platform is a research-grade, production-ready Network Intrusion Detection System (IDS) that combines machine learning-based threat detection with a modern SOC (Security Operations Center) dashboard. Built with a focus on **scientific rigor**, **operational usability**, and **deployment readiness**.

## Key Features

### 🔬 Research-Grade Detection Engine
- **Leakage-safe evaluation pipeline** - Fixed SMOTE data leakage by applying oversampling only to training data after train/test split
- **Comprehensive metrics** - MCC, per-class FPR/FNR, weighted F1, PR-AUC, ROC-AUC, macro/micro averages
- **Cross-dataset generalization** - Train on CIC-IDS2017, test on UNSW-NB15 and vice versa
- **Unseen attack detection** - Leave-one-class-out evaluation for zero-day attack detection
- **Model robustness testing** - Gaussian noise, feature scaling, missing features, distribution shift, OOD detection

### 🧠 Explainable AI & Risk Scoring
- **SHAP Explainability** - TreeSHAP for tree-based models, KernelSHAP fallback for KNN/SVM
- **Per-prediction explanations** - Top contributing features with direction (positive/negative impact)
- **Risk scoring** - Multi-factor risk scoring (0-100): attack probability, severity, traffic behavior, frequency, source reputation, destination sensitivity, historical events, persistence
- **Severity mapping** - LOW/MEDIUM/HIGH/CRITICAL with configurable mappings

### 🎯 Alert Prioritization & Incident Management
- **P1-P4 Priority system** - P1_CRITICAL, P2_HIGH, P3_MEDIUM, P4_LOW based on risk score, severity, confidence
- **Incident grouping** - Automatic grouping by source IP, attack type, time window (configurable)
- **Incident management** - Auto-aggregation with event count, first/last seen, aggregated risk score
- **Threat tagging** - Known Malicious, Suspicious, Unknown, Trusted with visual badges

### ⚙️ Configurable Detection & Response
- **Threshold tuning** - LOW/BALANCED/HIGH sensitivity modes with per-class thresholds
- **Automated response** - DETECT → SCORE → VERIFY → RESPOND → LOG pipeline
- **Response policies** - Configurable rules with dry-run mode, approval workflows, rollback timers
- **Automated actions** - LOG_ONLY, CREATE_ALERT, NOTIFY_SOC, QUARANTINE_HOST, BLOCK_IP, RATE_LIMIT, ISOLATE_NETWORK

### 🔧 Self-Healing & Model Health
- **Concept drift detection** - Population Stability Index (PSI), Kolmogorov-Smirnov test, prediction distribution shift (Chi-square)
- **Model health states** - NORMAL / WATCH / DRIFT_DETECTED with configurable thresholds
- **Automatic recovery** - Rollback blocks, quarantine releases, rate limit removal with verification
- **Performance tracking** - Accuracy, F1, MCC tracking over time

### 📊 Deployment Monitoring & Metrics
- **Latency tracking** - P50/P95/P99 inference latency (ms)
- **Throughput** - flows/sec, packets/sec, bytes/sec, alerts/minute
- **System resources** - CPU%, memory MB/%, disk I/O, network I/O
- **Detection metrics** - TP/FP/TN/FN, accuracy, precision, recall, F1, FPR, FNR, MCC
- **Real-time dashboard** - Live packet stream with detection correlation

### 🖥️ Modern SOC Dashboard (Electron + React + TypeScript)
- **Real-time dashboard** - Live packet stream with detection correlation badges
- **Zoom controls** - +/-/Reset zoom (0.6x-2.0x) with localStorage persistence
- **System Health** - CPU, memory, disk, network, GPU telemetry with sparklines
- **Alert management** - P1-P4 priority badges, threat tags, SHAP explanation cards
- **Zoom controls** - +/-/Reset with localStorage persistence, default 0.93x
- **Dark/Light theme** - Tailwind CSS with CSS variables

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        SOC Platform                              │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (Electron + React + TypeScript + Tailwind)           │
│  ├── Dashboard, Alerts, Flows, System Health, Experiment Dash  │
│  └── WebSocket → Real-time alerts & packets                    │
├─────────────────────────────────────────────────────────────────┤
│  Backend (FastAPI + Python)                                    │
│  ├── FastAPI REST API + WebSocket (/ws/alerts)                 │
│  ├── ML Pipeline (scikit-learn, pandas, numpy)                 │
│  ├── Packet Capture (scapy) → Flow Manager → Detection        │
│  ├── ML Pipeline (StandardScaler → PCA → RandomForest/KNN)     │
│  ├── SHAP Explainer (TreeSHAP/KernelSHAP)                     │
│  ├── Automated Response Engine (policy-based)                  │
│  ├── Model Health Monitor (PSI, KS test, drift detection)      │
│  ├── Automated Response Engine (policy-based)                  │
│  ├── Self-Healing Recovery (rollback, verification)            │
│  └── SQLite/PostgreSQL (SQLAlchemy)                            │
├─────────────────────────────────────────────────────────────────┤
│  Desktop (Electron + Vite)                                     │
│  ├── Single executable (PyInstaller + electron-builder)        │
│  ├── Auto-updates, auto-start, system tray                     │
│  └── Per-user data (%LOCALAPPDATA%\SOC-Platform)               │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- Windows 10/11 (primary target), Linux/macOS supported

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd ids-platform

# Backend setup
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install

# Build desktop app (optional)
cd ../desktop
npm install
npm run dist
```

### Running

```bash
# Development mode (frontend + backend)
# Terminal 1 - Backend
cd backend
.\venv\Scripts\activate
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev

# Terminal 3 - Electron (optional)
cd desktop
npm run dev
```

### Packaged Desktop App
```bash
cd desktop
npm run build       # Creates installer in desktop/release/
npm run pack:dir    # Unpacked directory for testing
```

## Project Structure

```
ids-platform/
├── backend/                 # FastAPI backend + ML pipeline
│   ├── ml/                  # ML pipeline (training, evaluation, SHAP, etc.)
    │   ├── training.py       # SMOTE-safe training pipeline
    │   ├── evaluation.py     # MCC, FPR/FNR, PR-AUC, etc.
    │   ├── cross_dataset.py  # Cross-dataset generalization
    │   ├── unseen_detection.py # Leave-one-class-out
    │   ├── shap_explainer.py # SHAP integration
    │   ├── automated_response.py # Response engine
    │   ├── self_healing.py  # Recovery mechanisms
    │   ├── model_health.py  # PSI, KS test, drift detection
    │   └── ...
│   ├── api/                  # FastAPI routes
│   ├── services/            # Capture, alert, prediction services
│   └── database/            # SQLAlchemy models
├── frontend/                # React + TypeScript + Tailwind
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── pages/           # Dashboard, Alerts, SystemHealth, Experiments
│   │   ├── components/alerts/LivePacketsFeed.tsx  # Live packets with detection badges
│   │   ├── components/layout/TopNav.tsx           # Zoom controls
│   │   └── hooks/useDeploymentMetrics.ts
├── desktop/                 # Electron + Vite + electron-builder
│   ├── src/main.cjs         # Main process (spawns Python engine)
│   └── electron-builder.yml
├── desktop/                 # Electron + Vite
├── docs/                    # Documentation
├── scripts/                 # Training, deployment scripts
├── data/                    # Datasets (CIC-IDS2017, etc.)
├── models/                  # Trained model artifacts
├── cacheclean.bat           # Cache cleanup script
├── .gitignore               # Git ignore rules
└── README.md                # This file
```

## Research Contributions

This platform implements **5 major research contributions**:

1. **Leakage-Safe, Imbalance-Aware IDS Evaluation**
   - Correct SMOTE application (train-only)
   - Macro-F1, FPR/FNR, PR-AUC, MCC metrics
   - Minority class analysis

2. **Cross-Dataset & Unseen-Attack Validation**
   - CIC-IDS2017 retained as baseline
   - UNSW-NB15 cross-dataset evaluation
   - Leave-one-class-out unseen attack experiments
   - Quantified generalization degradation

3. **Explainable Confidence-Aware Risk Scoring**
   - Actual SHAP explanations (TreeSHAP/KernelSHAP)
   - Confidence (model certainty) vs Risk Score (operational risk)
   - Severity levels: LOW/MEDIUM/HIGH/CRITICAL
   - Per-prediction explanations in UI

2. **Risk-Based SOC Alert Prioritization & Controlled Response**
   - P1-P4 priority system with risk scoring
   - Incident aggregation (100 port scans → 1 incident)
   - DETECT→SCORE→VERIFY→RESPOND→LOG pipeline
   - Dry-run mode, approval workflows, rollback timers

5. **Deployment-Aware Continuous IDS Evaluation**
   - Real-time latency (P50/P95/P99), throughput, CPU/memory
   - Concept drift monitoring (PSI, KS test)
   - Robustness testing (noise, scaling, missing features, OOD)
   - Continuous monitoring with time windows (1m/5m/15m/1h/24h)

## Configuration

Key configuration files:
- `.env` - Environment variables (database, API keys, secrets)
- `.env.example` - Template for environment variables
- `backend/core/config.py` - Pydantic Settings (all config)
- `desktop/electron-builder.yml` - Electron build config
- `frontend/tailwind.config.js` - Tailwind theme
- `desktop/electron-builder.yml` - Electron build config

## Scripts

```bash
# Training
python -m backend.ml.training          # Train all models
python -m backend.ml.train_one --model random_forest

# Evaluation
python -m backend.ml.evaluation        # Full evaluation suite

# Experiments
python -m backend.ml.experiment_framework  # Run experiment suite

# Deployment metrics
python -m backend.ml.deployment_metrics

# Cache cleanup
.\cacheclean.bat
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |
| GET | `/system/health` | Extended health (model, DB, alerts/min) |
| GET | `/system/stats` | OS telemetry (CPU, mem, disk, net, GPU) |
| GET | `/alerts` | Paginated alerts with filters |
| GET | `/alerts/latest` | Latest N alerts |
| GET | `/flows` | Network flows with pagination |
| GET | `/statistics` | Threat counts, trends, accuracy |
| GET | `/system/health` | System health |
| GET | `/deployment/metrics` | Deployment metrics (latency, throughput, etc.) |
| WS | `/ws/alerts` | Real-time alerts & packets |

## License

MIT License - see LICENSE file for details.

## Citation

If you use this platform in research, please cite:

```bibtex
@software{soc_platform,
  title = {SOC Platform: Research-Grade Network Intrusion Detection System},
  author = {SOC Platform Team},
  year = {2026},
  url = {https://github.com/your-org/soc-platform}
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest backend/tests/` and `npm test` in frontend
5. Submit a PR

## Support

- Issues: GitHub Issues
- Documentation: `/docs` directory
- Security: Report vulnerabilities to security@your-org.com

---

**Built with scientific rigor, operational practicality, and deployment reality in mind.**