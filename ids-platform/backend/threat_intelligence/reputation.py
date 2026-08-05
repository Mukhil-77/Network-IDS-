"""
The modular reputation-provider framework: "allow future providers to be
added easily" from the spec, done the same way response_engine's action
registry does it - a Protocol every provider implements, plus a registry
any part of the app can query without knowing which providers exist.

Built-in provider: `StaticIndicatorProvider`, checking
`backend.database.models.ThreatIndicator` (Known Malicious IP List / Known
Bot Networks - Milestone 10's seed data, see enrichment.py's docstring).

Adding a real external feed (AbuseIPDB, AlienVault OTX, etc.) means writing
one class implementing `ReputationProvider.check()` and calling
`register_provider()` - see feeds.py for a worked example using a local
file instead of a live external API (this project has no API keys/network
access configured for a real feed, but the integration point is identical
whether the data comes from a file, a database, or an HTTP call).
"""

from __future__ import annotations

import time
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import ThreatIndicator
from backend.threat_intelligence.indicators import ReputationResult, ThreatTag
from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CACHE_TTL_SECONDS = 300  # 5 minutes - long enough to matter under a burst of alerts from the same IP, short enough that a newly-added indicator takes effect promptly


class ReputationProvider(Protocol):
    """Anything with a `.name` and a `.check(db, ip)` method can be registered - see register_provider()."""

    name: str

    def check(self, db: Session, ip: str) -> ReputationResult | None:
        """Returns None if this provider has no opinion about `ip` (not a "don't know" tag - just "ask the next provider")."""
        ...


class _TTLCache:
    """Minimal TTL cache - avoids re-querying (or re-calling an external API, for a real feed provider) for the same IP within the same burst of alerts."""

    def __init__(self, ttl_seconds: float):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, ReputationResult]] = {}

    def get(self, key: str) -> ReputationResult | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: ReputationResult) -> None:
        self._store[key] = (time.monotonic() + self.ttl_seconds, value)

    def clear(self) -> None:
        self._store.clear()


class StaticIndicatorProvider:
    """Checks the database-backed ThreatIndicator table - the built-in "Known Malicious IP List / Known Bot Networks" from the spec."""

    name = "internal"

    def check(self, db: Session, ip: str) -> ReputationResult | None:
        indicator = db.execute(
            select(ThreatIndicator).where(ThreatIndicator.value == ip, ThreatIndicator.indicator_type == "ip")
        ).scalars().first()

        if indicator is None:
            return None

        return ReputationResult(
            tag=ThreatTag(indicator.tag), source=indicator.source,
            confidence=indicator.confidence, notes=indicator.notes or "",
        )


class ReputationRegistry:
    """Queries every registered provider in order, first non-None result wins, with a shared TTL cache in front."""

    def __init__(self, cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS):
        self._providers: list[ReputationProvider] = []
        self._cache = _TTLCache(cache_ttl_seconds)

    def register_provider(self, provider: ReputationProvider) -> None:
        self._providers.append(provider)
        logger.info("Registered threat intelligence provider: %s", provider.name)

    def check_ip(self, db: Session, ip: str) -> ReputationResult:
        """Never returns None - falls back to ThreatTag.UNKNOWN if no provider has an opinion."""
        cached = self._cache.get(ip)
        if cached is not None:
            return cached

        for provider in self._providers:
            try:
                result = provider.check(db, ip)
            except Exception:  # noqa: BLE001 - one provider's failure (e.g. a real feed's network error) must not block the others or crash enrichment
                logger.exception("Threat intelligence provider '%s' raised while checking %s", provider.name, ip)
                continue
            if result is not None:
                self._cache.set(ip, result)
                return result

        fallback = ReputationResult(tag=ThreatTag.UNKNOWN, source="none", confidence=0.0, notes="No provider had information about this IP")
        self._cache.set(ip, fallback)
        return fallback

    def clear_cache(self) -> None:
        self._cache.clear()


# Process-wide instance, with the built-in provider registered by default.
reputation_registry = ReputationRegistry()
reputation_registry.register_provider(StaticIndicatorProvider())
