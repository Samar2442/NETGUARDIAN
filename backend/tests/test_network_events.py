from datetime import datetime, timezone
from app.models import Device, Event
from app.services.telemetry_engine import TelemetryEngine


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_cisco_style_event_generation_and_deduplication(db):
    dev = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()
    db.query(Event).filter(Event.source_id == str(dev.id), Event.event_type == "HIGH_CPU", Event.resolved == False).update({"resolved": True})
    db.commit()
    now = datetime.now(timezone.utc)

    ev1 = TelemetryEngine._emit_deduplicated_event(
        db,
        now,
        event_type="HIGH_CPU",
        event_code="%SYS-1-CPUHOG",
        severity="CRITICAL",
        device=dev,
        message=f"%SYS-1-CPUHOG: High CPU utilization detected on {dev.hostname} [SIMULATION].",
        dedup_window_seconds=120,
    )
    db.commit()
    assert ev1 is not None
    assert ev1.event_code == "%SYS-1-CPUHOG"
    assert ev1.correlation_id is not None
    assert ev1.details.get("source") == "SIMULATION"

    # Second identical event within dedup window must be suppressed
    ev2 = TelemetryEngine._emit_deduplicated_event(
        db,
        now,
        event_type="HIGH_CPU",
        event_code="%SYS-1-CPUHOG",
        severity="CRITICAL",
        device=dev,
        message=f"%SYS-1-CPUHOG: High CPU utilization detected on {dev.hostname} [SIMULATION].",
        dedup_window_seconds=120,
    )
    assert ev2 is None
    ev1.resolved = True
    db.commit()


def test_event_acknowledgment_api_and_rbac(client, db):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")

    ev = db.query(Event).first()
    if not ev:
        dev = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()
        ev = TelemetryEngine._emit_deduplicated_event(
            db, datetime.now(timezone.utc), "HIGH_CPU", "%SYS-1-CPUHOG", "WARNING", dev,
            "%SYS-1-CPUHOG: Test event [SIMULATION]."
        )
        db.commit()

    assert client.post(f"/api/v1/events/{ev.id}/acknowledge", headers={"Authorization": f"Bearer {viewer_tok}"}).status_code == 403
    res = client.post(f"/api/v1/events/{ev.id}/acknowledge", headers={"Authorization": f"Bearer {eng_tok}"})
    assert res.status_code == 200
    assert res.json()["acknowledged"] is True
