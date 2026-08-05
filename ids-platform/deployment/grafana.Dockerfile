# Grafana Dockerfile - provisioned datasources (Prometheus + Elasticsearch)
# and the SOC overview dashboard.

FROM grafana/grafana:latest

COPY provisioning/datasources.yml /etc/grafana/provisioning/datasources/datasources.yml
COPY provisioning/dashboards.yml /etc/grafana/provisioning/dashboards/dashboards.yml
COPY dashboards/soc_overview.json /var/lib/grafana/dashboards/soc_overview.json

EXPOSE 3000
