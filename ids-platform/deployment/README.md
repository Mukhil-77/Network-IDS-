# Deployment

Docker Compose deployment for the AI-Powered SOC Platform, matching the
service layout documented in `originalsetup.pdf`:

| Service        | Image/Base        | Ports       | Profile        |
| -------------- | ----------------- | ----------- | -------------- |
| postgres       | postgres:16-alpine| 5432        | always         |
| redis          | redis:7-alpine    | 6379        | with-cache     |
| backend        | python:3.14-slim  | 8000        | always         |
| frontend       | nginx:1.27-alpine | 80, 443     | always         |
| prometheus     | prom/prometheus   | 9090        | monitoring     |
| grafana        | grafana/grafana   | 3001        | monitoring     |
| elasticsearch  | elasticsearch:8.12.0 | 9200     | with-elk       |
| logstash       | logstash:8.12.0   | 5000, 9600  | with-elk       |
| kibana         | kibana:8.12.0     | 5601        | with-elk       |
| filebeat       | filebeat:8.12.0   | -           | with-elk       |

## Usage

```bash
cd deployment

# Core stack only (postgres + backend + frontend)
docker compose up -d --build

# Add monitoring (Prometheus on :9090, Grafana on :3001)
docker compose --profile monitoring up -d --build

# Add caching (Redis)
docker compose --profile with-cache up -d --build

# Add ELK logging (Elasticsearch :9200, Kibana :5601)
docker compose --profile with-elk up -d --build
```

## Layout

```
deployment/
├── docker-compose.yml
├── backend.Dockerfile          # multi-stage: builder -> slim runtime, libpcap, healthcheck
├── frontend.Dockerfile         # multi-stage: node:22-alpine build -> nginx:1.27-alpine serve
├── nginx.Dockerfile            # self-signed SSL cert generator + nginx.conf
├── nginx/
│   └── nginx.conf              # TLS, rate limiting (100 r/s API, 20 r/s WS), headers
├── prometheus.Dockerfile
├── prometheus.yml              # scrapes backend, postgres, node exporters
├── alerts.yml                  # BackendDown, HighThreatRate, HighPredictionLatency, ...
├── grafana.Dockerfile
├── grafana/
│   ├── provisioning/           # datasources (Prometheus + Elasticsearch) + dashboard provider
│   └── dashboards/soc_overview.json
└── logging/
    ├── logstash.conf           # parses backend JSON logs + nginx combined format
    └── filebeat.yml            # ships Docker container logs to Logstash
```

## Scaling

- Backend supports horizontal scaling via `docker compose up --scale backend=3`.
- Database pool: pool_size=10, max_overflow=20 (see `backend/core/config.py`).
- Uvicorn workers: (2 * CPU_CORES) + 1 (default 4 in `backend.Dockerfile`).

## Monitoring

Prometheus alert rules (`alerts.yml`): BackendDown, HighThreatRate,
HighPredictionLatency, DatabaseConnectionHigh, HighCPUUsage.
Grafana is pre-provisioned with Prometheus + Elasticsearch datasources and
the SOC overview dashboard (`soc_overview.json`).

## Production notes

- Replace the self-signed certificate in `nginx.Dockerfile` with real certs.
- Set `JWT_SECRET_KEY` and a strong `DB_PASSWORD` in the environment.
- Restrict CORS origins (`CORS_ORIGINS`) to your frontend domain.
