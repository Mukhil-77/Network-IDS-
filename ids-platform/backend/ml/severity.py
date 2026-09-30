"""
Attack Severity Mapping

Maps attack types to severity levels and provides consistent severity scoring.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SeverityLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Attack type to severity mapping
ATTACK_SEVERITY_MAP: Final[dict[str, str]] = {
    "BENIGN": "LOW",
    "UNKNOWN": "HIGH",
    "DoS": "HIGH",
    "DDoS": "CRITICAL",
    "Port Scan": "MEDIUM",
    "Port Scan": "MEDIUM",
    "Brute Force": "HIGH",
    "Web Attack - Brute Force": "HIGH",
    "XSS": "MEDIUM",
    "SQL Injection": "CRITICAL",
    "Infiltration": "CRITICAL",
    "Bot": "HIGH",
    "Heartbleed": "HIGH",
    "Exploit": "CRITICAL",
    "Fuzzer": "MEDIUM",
    "Reconnaissance": "LOW",
    "Analysis": "LOW",
    "Backdoor": "CRITICAL",
    "Shellcode": "CRITICAL",
    "Worms": "CRITICAL",
    "UNKNOWN": "HIGH",
    "Known Malicious": "CRITICAL",
    "Suspicious": "HIGH",
    "Trusted": "LOW",
    "Legitimate": "LOW",
    # NF-UQ-NIDS-v2 labels (from LightGBM model)
    "normal": "LOW",
    "dos": "CRITICAL",
    "port_scan": "MEDIUM",
    "brute_force": "HIGH",
    "web_attack": "HIGH",
    "botnet": "CRITICAL",
    "infiltration": "CRITICAL",
    "anomaly": "HIGH",
    "other": "MEDIUM",
}

# Severity to numeric score (0-1)
SEVERITY_TO_SCORE = {
    "LOW": 0.2,
    "MEDIUM": 0.4,
    "HIGH": 0.7,
    "CRITICAL": 1.0,
}


def get_severity(attack_type: str, severity_map: dict[str, str] | None = None) -> str:
    """Get severity level for an attack type."""
    mapping = severity_map if severity_map is not None else ATTACK_SEVERITY_MAP
    return mapping.get(attack_type, "MEDIUM")


def get_severity_score(severity: str) -> float:
    """Get numeric score (0-1) for a severity level."""
    return {"LOW": 0.2, "MEDIUM": 0.4, "HIGH": 0.7, "CRITICAL": 1.0}.get(severity, 0.4)


def get_severity_color(severity: str) -> str:
    """Get CSS color class for severity level."""
    return {
        "LOW": "text-green-500",
        "MEDIUM": "text-yellow-500",
        "HIGH": "text-orange-500",
        "CRITICAL": "text-red-500",
    }.get(severity, "text-gray-500")


def severity_to_risk_score(severity: str) -> int:
    """Convert severity to base risk score (0-100)."""
    return {
        "LOW": 15,
        "MEDIUM": 40,
        "HIGH": 70,
        "CRITICAL": 95,
    }.get(severity, 40)


def get_risk_level(risk_score: int) -> str:
    """Convert risk score (0-100) to risk level."""
    if risk_score <= 20:
        return "LOW"
    elif risk_score <= 40:
        return "GUARDED"
    elif risk_score <= 60:
        return "MEDIUM"
    elif risk_score <= 80:
        return "HIGH"
    else:
        return "CRITICAL"


def get_risk_color(risk_level: str) -> str:
    """Get CSS color class for risk level."""
    return {
        "LOW": "text-green-500",
        "GUARDED": "text-blue-500",
        "MEDIUM": "text-yellow-500",
        "HIGH": "text-orange-500",
        "CRITICAL": "text-red-500",
    }.get(risk_level, "text-gray-500")


if __name__ == "__main__":
    print("Severity module loaded successfully")