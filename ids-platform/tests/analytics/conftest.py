import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.models import Alert, FlowHistory, Base


@pytest.fixture
def db_session():
    db_path = Path(tempfile.mktemp(suffix=".db"))
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    from backend.auth import models as _auth_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        db_path.unlink(missing_ok=True)


def seed_alert(db, alert_id, attack_type="DoS", severity="High", source_ip="10.0.0.1", dest_ip="10.0.0.9", timestamp=None, latency_ms=5.0):
    flow_id = f"flow-{alert_id}"
    db.add(FlowHistory(
        id=flow_id, protocol="TCP", source_ip=source_ip, destination_ip=dest_ip,
        source_port=1, destination_port=2,
        start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc),
        packet_count=1, byte_count=100,
    ))
    alert = Alert(
        id=alert_id, attack_type=attack_type, confidence=90.0, severity=severity,
        source_ip=source_ip, destination_ip=dest_ip, protocol="TCP", flow_id=flow_id,
        packet_count=1, bytes=100, status="new", model_version="v1", processing_time_ms=latency_ms,
    )
    if timestamp is not None:
        alert.timestamp = timestamp
    db.add(alert)
    db.commit()
    return alert
