from datetime import datetime, timedelta, timezone
from app.models import Device, Event, Incident, IncidentEscalation, User
from app.engines.correlation.correlation_engine import CorrelationEngine
from app.services.incident_lifecycle import IncidentLifecycleService


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_incident_lifecycle_transitions_and_invalid_blocks(client, db):
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")

    inc = Incident(
        incident_number="INC-5-LC-001",
        title="Lifecycle Test Incident",
        description="Testing state machine",
        severity="high",
        priority="P2",
        status="DETECTED",
        lifecycle_state="NEW",
    )
    db.add(inc)
    db.commit()

    # Viewer cannot transition
    assert client.post(
        f"/api/v1/incidents/{inc.id}/transition",
        json={"target_state": "ACKNOWLEDGED"},
        headers={"Authorization": f"Bearer {viewer_tok}"},
    ).status_code == 403

    # Invalid transition NEW -> CLOSED rejected
    assert client.post(
        f"/api/v1/incidents/{inc.id}/transition",
        json={"target_state": "CLOSED"},
        headers={"Authorization": f"Bearer {eng_tok}"},
    ).status_code == 400

    # Valid path: NEW -> ACKNOWLEDGED -> IN_PROGRESS -> MITIGATED -> RESOLVED -> CLOSED
    for state in ["ACKNOWLEDGED", "IN_PROGRESS", "MITIGATED", "RESOLVED", "CLOSED"]:
        r = client.post(
            f"/api/v1/incidents/{inc.id}/transition",
            json={"target_state": state, "reason": f"Moving to {state}"},
            headers={"Authorization": f"Bearer {eng_tok}"},
        )
        assert r.status_code == 200
        assert r.json()["lifecycle_state"] == state

    # Closed is terminal
    assert client.post(
        f"/api/v1/incidents/{inc.id}/transition",
        json={"target_state": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {admin_tok}"},
    ).status_code == 400


def test_incident_assignment_notes_and_timeline(client, db):
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")

    inc = Incident(
        incident_number="INC-5-ASGN-001",
        title="Assignment & Notes Test",
        description="Testing assignment",
        severity="critical",
        priority="P2",
        status="DETECTED",
        lifecycle_state="NEW",
    )
    db.add(inc)
    db.commit()

    # Engineer cannot assign (admin-only)
    assert client.post(
        f"/api/v1/incidents/{inc.id}/assign",
        json={"assigned_to": "neteng", "priority": "P1"},
        headers={"Authorization": f"Bearer {eng_tok}"},
    ).status_code == 403

    # Cannot assign to viewer ('auditor') or nonexistent user
    assert client.post(
        f"/api/v1/incidents/{inc.id}/assign",
        json={"assigned_to": "auditor"},
        headers={"Authorization": f"Bearer {admin_tok}"},
    ).status_code == 400

    # Valid assignment + priority update
    res_assign = client.post(
        f"/api/v1/incidents/{inc.id}/assign",
        json={"assigned_to": "neteng", "priority": "P1"},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert res_assign.status_code == 200
    assert res_assign.json()["assigned_to"] == "neteng"
    assert res_assign.json()["priority"] == "P1"

    # Engineer adds investigation note
    res_note = client.post(
        f"/api/v1/incidents/{inc.id}/notes",
        json={"content": "Checked trunk Gi0/1 and verified BGP neighbor state."},
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert res_note.status_code == 200

    # Timeline contains assignment, priority change, and note
    res_tl = client.get(
        f"/api/v1/incidents/{inc.id}/timeline",
        headers={"Authorization": f"Bearer {viewer_tok}"},
    )
    assert res_tl.status_code == 200
    actions = [a["action"] for a in res_tl.json()]
    assert "INCIDENT_ASSIGNED" in actions
    assert "PRIORITY_CHANGED" in actions
    assert "INVESTIGATION_NOTE_ADDED" in actions


def test_escalation_policy_no_duplicate_per_level(db):
    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    inc = Incident(
        incident_number="INC-5-ESC-001",
        title="Critical Unacknowledged Incident",
        description="Escalation test",
        severity="critical",
        priority="P1",
        status="DETECTED",
        lifecycle_state="NEW",
        created_at=old_time,
    )
    db.add(inc)
    db.commit()

    esc1 = IncidentLifecycleService.evaluate_escalations(db)
    assert any(e.incident_id == inc.id for e in esc1)

    # Second run must NOT create a duplicate level 1 escalation
    esc2 = IncidentLifecycleService.evaluate_escalations(db)
    assert not any(e.incident_id == inc.id for e in esc2)
    assert db.query(IncidentEscalation).filter(IncidentEscalation.incident_id == inc.id).count() == 1


def test_unrelated_events_on_same_device_not_merged(db):
    dev = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()
    ev1 = Event(
        source_type="device",
        source_id=dev.id,
        source_name=dev.hostname,
        event_type="HIGH_CPU",
        severity="CRITICAL",
        message="%SYS-1-CPUHOG: High CPU on SW-CORE-01",
        correlation_id="CORR-CPU-TEST",
    )
    db.add(ev1)
    db.flush()
    inc1 = CorrelationEngine.correlate_event(db, ev1)

    ev2 = Event(
        source_type="device",
        source_id=dev.id,
        source_name=dev.hostname,
        event_type="MEMORY_PRESSURE",
        severity="CRITICAL",
        message="%SYS-1-MEMCRIT: Memory pressure on SW-CORE-01",
        correlation_id="CORR-MEM-TEST",
    )
    db.add(ev2)
    db.flush()
    inc2 = CorrelationEngine.correlate_event(db, ev2)

    assert inc1.id != inc2.id
