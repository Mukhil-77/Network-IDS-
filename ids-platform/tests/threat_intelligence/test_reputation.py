"""Tests for reputation.py: the provider framework, registry, and cache."""

from backend.database.models import ThreatIndicator
from backend.threat_intelligence.indicators import ReputationResult, ThreatTag
from backend.threat_intelligence.reputation import ReputationRegistry, StaticIndicatorProvider


def seed_indicator(db, value="1.2.3.4", tag="Known Malicious", source="internal"):
    db.add(ThreatIndicator(value=value, indicator_type="ip", tag=tag, source=source, confidence=90.0))
    db.commit()


class TestStaticIndicatorProvider:
    def test_returns_none_for_an_unknown_ip(self, db_session):
        result = StaticIndicatorProvider().check(db_session, "9.9.9.9")
        assert result is None

    def test_returns_the_tag_for_a_known_indicator(self, db_session):
        seed_indicator(db_session, value="1.2.3.4", tag="Known Malicious")
        result = StaticIndicatorProvider().check(db_session, "1.2.3.4")
        assert result is not None
        assert result.tag == ThreatTag.KNOWN_MALICIOUS


class TestReputationRegistry:
    def test_falls_back_to_unknown_when_no_provider_has_an_opinion(self, db_session):
        registry = ReputationRegistry()
        registry.register_provider(StaticIndicatorProvider())
        result = registry.check_ip(db_session, "9.9.9.9")
        assert result.tag == ThreatTag.UNKNOWN

    def test_first_matching_provider_wins(self, db_session):
        class AlwaysTrusted:
            name = "always-trusted"
            def check(self, db, ip):
                return ReputationResult(tag=ThreatTag.TRUSTED, source="always-trusted", confidence=100.0)

        registry = ReputationRegistry()
        registry.register_provider(AlwaysTrusted())
        registry.register_provider(StaticIndicatorProvider())  # would say "Known Malicious" but never reached
        seed_indicator(db_session, value="1.2.3.4", tag="Known Malicious")

        result = registry.check_ip(db_session, "1.2.3.4")
        assert result.tag == ThreatTag.TRUSTED

    def test_a_provider_that_raises_does_not_break_the_lookup(self, db_session):
        class BrokenProvider:
            name = "broken"
            def check(self, db, ip):
                raise RuntimeError("simulated feed outage")

        registry = ReputationRegistry()
        registry.register_provider(BrokenProvider())
        registry.register_provider(StaticIndicatorProvider())
        seed_indicator(db_session, value="1.2.3.4", tag="Suspicious")

        result = registry.check_ip(db_session, "1.2.3.4")
        assert result.tag == ThreatTag.SUSPICIOUS  # fell through to the working provider

    def test_result_is_cached_and_does_not_requery_on_second_lookup(self, db_session):
        call_count = 0

        class CountingProvider:
            name = "counting"
            def check(self, db, ip):
                nonlocal call_count
                call_count += 1
                return ReputationResult(tag=ThreatTag.SUSPICIOUS, source="counting", confidence=50.0)

        registry = ReputationRegistry(cache_ttl_seconds=60)
        registry.register_provider(CountingProvider())

        registry.check_ip(db_session, "1.2.3.4")
        registry.check_ip(db_session, "1.2.3.4")
        assert call_count == 1  # second call served from cache

    def test_clear_cache_forces_a_fresh_lookup(self, db_session):
        call_count = 0

        class CountingProvider:
            name = "counting"
            def check(self, db, ip):
                nonlocal call_count
                call_count += 1
                return ReputationResult(tag=ThreatTag.SUSPICIOUS, source="counting", confidence=50.0)

        registry = ReputationRegistry(cache_ttl_seconds=60)
        registry.register_provider(CountingProvider())

        registry.check_ip(db_session, "1.2.3.4")
        registry.clear_cache()
        registry.check_ip(db_session, "1.2.3.4")
        assert call_count == 2
