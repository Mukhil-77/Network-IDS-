# Prometheus Dockerfile - custom config + alert rules.

FROM prom/prometheus:latest

COPY prometheus.yml /etc/prometheus/prometheus.yml
COPY alerts.yml /etc/prometheus/alerts.yml
COPY prometheus.Dockerfile /etc/prometheus/

EXPOSE 9090
