"""
Packet-throughput snapshot data access.

Nothing in Milestone 6 automatically writes these rows yet (see the
Milestone 6 documentation's "Deferred" note) - the repository and table
exist so a periodic recorder (a natural fit once a long-running capture
process exists) has somewhere to write, without a schema change.
"""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.database.models import PacketStatistics
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class PacketStatisticsRepository:
    def __init__(self, db: Session):
        self.db = db

    def record_snapshot(self, packets_captured: int, bytes_captured: int, active_flows: int, flows_closed: int) -> PacketStatistics:
        snapshot = PacketStatistics(
            packets_captured=packets_captured,
            bytes_captured=bytes_captured,
            active_flows=active_flows,
            flows_closed=flows_closed,
        )
        self.db.add(snapshot)
        self.db.flush()
        logger.info("DB insert: packet_statistics snapshot active_flows=%d packets=%d", active_flows, packets_captured)
        return snapshot

    def get_latest(self) -> PacketStatistics | None:
        stmt = select(PacketStatistics).order_by(desc(PacketStatistics.timestamp)).limit(1)
        return self.db.execute(stmt).scalars().first()

    def list_recent(self, limit: int = 60) -> list[PacketStatistics]:
        stmt = select(PacketStatistics).order_by(desc(PacketStatistics.timestamp)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
