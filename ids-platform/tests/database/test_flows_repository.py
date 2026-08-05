"""Tests for FlowRepository."""

from datetime import datetime, timezone

from backend.database.models import FlowHistory
from backend.database.repositories.flows import FlowFilters, FlowRepository


def make_flow(flow_id, source_ip="10.0.0.1", protocol="TCP"):
    return FlowHistory(
        id=flow_id, protocol=protocol, source_ip=source_ip, destination_ip="10.0.0.2",
        source_port=5000, destination_port=80,
        start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc),
        packet_count=3, byte_count=300,
    )


def test_create_and_get(db_session):
    repo = FlowRepository(db_session)
    repo.create(make_flow("flow-1"))
    db_session.commit()

    fetched = repo.get("flow-1")
    assert fetched is not None
    assert fetched.source_ip == "10.0.0.1"


def test_list_filters_by_protocol(db_session):
    repo = FlowRepository(db_session)
    repo.create(make_flow("f1", protocol="TCP"))
    repo.create(make_flow("f2", protocol="UDP"))
    db_session.commit()

    result = repo.list(filters=FlowFilters(protocol="UDP"))
    assert result.total == 1
    assert result.items[0].protocol == "UDP"


def test_list_filters_by_source_ip(db_session):
    repo = FlowRepository(db_session)
    repo.create(make_flow("f1", source_ip="1.1.1.1"))
    repo.create(make_flow("f2", source_ip="2.2.2.2"))
    db_session.commit()

    result = repo.list(filters=FlowFilters(source_ip="2.2.2.2"))
    assert result.total == 1


def test_list_pagination(db_session):
    repo = FlowRepository(db_session)
    for i in range(4):
        repo.create(make_flow(f"f{i}"))
    db_session.commit()

    page = repo.list(page=1, page_size=2)
    assert page.total == 4
    assert len(page.items) == 2
