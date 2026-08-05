"""Tests for AlertRepository."""

from datetime import datetime, timedelta, timezone

from backend.database.models import Alert, FlowHistory
from backend.database.repositories.alerts import AlertFilters, AlertRepository
from backend.database.repositories.flows import FlowRepository


def make_flow(db, flow_id="flow-1"):
    flow = FlowHistory(
        id=flow_id, protocol="TCP", source_ip="10.0.0.1", destination_ip="10.0.0.2",
        source_port=5000, destination_port=80,
        start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc),
        packet_count=3, byte_count=300,
    )
    return FlowRepository(db).create(flow)


def make_alert(db, flow_id="flow-1", attack_type="DoS", severity="High", confidence=95.0, source_ip="10.0.0.1", ts=None):
    alert = Alert(
        attack_type=attack_type, confidence=confidence, severity=severity,
        source_ip=source_ip, destination_ip="10.0.0.2", protocol="TCP", flow_id=flow_id,
        packet_count=3, bytes=300, model_version="v1", processing_time_ms=5.0,
    )
    if ts is not None:
        alert.timestamp = ts
    return AlertRepository(db).create(alert)


def test_create_and_get_alert(db_session):
    make_flow(db_session)
    created = make_alert(db_session)
    db_session.commit()

    fetched = AlertRepository(db_session).get(created.id)
    assert fetched is not None
    assert fetched.attack_type == "DoS"
    assert fetched.severity == "High"


def test_get_returns_none_for_unknown_id(db_session):
    assert AlertRepository(db_session).get("does-not-exist") is None


def test_list_filters_by_attack_type(db_session):
    make_flow(db_session, "f1")
    make_flow(db_session, "f2")
    make_alert(db_session, flow_id="f1", attack_type="DoS")
    make_alert(db_session, flow_id="f2", attack_type="PortScan")
    db_session.commit()

    result = AlertRepository(db_session).list(filters=AlertFilters(attack_type="DoS"))
    assert result.total == 1
    assert result.items[0].attack_type == "DoS"


def test_list_filters_by_severity_and_min_confidence(db_session):
    make_flow(db_session, "f1")
    make_flow(db_session, "f2")
    make_alert(db_session, flow_id="f1", severity="High", confidence=95.0)
    make_alert(db_session, flow_id="f2", severity="High", confidence=40.0)
    db_session.commit()

    result = AlertRepository(db_session).list(filters=AlertFilters(severity="High", min_confidence=90.0))
    assert result.total == 1
    assert result.items[0].confidence == 95.0


def test_list_filters_by_date_range(db_session):
    make_flow(db_session, "f1")
    old_ts = datetime.now(timezone.utc) - timedelta(days=10)
    make_alert(db_session, flow_id="f1", ts=old_ts)
    db_session.commit()

    result = AlertRepository(db_session).list(filters=AlertFilters(start_date=datetime.now(timezone.utc) - timedelta(days=1)))
    assert result.total == 0


def test_list_pagination(db_session):
    for i in range(5):
        make_flow(db_session, f"f{i}")
        make_alert(db_session, flow_id=f"f{i}")
    db_session.commit()

    page1 = AlertRepository(db_session).list(page=1, page_size=2)
    page2 = AlertRepository(db_session).list(page=2, page_size=2)

    assert page1.total == 5
    assert len(page1.items) == 2
    assert len(page2.items) == 2
    assert {a.id for a in page1.items}.isdisjoint({a.id for a in page2.items})


def test_list_sorting_by_confidence(db_session):
    make_flow(db_session, "f1")
    make_flow(db_session, "f2")
    make_alert(db_session, flow_id="f1", confidence=30.0)
    make_alert(db_session, flow_id="f2", confidence=90.0)
    db_session.commit()

    result = AlertRepository(db_session).list(sort_by="confidence", sort_desc=True)
    assert result.items[0].confidence == 90.0

    result_asc = AlertRepository(db_session).list(sort_by="confidence", sort_desc=False)
    assert result_asc.items[0].confidence == 30.0


def test_get_latest_returns_most_recent_first(db_session):
    make_flow(db_session, "f1")
    make_flow(db_session, "f2")
    make_alert(db_session, flow_id="f1", ts=datetime.now(timezone.utc) - timedelta(minutes=10))
    make_alert(db_session, flow_id="f2", ts=datetime.now(timezone.utc))
    db_session.commit()

    latest = AlertRepository(db_session).get_latest(limit=1)
    assert len(latest) == 1
    assert latest[0].flow_id == "f2"


def test_count_since(db_session):
    make_flow(db_session, "f1")
    make_alert(db_session, flow_id="f1", ts=datetime.now(timezone.utc))
    db_session.commit()

    count = AlertRepository(db_session).count_since(datetime.now(timezone.utc) - timedelta(minutes=1))
    assert count == 1
