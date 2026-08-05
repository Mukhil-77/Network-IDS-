"""
Attack type -> severity mapping.

The spec's mapping only covers 6 of the labels backend.ml.constants.ATTACK_MAP
can actually produce (BENIGN, DDoS, DoS, Port Scan, Brute Force, Bot). This
module extends it to cover every label the trained model can output -
Web Attack - Brute Force, XSS, SQL Injection, Heartbleed, UNKNOWN - using
the same judgment call a security analyst would (web/memory-exploit
attacks are Critical; anything genuinely unrecognized defaults to Medium
rather than being silently dropped to Low). These additions are flagged
below; adjust DEFAULT_SEVERITY_MAP freely if your intended ranking differs.

"Configurable" (per the spec) means: the mapping is a plain dict, callers
can pass their own to get_severity()/build_severity_map(), and it can be
overridden at runtime by pointing SEVERITY_CONFIG_PATH at a JSON file -
no code change required to re-rank a label.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class Severity:
    """Severity levels, ordered low to high. Plain string constants (not an Enum) so they serialize directly."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


# --------------------------------------------------------------------------
# Default mapping. Entries above the "--- spec ---" line are exactly as
# given in the Milestone 3 requirements. Entries below are additions
# (flagged in the module docstring) covering every other label
# constants.ATTACK_MAP can produce.
# --------------------------------------------------------------------------
DEFAULT_SEVERITY_MAP: dict[str, str] = {
    # --- spec ---
    "DDoS": Severity.CRITICAL,
    "Infiltration": Severity.CRITICAL,
    "DoS": Severity.HIGH,
    "Brute Force": Severity.HIGH,
    "Port Scan": Severity.MEDIUM,
    "Bot": Severity.MEDIUM,
    "BENIGN": Severity.LOW,
    # --- additions, not in the original spec ---
    "Heartbleed": Severity.CRITICAL,  # memory-disclosure exploit; treated like Infiltration
    "SQL Injection": Severity.CRITICAL,  # can lead to full data compromise
    "XSS": Severity.HIGH,
    "Web Attack - Brute Force": Severity.HIGH,  # matches "Brute Force" above
    "UNKNOWN": Severity.MEDIUM,  # unrecognized traffic: not dismissed as Low, not alarmed as Critical
}

# Fallback for any label neither the default map nor a caller-supplied
# override has an entry for, so get_severity() never raises on an
# unexpected string - it degrades to a safe, visible default instead.
FALLBACK_SEVERITY: str = Severity.MEDIUM

_ENV_VAR_CONFIG_PATH = "SEVERITY_CONFIG_PATH"


def load_severity_overrides(config_path: Optional[str | Path] = None) -> dict[str, str]:
    """
    Load a JSON file of {"AttackLabel": "Severity"} overrides, e.g.:

        {"Port Scan": "High", "Bot": "Critical"}

    Args:
        config_path: Path to the override file. If not given, falls back
            to the `SEVERITY_CONFIG_PATH` environment variable. If neither
            is set, returns an empty dict (defaults only).

    Returns:
        The parsed override dict (empty if no config path is configured).
    """
    resolved = config_path or os.environ.get(_ENV_VAR_CONFIG_PATH)
    if not resolved:
        return {}

    path = Path(resolved)
    if not path.is_file():
        logger.warning("Severity config path '%s' does not exist; using defaults only", path)
        return {}

    overrides = json.loads(path.read_text())
    logger.info("Loaded %d severity override(s) from %s", len(overrides), path)
    return overrides


def build_severity_map(config_path: Optional[str | Path] = None) -> dict[str, str]:
    """Merge DEFAULT_SEVERITY_MAP with any configured overrides (overrides win)."""
    merged = dict(DEFAULT_SEVERITY_MAP)
    merged.update(load_severity_overrides(config_path))
    return merged


def get_severity(attack_label: str, severity_map: Optional[dict[str, str]] = None) -> str:
    """
    Return the severity for a single attack label.

    Args:
        attack_label: The predicted attack type, e.g. "DoS", "BENIGN".
        severity_map: Mapping to use. Defaults to DEFAULT_SEVERITY_MAP if
            not given - pass build_severity_map() explicitly to include
            any configured overrides.

    Returns:
        One of Severity.LOW/MEDIUM/HIGH/CRITICAL. Never raises - an
        unmapped label logs a warning and returns FALLBACK_SEVERITY.
    """
    mapping = severity_map if severity_map is not None else DEFAULT_SEVERITY_MAP
    if attack_label not in mapping:
        logger.warning("No severity mapping for attack label '%s'; defaulting to %s", attack_label, FALLBACK_SEVERITY)
        return FALLBACK_SEVERITY
    return mapping[attack_label]
