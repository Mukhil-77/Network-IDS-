"""
Tags a persisted alert with a ThreatTag by checking its source IP against
the reputation registry, and writes that tag onto the Alert row.

Wired as one step of the composite `on_alert_persisted` callback in
main.py's lifespan (alongside response_engine's auto-response trigger,
added in Milestone 8) - every alert gets enriched, not just ones that also
trigger a response.
"""

from __future__ import annotations

from backend.database.connection import session_scope
from backend.database.models import Alert
from backend.threat_intelligence.indicators import ThreatTag
from backend.threat_intelligence.reputation import ReputationRegistry, reputation_registry as default_registry
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def enrich_and_tag(alert_summary: dict, registry: ReputationRegistry = default_registry) -> ThreatTag:
    """
    `alert_summary`: the same plain-dict shape AlertService/ResponseService
    already pass around ({id, severity, attack_type, source_ip, ...}).

    Returns the tag applied, for logging/testing - callers that don't need
    it can ignore the return value.
    """
    with session_scope() as db:
        result = registry.check_ip(db, alert_summary["source_ip"])

        alert_row = db.get(Alert, alert_summary["id"])
        if alert_row is not None:
            alert_row.threat_tag = result.tag.value

    logger.info(
        "Threat intel: alert %s source_ip=%s tagged '%s' (source=%s, confidence=%.0f)",
        alert_summary["id"], alert_summary["source_ip"], result.tag.value, result.source, result.confidence,
    )
    return result.tag
