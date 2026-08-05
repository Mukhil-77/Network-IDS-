"""
API-layer response schemas.

`POST /predict` reuses backend.ml.schemas.PredictionRequest/PredictionResponse
directly (see backend/api/routes/predict.py) - no schema is duplicated here
for that endpoint. This file only holds response shapes that are specific
to the HTTP layer itself (root info, health, and the model-info endpoint's
required field subset) and have no equivalent in backend/ml/schemas.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RootResponse(BaseModel):
    """GET / - basic API identification."""

    name: str
    description: str
    version: str
    docs_url: str


class HealthResponse(BaseModel):
    """GET /health - liveness/readiness signal for load balancers, uptime checks, etc."""

    status: str = Field(..., description="'healthy' if the API and model are both usable, else 'degraded'.")
    model_status: str = Field(..., description="'loaded' or 'unavailable'.")
    version: str = Field(..., description="API_VERSION from configuration.")
    uptime_seconds: float = Field(..., ge=0.0, description="Seconds since this process started.")


class ModelInfoResponse(BaseModel):
    """
    GET /model/info - the specific subset of metadata.json the spec asks
    for, reshaped from backend.ml.schemas.ModelMetadata (which carries a
    few additional fields - dataset, project_version - not requested here).
    """

    model_name: str
    version: str = Field(..., description="Model version directory, e.g. 'v1'.")
    training_date: str
    accuracy: float
    num_features: int = Field(..., description="Number of raw input features the model expects.")
    pca_components: int
    sklearn_version: str


class ModelVersionSummary(BaseModel):
    """GET /model/versions - one entry per trained model version on disk."""

    version: str
    model_name: str
    dataset: str = "unknown"
    training_date: str = ""
    accuracy: Optional[float] = None
    pca_components: Optional[int] = None
    active: bool = False


# ---------------------------------------------------------------------------
# Milestone 6: SOC backend schemas
# ---------------------------------------------------------------------------

class AlertResponse(BaseModel):
    """One row from the `alerts` table, in API-response shape."""

    id: str
    timestamp: datetime
    attack_type: str
    confidence: float
    severity: str
    source_ip: str
    destination_ip: str
    protocol: str
    flow_id: str
    packet_count: int
    bytes: int
    status: str
    model_version: str
    processing_time_ms: float
    threat_tag: str = "Unknown"  # set by threat_intelligence/enrichment.py

    model_config = {"from_attributes": True}  # lets Alert.model_validate(<ORM row>) work directly


class PaginatedAlertsResponse(BaseModel):
    items: list[AlertResponse]
    total: int
    page: int
    page_size: int


class FlowHistoryResponse(BaseModel):
    id: str
    protocol: str
    source_ip: str
    destination_ip: str
    source_port: int
    destination_port: int
    start_time: datetime
    end_time: datetime
    packet_count: int
    byte_count: int

    model_config = {"from_attributes": True}


class PaginatedFlowsResponse(BaseModel):
    items: list[FlowHistoryResponse]
    total: int
    page: int
    page_size: int


class ThreatsPerMinutePoint(BaseModel):
    minute: str
    count: int


class TopSourceIP(BaseModel):
    source_ip: str
    count: int


class StatisticsResponse(BaseModel):
    threat_count: int
    threats_per_minute: list[ThreatsPerMinutePoint]
    threats_by_type: dict[str, int]
    threats_by_severity: dict[str, int]
    top_source_ips: list[TopSourceIP]
    detection_accuracy: Optional[float] = Field(
        None, description="The trained model's own evaluated accuracy (not a live-traffic figure - see statistics_service.py)."
    )
    average_prediction_latency_ms: float


class TopAttackResponse(BaseModel):
    attack_type: str
    total_count: int
    last_seen: datetime
    avg_confidence: float

    model_config = {"from_attributes": True}


class SystemHealthResponse(BaseModel):
    """GET /system/health - extended, DB-backed health, distinct from Milestone 4's simpler GET /health."""

    status: str
    model_status: str
    model_version: Optional[str] = None
    active_flows: int
    alerts_last_minute: int
    timestamp: datetime


# ---------------------------------------------------------------------------
# OS-level telemetry (GET /system/stats) - the "task manager" view
# ---------------------------------------------------------------------------

class CpuStatsSchema(BaseModel):
    percent: float
    logical_count: int
    physical_count: int
    per_core_percent: list[float] = []


class MemoryStatsSchema(BaseModel):
    total_bytes: int
    used_bytes: int
    available_bytes: int
    percent: float
    swap_total_bytes: int = 0
    swap_used_bytes: int = 0
    swap_percent: float = 0.0


class DiskStatsSchema(BaseModel):
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float


class NetworkStatsSchema(BaseModel):
    bytes_sent_per_sec: float
    bytes_recv_per_sec: float
    packets_sent_per_sec: float
    packets_recv_per_sec: float


class ProcessStatsSchema(BaseModel):
    cpu_percent: float
    memory_rss_bytes: int
    threads: int


class GpuStatsSchema(BaseModel):
    name: str
    utilization_percent: float
    memory_used_mb: float
    memory_total_mb: float


class SystemStatsResponse(BaseModel):
    """GET /system/stats - one point-in-time OS telemetry snapshot."""

    timestamp: float
    cpu: CpuStatsSchema
    memory: MemoryStatsSchema
    disk: DiskStatsSchema
    network: NetworkStatsSchema
    process: ProcessStatsSchema
    gpu: Optional[GpuStatsSchema] = None


# ---------------------------------------------------------------------------
# Milestone 8: Response Engine schemas
# ---------------------------------------------------------------------------

class ResponseHistoryEntry(BaseModel):
    id: str
    response_group_id: str
    alert_id: str
    action: str
    status: str
    message: Optional[str] = None
    execution_time_ms: float
    operator: str
    mode: str
    rollback_available: bool
    rolled_back: bool
    timestamp: datetime

    model_config = {"from_attributes": True}


class PaginatedResponses(BaseModel):
    items: list[ResponseHistoryEntry]
    total: int
    page: int
    page_size: int


class ResponseExecuteRequest(BaseModel):
    """POST /responses/execute - trigger a response for an existing alert, optionally overriding its policy."""

    alert_id: str
    actions: Optional[list[str]] = Field(None, description="Overrides the severity's configured policy if given.")
    mode: Optional[str] = Field(None, description="'simulation' or 'live' - overrides the global policy setting if given.")


class ResponseRollbackRequest(BaseModel):
    response_id: str


class ResponseRulesResponse(BaseModel):
    simulation_mode: bool
    policies: dict[str, list[str]]
    available_actions: list[str]


class ResponseRulesUpdateRequest(BaseModel):
    simulation_mode: Optional[bool] = None
    policies: Optional[dict[str, list[str]]] = None


# ---------------------------------------------------------------------------
# Milestone 10: Reports, Analytics, Threat Intelligence, Incidents, Notifications
# ---------------------------------------------------------------------------

class ReportGenerateRequest(BaseModel):
    report_type: str = Field(..., description="daily | weekly | monthly | custom | incident | threat_summary | executive_summary")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    incident_id: Optional[str] = None
    format: str = Field("json", description="json | csv | pdf")


class ReportSummary(BaseModel):
    """GET /reports - one entry per available report *type* (this platform generates on demand, not a stored report library - see docs/REPORTS.md)."""

    report_type: str
    title: str
    available_formats: list[str] = ["json", "csv", "pdf"]


class AnalyticsOverviewResponse(BaseModel):
    top_attack_types: dict[str, int]
    attack_timeline: list[dict]
    top_source_ips: list[dict]
    top_destination_ips: list[dict]
    attack_heatmap: list[dict]
    severity_distribution: dict[str, int]
    detection_accuracy: Optional[float]
    false_positive_rate: Optional[float]
    average_detection_time_ms: float
    average_response_time_seconds: Optional[float]


class AnalyticsTrendsResponse(BaseModel):
    attack_timeline: list[dict]
    forecast: list[dict]


class ThreatIndicatorResponse(BaseModel):
    id: str
    value: str
    indicator_type: str
    tag: str
    source: str
    confidence: float
    notes: Optional[str] = None
    added_at: datetime

    model_config = {"from_attributes": True}


class IncidentResponse(BaseModel):
    id: str
    title: str
    description: str
    severity: str
    priority: str
    status: str
    owner: Optional[str] = None
    alert_id: Optional[str] = None
    timeline: list[dict]
    created_by: str
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedIncidents(BaseModel):
    items: list[IncidentResponse]
    total: int
    page: int
    page_size: int


class IncidentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    severity: str
    priority: str = "Medium"
    alert_id: Optional[str] = None


class IncidentUpdateRequest(BaseModel):
    status: Optional[str] = None
    owner: Optional[str] = None
    priority: Optional[str] = None
    note: Optional[str] = None


class NotificationTestRequest(BaseModel):
    severity: str = Field(..., description="Which severity's configured channels to test-fire, e.g. 'Critical'")
    message: str = "This is a test notification from the SOC platform."
