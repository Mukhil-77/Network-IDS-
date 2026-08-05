"""Tests for feeds.py's LocalJSONFeedProvider."""

import json

from backend.database.models import ThreatIndicator
from backend.threat_intelligence.feeds import LocalJSONFeedProvider
from backend.threat_intelligence.indicators import ThreatTag


def write_feed(path, indicators):
    path.write_text(json.dumps({"feed_name": "test-feed", "indicators": indicators}))


def test_check_returns_none_for_ip_not_in_feed(tmp_path, db_session):
    write_feed(tmp_path / "feed.json", [])
    provider = LocalJSONFeedProvider(feed_path=tmp_path / "feed.json")
    assert provider.check(db_session, "1.2.3.4") is None


def test_check_returns_matching_indicator(tmp_path, db_session):
    write_feed(tmp_path / "feed.json", [{"value": "1.2.3.4", "tag": "Known Malicious", "confidence": 90.0, "notes": "test"}])
    provider = LocalJSONFeedProvider(feed_path=tmp_path / "feed.json")

    result = provider.check(db_session, "1.2.3.4")
    assert result.tag == ThreatTag.KNOWN_MALICIOUS
    assert result.source == "demo-community-feed"


def test_sync_creates_new_indicators(tmp_path, db_session):
    write_feed(tmp_path / "feed.json", [{"value": "5.6.7.8", "tag": "Suspicious", "confidence": 60.0}])
    provider = LocalJSONFeedProvider(feed_path=tmp_path / "feed.json")

    count = provider.sync(db_session)
    db_session.commit()

    assert count == 1
    row = db_session.query(ThreatIndicator).filter(ThreatIndicator.value == "5.6.7.8").first()
    assert row is not None
    assert row.tag == "Suspicious"


def test_sync_updates_an_existing_indicator_rather_than_duplicating(tmp_path, db_session):
    write_feed(tmp_path / "feed.json", [{"value": "5.6.7.8", "tag": "Suspicious", "confidence": 60.0}])
    provider = LocalJSONFeedProvider(feed_path=tmp_path / "feed.json")
    provider.sync(db_session)
    db_session.commit()

    write_feed(tmp_path / "feed.json", [{"value": "5.6.7.8", "tag": "Known Malicious", "confidence": 99.0}])
    provider.sync(db_session)
    db_session.commit()

    rows = db_session.query(ThreatIndicator).filter(ThreatIndicator.value == "5.6.7.8").all()
    assert len(rows) == 1
    assert rows[0].tag == "Known Malicious"


def test_missing_feed_file_returns_empty_without_raising(tmp_path, db_session):
    provider = LocalJSONFeedProvider(feed_path=tmp_path / "does_not_exist.json")
    assert provider.check(db_session, "1.2.3.4") is None
    assert provider.sync(db_session) == 0
