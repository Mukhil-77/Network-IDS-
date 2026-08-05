"""
Unit tests for backend/ml/severity.py.

Run with:
    python -m pytest tests/test_severity.py -v
"""

import json

from backend.ml.severity import (
    DEFAULT_SEVERITY_MAP,
    FALLBACK_SEVERITY,
    Severity,
    build_severity_map,
    get_severity,
    load_severity_overrides,
)


def test_spec_mapping_critical():
    assert get_severity("DDoS") == Severity.CRITICAL
    assert get_severity("Infiltration") == Severity.CRITICAL


def test_spec_mapping_high():
    assert get_severity("DoS") == Severity.HIGH
    assert get_severity("Brute Force") == Severity.HIGH


def test_spec_mapping_medium():
    assert get_severity("Port Scan") == Severity.MEDIUM
    assert get_severity("Bot") == Severity.MEDIUM


def test_spec_mapping_low():
    assert get_severity("BENIGN") == Severity.LOW


def test_every_attack_map_output_has_a_severity():
    # backend.ml.constants.ATTACK_MAP can produce these exact strings;
    # every one of them must resolve to a real severity, not the fallback.
    from backend.ml.constants import ATTACK_MAP

    for attack_label in set(ATTACK_MAP.values()):
        assert attack_label in DEFAULT_SEVERITY_MAP, f"'{attack_label}' has no severity mapping"


def test_unmapped_label_falls_back_safely():
    assert get_severity("SomeBrandNewAttackType") == FALLBACK_SEVERITY


def test_load_severity_overrides_from_file(tmp_path):
    config_path = tmp_path / "severity_overrides.json"
    config_path.write_text(json.dumps({"Port Scan": "Critical"}))

    overrides = load_severity_overrides(config_path)
    assert overrides == {"Port Scan": "Critical"}


def test_load_severity_overrides_missing_file_returns_empty(tmp_path):
    overrides = load_severity_overrides(tmp_path / "does_not_exist.json")
    assert overrides == {}


def test_build_severity_map_applies_overrides(tmp_path):
    config_path = tmp_path / "severity_overrides.json"
    config_path.write_text(json.dumps({"Port Scan": "Critical"}))

    merged = build_severity_map(config_path)
    assert merged["Port Scan"] == "Critical"  # overridden
    assert merged["DDoS"] == Severity.CRITICAL  # untouched default survives
