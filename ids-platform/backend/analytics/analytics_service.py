"""
Composes analytics from three sources, deliberately reusing rather than
recomputing anything that already exists:
    - backend.services.statistics_service (Milestone 6): threats_by_type,
      threats_by_severity, top_source_ips, detection_accuracy, average
      prediction latency.
    - backend.database.repositories.statistics (Milestone 6): threat_count.
    - backend.analytics.trends (this milestone): timeline, top destination
      IPs, heatmap, average response time.
    - backend.analytics.forecasting (this milestone): the trend projection.

No route or service anywhere recomputes "threats by severity" a second
way - this module is purely composition.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.analytics import forecasting, trends
from backend.database.repositories import statistics as stats_repo
from backend.services.statistics_service import StatisticsService

_statistics_service = StatisticsService()


def get_overview(db: Session, timeline_days: int = 30) -> dict:
    base_stats = _statistics_service.get_summary(db)
    timeline = trends.attack_timeline(db, days=timeline_days)

    return {
        "top_attack_types": base_stats["threats_by_type"],
        "attack_timeline": timeline,
        "top_source_ips": base_stats["top_source_ips"],
        "top_destination_ips": trends.top_destination_ips(db),
        "attack_heatmap": trends.attack_heatmap(db, days=timeline_days),
        "severity_distribution": base_stats["threats_by_severity"],
        "detection_accuracy": base_stats["detection_accuracy"],
        # Placeholder, honestly: computing a real false-positive rate needs
        # ground-truth labels for live traffic (an analyst confirming which
        # alerts were wrong) - Milestone 10 doesn't add that labeling
        # workflow, so this reports why the figure isn't available rather
        # than fabricating one. See docs/ANALYTICS.md.
        "false_positive_rate": None,
        # "Detection time" and "prediction latency" are the same
        # underlying measurement (model inference time, Milestone 6) -
        # exposed under both names rather than computed twice.
        "average_detection_time_ms": base_stats["average_prediction_latency_ms"],
        "average_response_time_seconds": trends.average_response_time_seconds(db),
    }


def get_trends(db: Session, timeline_days: int = 30, forecast_days: int = 7) -> dict:
    timeline = trends.attack_timeline(db, days=timeline_days)
    return {
        "attack_timeline": timeline,
        "forecast": forecasting.forecast_next_days(timeline, days_ahead=forecast_days),
    }
