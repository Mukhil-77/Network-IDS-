# Backend Dockerfile - multi-stage: builder installs deps, slim runtime runs the API.
# Build context is the project root: docker build -f deployment/backend.Dockerfile .

FROM python:3.14-slim AS builder

WORKDIR /build

# libpcap-dev is needed by scapy for packet capture; gcc for building deps.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpcap-dev gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ---------------- runtime ----------------
FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpcap0.8 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

COPY backend ./backend
COPY models ./models
COPY .env .env.example ./

RUN useradd -m socapp && chown -R socapp:socapp /app
USER socapp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Uvicorn workers: (2 * CPU_CORES) + 1, default 4.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
