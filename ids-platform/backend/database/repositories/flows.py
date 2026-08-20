"""Flow history data access - backs GET /flows and GET /flows/summary."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.database.models import FlowHistory
from backend.database.repositories.alerts import PageResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FlowFilters:
    source_ip: Optional[str] = None
    destination_ip: Optional[str] = None
    protocol: Optional[str] = None


class FlowRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, flow: FlowHistory) -> FlowHistory:
        self.db.add(flow)
        self.db.flush()
        logger.info("DB insert: flow_history id=%s %s:%d <-> %s:%d", flow.id, flow.source_ip, flow.source_port, flow.destination_ip, flow.destination_port)
        return flow

    def get(self, flow_id: str) -> Optional[FlowHistory]:
        return self.db.get(FlowHistory, flow_id)

    def list(
        self,
        filters: Optional[FlowFilters] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PageResult:
        filters = filters or FlowFilters()
        stmt = select(FlowHistory)

        if filters.source_ip is not None:
            stmt = stmt.where(FlowHistory.source_ip == filters.source_ip)
        if filters.destination_ip is not None:
            stmt = stmt.where(FlowHistory.destination_ip == filters.destination_ip)
        if filters.protocol is not None:
            stmt = stmt.where(FlowHistory.protocol == filters.protocol)

        total = len(self.db.execute(stmt).all())

        page = max(1, page)
        page_size = max(1, min(page_size, 500))
        stmt = stmt.order_by(desc(FlowHistory.start_time)).offset((page - 1) * page_size).limit(page_size)

        items = list(self.db.execute(stmt).scalars().all())
        return PageResult(items=items, total=total, page=page, page_size=page_size)

    def summary(self) -> dict:
        """
        Aggregate totals over the whole flow history: total flows, per-
        protocol flow/packet/byte counts, and top talkers (most active
        source IPs) - the numbers the Flows page's summary cards show.
        """
        rows = list(self.db.execute(select(FlowHistory)).scalars().all())

        total_flows = len(rows)
        total_packets = sum(r.packet_count for r in rows)
        total_bytes = sum(r.byte_count for r in rows)

        per_protocol: dict[str, dict] = {}
        talker_counts: Counter[str] = Counter()
        talker_bytes: Counter[str] = Counter()
        for row in rows:
            bucket = per_protocol.setdefault(row.protocol, {"flows": 0, "packets": 0, "bytes": 0})
            bucket["flows"] += 1
            bucket["packets"] += row.packet_count
            bucket["bytes"] += row.byte_count
            talker_counts[row.source_ip] += 1
            talker_bytes[row.source_ip] += row.byte_count

        top_talkers = [
            {
                "source_ip": ip,
                "flows": talker_counts[ip],
                "bytes": talker_bytes[ip],
            }
            for ip in talker_counts.most_common(10)
        ]

        return {
            "total_flows": total_flows,
            "total_packets": total_packets,
            "total_bytes": total_bytes,
            "per_protocol": per_protocol,
            "top_talkers": top_talkers,
        }
