"""
Database schema (SQLAlchemy ORM models).

Uses portable column types (String for UUIDs, generic JSON, standard
DateTime/Float/Integer) rather than PostgreSQL-only types (e.g. native
UUID, JSONB) so the exact same models work against SQLite in tests without
a second schema to maintain - see database/connection.py's docstring for
why sync SQLAlchemy (not an async ORM) was chosen, consistent with the rest
of this codebase.

Entity relationships (see ER diagram in the Milestone 6 documentation):

    FlowHistory (1) ──── (0..1) Alert
        one flow produces at most one alert (every classified flow gets
        an Alert row today, including BENIGN ones - see alert_service.py -
        but the relationship is modeled as optional since a flow could, in
        principle, be recorded without a resulting alert, e.g. if
        classification fails).

    AttackStatistics, SystemHealth, ModelMetadataRecord, AuditLog, BlockedIP
        standalone tables - rollups/logs/snapshots, not directly
        foreign-keyed to Alert/FlowHistory (they aggregate or record
        system-level state, not a single flow's outcome).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class FlowHistory(Base):
    """One reconstructed network flow (Milestone 5's Flow, persisted)."""

    __tablename__ = "flow_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # == Flow.flow_id
    protocol: Mapped[str] = mapped_column(String(10), index=True)
    source_ip: Mapped[str] = mapped_column(String(45), index=True)  # 45 chars fits IPv6
    destination_ip: Mapped[str] = mapped_column(String(45), index=True)
    source_port: Mapped[int] = mapped_column(Integer)
    destination_port: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    packet_count: Mapped[int] = mapped_column(Integer, default=0)
    byte_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    alert: Mapped["Alert | None"] = relationship(back_populates="flow", uselist=False)


class Alert(Base):
    """One classification result - the spec's required fields, plus a few additive ones (flagged below)."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    attack_type: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    source_ip: Mapped[str] = mapped_column(String(45), index=True)
    destination_ip: Mapped[str] = mapped_column(String(45), index=True)
    protocol: Mapped[str] = mapped_column(String(10))
    flow_id: Mapped[str] = mapped_column(String(36), ForeignKey("flow_history.id"), index=True)
    packet_count: Mapped[int] = mapped_column(Integer, default=0)
    bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)  # new / acknowledged / resolved

    # Additive (not in the spec's required field list, but needed elsewhere
    # in this milestone): model_version supports the ModelMetadata join and
    # per-version accuracy breakdowns; processing_time_ms is what
    # statistics_service's "Average Prediction Latency" stat aggregates.
    model_version: Mapped[str] = mapped_column(String(32), default="unknown")

    # Milestone 10: set by threat_intelligence/enrichment.py - one of
    # ThreatTag's values ("Known Malicious", "Suspicious", "Unknown", "Trusted").
    # Nullable/defaulted so every pre-Milestone-10 row (and any row created
    # before enrichment runs) is well-formed without a backfill.
    threat_tag: Mapped[str] = mapped_column(String(32), default="Unknown")
    processing_time_ms: Mapped[float] = mapped_column(Float, default=0.0)

    flow: Mapped["FlowHistory"] = relationship(back_populates="alert")

    __table_args__ = (
        Index("ix_alerts_attack_severity", "attack_type", "severity"),
        Index("ix_alerts_timestamp_severity", "timestamp", "severity"),
    )


class PacketStatistics(Base):
    """Periodic capture-throughput snapshot (packets/bytes captured, active flows) - see history_service.py."""

    __tablename__ = "packet_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    packets_captured: Mapped[int] = mapped_column(Integer, default=0)
    bytes_captured: Mapped[int] = mapped_column(Integer, default=0)
    active_flows: Mapped[int] = mapped_column(Integer, default=0)
    flows_closed: Mapped[int] = mapped_column(Integer, default=0)


class AttackStatistics(Base):
    """Running per-attack-type rollup, upserted on every alert - powers GET /attacks/top without scanning all alerts."""

    __tablename__ = "attack_statistics"

    attack_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)


class BlockedIP(Base):
    """
    Placeholder table only, per the spec - no enforcement logic exists yet
    (that's Automated Response, a future milestone). This just gives that
    milestone a schema to write into.
    """

    __tablename__ = "blocked_ips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip_address: Mapped[str] = mapped_column(String(45), unique=True, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SystemHealth(Base):
    """Historical health snapshots - GET /system/health both returns a live status and records one of these."""

    __tablename__ = "system_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    status: Mapped[str] = mapped_column(String(16))  # "healthy" / "degraded"
    model_status: Mapped[str] = mapped_column(String(16))  # "loaded" / "unavailable"
    model_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active_flows: Mapped[int] = mapped_column(Integer, default=0)
    alerts_last_minute: Mapped[int] = mapped_column(Integer, default=0)


class ModelMetadataRecord(Base):
    """
    Database copy of metadata.json (see backend.ml.artifacts) for the
    currently- and previously-loaded model versions - lets Alert.model_version
    be joined against training-time accuracy/features without re-reading
    files from disk on every query.
    """

    __tablename__ = "model_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    model_name: Mapped[str] = mapped_column(String(128))
    training_date: Mapped[str] = mapped_column(String(64))
    accuracy: Mapped[float] = mapped_column(Float)
    precision: Mapped[float] = mapped_column(Float)
    recall: Mapped[float] = mapped_column(Float)
    f1_score: Mapped[float] = mapped_column(Float)
    num_features: Mapped[int] = mapped_column(Integer)
    pca_components: Mapped[int] = mapped_column(Integer)
    sklearn_version: Mapped[str] = mapped_column(String(32))
    project_version: Mapped[str] = mapped_column(String(32))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditLog(Base):
    """
    General-purpose system audit trail. Originally added in Milestone 6 for
    system-level events (model loads); Milestone 8 reused it for response
    actions; Milestone 9 extends it (not a new table) for user-attributed
    security events (login, logout, permission changes, etc.) - one audit
    trail for the whole platform, not three.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(64), default="system")  # username, or "system"/"automated" for non-user events
    action: Mapped[str] = mapped_column(String(128), index=True)
    target: Mapped[str | None] = mapped_column(String(128), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Milestone 9 additions - all nullable so every pre-existing call site
    # (backend.response_engine, backend.main's model-metadata sync) keeps
    # working unchanged with these simply left unset.
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="success")  # "success" or "failed"


class ResponseHistory(Base):
    """
    Milestone 8: one row per executed (or rolled-back) response action.

    A single alert triggering a "Critical" policy with 5 actions produces 5
    rows sharing the same `alert_id` and `response_group_id` (the latter is
    additive - not in the spec's required field list, but needed so the API
    can group "everything that happened for this one detection" without a
    fragile timestamp-window query).
    """

    __tablename__ = "response_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    response_group_id: Mapped[str] = mapped_column(String(36), index=True)
    alert_id: Mapped[str] = mapped_column(String(36), ForeignKey("alerts.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)  # success / failed / skipped / rolled_back
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    operator: Mapped[str] = mapped_column(String(64), default="automated")  # "automated" or an analyst identifier
    mode: Mapped[str] = mapped_column(String(16), default="simulation")  # "simulation" or "live"
    rollback_available: Mapped[bool] = mapped_column(Boolean, default=False)
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)


class ThreatIndicator(Base):
    """
    Milestone 10: Known Malicious IP List / Known Bot Networks / IOCs -
    the data threat_intelligence/reputation.py's built-in provider checks
    against. A "future-ready" external feed provider (threat_intelligence/feeds.py)
    can write into this same table, or maintain its own cache entirely -
    the ReputationProvider interface doesn't require it, see that module.
    """

    __tablename__ = "threat_indicators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    value: Mapped[str] = mapped_column(String(255), index=True)  # an IP, CIDR, domain, or hash
    indicator_type: Mapped[str] = mapped_column(String(16), index=True)  # "ip" / "domain" / "hash"
    tag: Mapped[str] = mapped_column(String(32), index=True)  # ThreatTag value - see threat_intelligence/indicators.py
    source: Mapped[str] = mapped_column(String(64), default="internal")  # which provider/feed added this
    confidence: Mapped[float] = mapped_column(Float, default=100.0)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_threat_indicators_value_type", "value", "indicator_type"),)


class Incident(Base):
    """
    Milestone 10: incident management. `timeline` holds the full activity
    log (status changes, assignments, notes) as a JSON list of
    {timestamp, actor, action, note} entries - simpler than a normalized
    child table for what's fundamentally an append-only audit trail
    specific to one incident, and it's never queried independently of its
    parent incident.
    """

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(2000), default="")
    severity: Mapped[str] = mapped_column(String(16), index=True)
    priority: Mapped[str] = mapped_column(String(16), default="Medium", index=True)  # Low/Medium/High/Urgent
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open/assigned/in_progress/resolved/closed
    owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alert_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("alerts.id"), nullable=True, index=True)
    timeline: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
