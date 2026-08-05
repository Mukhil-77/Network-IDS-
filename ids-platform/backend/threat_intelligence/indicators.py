"""Shared data types for the threat intelligence framework - no logic here, just the vocabulary every other module in this package speaks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ThreatTag(str, Enum):
    """The four tags the spec requires every alert to be classified into."""

    KNOWN_MALICIOUS = "Known Malicious"
    SUSPICIOUS = "Suspicious"
    UNKNOWN = "Unknown"
    TRUSTED = "Trusted"


class IndicatorType(str, Enum):
    IP = "ip"
    DOMAIN = "domain"
    HASH = "hash"


@dataclass(frozen=True)
class ReputationResult:
    """What a ReputationProvider.check() call returns - see reputation.py."""

    tag: ThreatTag
    source: str  # which provider produced this (e.g. "internal", "abuseipdb")
    confidence: float  # 0-100
    notes: str = ""
