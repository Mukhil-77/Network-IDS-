"""
A worked example of an external-style threat feed, demonstrating the
extension point `reputation.py`'s framework provides - "Threat Feed
Integration" and "allow future providers to be added easily" from the spec.

This project has no API key or outbound network access configured for a
real feed (AbuseIPDB, AlienVault OTX, etc.), so `LocalJSONFeedProvider`
reads a bundled JSON file instead of making an HTTP call - but the
*interface* is identical to what a real feed provider would implement:
`.check(db, ip)`, registered the same way. Swapping this for a real feed
means writing a class that calls the feed's API in `check()` (or, better,
syncs periodically into the same `ThreatIndicator` table via a
`sync()` method like this one, so lookups stay fast and don't depend on
that external API's uptime) - no change needed anywhere else in the app.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import ThreatIndicator
from backend.threat_intelligence.indicators import ReputationResult, ThreatTag
from backend.utils.logger import get_logger

logger = get_logger(__name__)

DEMO_FEED_PATH = Path(__file__).parent / "data" / "demo_feed.json"


class LocalJSONFeedProvider:
    """
    Reads indicators from a local JSON file (standing in for a real feed's
    API response) and can `sync()` them into `ThreatIndicator` so the
    existing `StaticIndicatorProvider` (reputation.py) also benefits from
    them - a real feed provider would do the same sync on a schedule
    (e.g. hourly) rather than re-fetching on every single lookup.
    """

    name = "demo-community-feed"

    def __init__(self, feed_path: Path = DEMO_FEED_PATH):
        self.feed_path = feed_path

    def _load_feed(self) -> list[dict]:
        if not self.feed_path.is_file():
            logger.warning("Feed file not found at %s", self.feed_path)
            return []
        with open(self.feed_path) as f:
            data = json.load(f)
        return data.get("indicators", [])

    def check(self, db: Session, ip: str) -> ReputationResult | None:
        for entry in self._load_feed():
            if entry["value"] == ip:
                return ReputationResult(
                    tag=ThreatTag(entry["tag"]), source=self.name,
                    confidence=entry.get("confidence", 50.0), notes=entry.get("notes", ""),
                )
        return None

    def sync(self, db: Session) -> int:
        """
        Upserts every indicator from the feed file into ThreatIndicator,
        so `StaticIndicatorProvider` can serve them without re-reading this
        file - the pattern a real scheduled feed sync would follow.
        Returns the number of indicators added or updated.
        """
        count = 0
        for entry in self._load_feed():
            existing = db.execute(
                select(ThreatIndicator).where(
                    ThreatIndicator.value == entry["value"], ThreatIndicator.indicator_type == "ip",
                )
            ).scalars().first()

            if existing is not None:
                existing.tag = entry["tag"]
                existing.confidence = entry.get("confidence", 50.0)
                existing.notes = entry.get("notes", "")
                existing.source = self.name
            else:
                db.add(ThreatIndicator(
                    value=entry["value"], indicator_type="ip", tag=entry["tag"],
                    source=self.name, confidence=entry.get("confidence", 50.0), notes=entry.get("notes", ""),
                ))
            count += 1

        logger.info("Synced %d indicator(s) from feed '%s'", count, self.name)
        return count
