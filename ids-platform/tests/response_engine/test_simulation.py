"""Tests for simulation.py's safety gate."""

from backend.core.config import get_settings
from backend.response_engine.simulation import is_simulation, resolve_mode


def test_simulation_requested_always_stays_simulation():
    assert resolve_mode("simulation") == "simulation"


def test_live_requested_falls_back_to_simulation_when_flag_disabled(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENABLE_LIVE_RESPONSE_ACTIONS", "false")
    get_settings.cache_clear()
    assert resolve_mode("live") == "simulation"
    get_settings.cache_clear()


def test_live_requested_stays_live_when_flag_enabled(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ENABLE_LIVE_RESPONSE_ACTIONS", "true")
    get_settings.cache_clear()
    assert resolve_mode("live") == "live"
    get_settings.cache_clear()


def test_is_simulation_helper():
    assert is_simulation("simulation") is True
