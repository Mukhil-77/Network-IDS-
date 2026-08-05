"""
Structural definitions of which sections belong in each report type - the
"templates" this milestone's folder structure calls for. Not Jinja/HTML
templates (pdf_generator.py builds PDFs programmatically with reportlab,
not by rendering HTML - see that module's docstring for why), but the same
idea: a declarative description of a report's shape, kept separate from
the generation logic that fills it in.
"""

from __future__ import annotations

REPORT_TYPES = ["daily", "weekly", "monthly", "custom", "incident", "threat_summary", "executive_summary"]

# Which top-level sections report_service.py assembles for each report type.
# "overview" = analytics_service.get_overview()'s dict; "top_attacks" =
# response_engine-adjacent attack-statistics rollup; "incidents" = open/
# recent incidents; "responses" = response action summary.
REPORT_SECTIONS: dict[str, list[str]] = {
    "daily": ["overview", "top_attacks"],
    "weekly": ["overview", "top_attacks", "trends"],
    "monthly": ["overview", "top_attacks", "trends", "incidents"],
    "custom": ["overview", "top_attacks", "trends", "incidents", "responses"],
    "incident": ["incident_detail"],
    "threat_summary": ["overview", "top_attacks", "threat_indicators"],
    "executive_summary": ["overview", "trends", "incidents"],  # high-level only - no raw tables
}

REPORT_TITLES: dict[str, str] = {
    "daily": "Daily Threat Report",
    "weekly": "Weekly Threat Report",
    "monthly": "Monthly Threat Report",
    "custom": "Custom Range Threat Report",
    "incident": "Incident Report",
    "threat_summary": "Threat Summary",
    "executive_summary": "Executive Summary",
}
