from datetime import datetime, timedelta, timezone
from app.models import Device, Event, Incident, NetworkLink, DeviceTelemetry
from app.engines.correlation.correlation_engine import CorrelationEngine
from app.engines.diagnosis.rca_engine import RootCauseAnalysisEngine
from app.services.service_intelligence import ServiceIntelligenceEngine
from app.services.fault_injection_engine import FaultInjectionEngine


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_multi_event_correlation_primary_vs_secondary_and_independent(client, db):
    ServiceIntelligenceEngine.seed_campus_services(db)
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")

    core = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()
    dist1 = db.query(Device).filter(Device.hostname == "SW-DIST-01").first()
    cse_sw = db.query(Device).filter(Device.hostname == "SW-CSE-01").first()
    unrelated_srv = db.query(Device).filter(Device.hostname == "SRV-APP-01").first()
    link = db.query(NetworkLink).filter(
        NetworkLink.source_device_id == core.id,
        NetworkLink.target_device_id == dist1.id,
    ).first()

    now = datetime.now(timezone.utc)
    # Inject a real link failure on SW-CORE-01 -> SW-DIST-01 (redundant path exists via SW-DIST-02)
    inj = FaultInjectionEngine.inject_fault(
        db=db,
        scenario_type="LINK_FAILURE",
        target_device_id="SW-DIST-01",
        target_link_id=link.id,
        created_by="admin",
    )
    corr_id = f"corr-rca-{now.timestamp()}"
    ev_primary = Event(
        event_type="LINK_DOWN",
        event_code="%LINK-3-UPDOWN",
        severity="HIGH",
        source_type="device",
        source_id=dist1.id,
        source_name=dist1.hostname,
        device_id=dist1.id,
        correlation_id=corr_id,
        message="Link SW-CORE-01 <-> SW-DIST-01 changed state to down",
        timestamp=now - timedelta(seconds=20),
    )
    db.add(ev_primary)
    db.flush()
    inc = CorrelationEngine.correlate_event(db, ev_primary)

    ev_secondary = Event(
        event_type="PACKET_LOSS",
        event_code="%NET-4-LOSS",
        severity="MEDIUM",
        source_type="device",
        source_id=cse_sw.id,
        source_name=cse_sw.hostname,
        device_id=cse_sw.id,
        vlan_id=10,
        correlation_id=corr_id,
        message="Transient packet loss on SW-CSE-01 during failover",
        timestamp=now - timedelta(seconds=10),
    )
    db.add(ev_secondary)

    # Independent unrelated event on SRV-APP-01
    ev_indep = Event(
        event_type="HIGH_CPU",
        event_code="%SYS-1-CPUHOG",
        severity="WARNING",
        source_type="device",
        source_id=unrelated_srv.id,
        source_name=unrelated_srv.hostname,
        device_id=unrelated_srv.id,
        message="Unrelated CPU spike on SRV-APP-01",
        timestamp=now - timedelta(seconds=5),
    )
    db.add(ev_indep)
    db.commit()

    # RBAC checks: unauthenticated -> 401, viewer -> 403 on POST /run
    assert client.post(f"/api/v1/diagnostics/run?incident_id={inc.id}").status_code == 401
    assert client.post(
        f"/api/v1/diagnostics/run?incident_id={inc.id}",
        headers={"Authorization": f"Bearer {viewer_tok}"},
    ).status_code == 403

    res = client.post(
        f"/api/v1/diagnostics/run?incident_id={inc.id}",
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "CONFIRMED"
    assert body["confidence"] >= 85.0
    assert ev_primary.id in body["related_event_ids"]
    assert ev_secondary.id in body["related_event_ids"]
    assert any(s["event_type"] == "PACKET_LOSS" for s in body["secondary_symptoms"])
    assert any(ind["event_id"] == ev_indep.id for ind in body["independent_failures"])
    assert len(body["timeline"]) >= 2
    assert len(body["candidate_causes"]) >= 1
    assert len(body["affected_services"]) >= 1

    # Verify new RCA sub-endpoints
    v_headers = {"Authorization": f"Bearer {viewer_tok}"}
    assert client.get(f"/api/v1/diagnostics/{inc.id}/evidence", headers=v_headers).status_code == 200
    assert client.get(f"/api/v1/diagnostics/{inc.id}/related-events", headers=v_headers).status_code == 200
    assert client.get(f"/api/v1/diagnostics/{inc.id}/affected-services", headers=v_headers).status_code == 200
    assert client.get(f"/api/v1/diagnostics/{inc.id}/timeline", headers=v_headers).status_code == 200
    assert client.get(f"/api/v1/diagnostics/{inc.id}/candidates", headers=v_headers).status_code == 200

    # Invalid incident reference -> 404
    assert client.get("/api/v1/diagnostics/nonexistent-id/evidence", headers=v_headers).status_code == 404

    FaultInjectionEngine.recover_fault(db, inj["fault"].id, recovered_by="admin")
    ev_primary.resolved = True
    ev_secondary.resolved = True
    ev_indep.resolved = True
    db.commit()


def test_insufficient_evidence_and_uncertain_never_confirmed(db):
    # Incident with zero events and no config/link failures -> INSUFFICIENT_EVIDENCE
    inc_empty = Incident(
        incident_number="INC-6-EMPTY-001",
        title="Empty Telemetry Incident",
        description="No events attached",
        severity="low",
        priority="P4",
        status="DETECTED",
        lifecycle_state="NEW",
    )
    db.add(inc_empty)
    db.commit()

    diag_empty = RootCauseAnalysisEngine.diagnose_incident(db, inc_empty)
    assert diag_empty.status == "INSUFFICIENT_EVIDENCE"
    assert diag_empty.confidence == 0.0
    assert inc_empty.status != "ROOT_CAUSE_IDENTIFIED"

    # Incident with ambiguous/unmatched events -> UNCERTAIN (never CONFIRMED)
    srv = db.query(Device).filter(Device.hostname == "SRV-DNS-01").first()
    inc_ambig = Incident(
        incident_number="INC-6-UNC-001",
        title="Ambiguous Anomaly",
        description="Unclear event",
        severity="medium",
        priority="P3",
        status="DETECTED",
        lifecycle_state="NEW",
        source_device_id=srv.id,
        source_device_name=srv.hostname,
        affected_device_ids=[srv.id],
    )
    db.add(inc_ambig)
    db.flush()
    now = datetime.now(timezone.utc)
    for i in range(2):
        db.add(Event(
            event_type="CONFIG_NOTICE",
            event_code="%SYS-5-NOTICE",
            severity="INFO",
            source_type="device",
            source_id=srv.id,
            source_name=srv.hostname,
            device_id=srv.id,
            incident_id=inc_ambig.id,
            message=f"Minor notice {i}",
            timestamp=now - timedelta(seconds=10 - i),
        ))
    db.commit()

    diag_unc = RootCauseAnalysisEngine.diagnose_incident(db, inc_ambig)
    assert diag_unc.status == "UNCERTAIN"
    assert diag_unc.confidence < 60.0
    assert diag_unc.status != "CONFIRMED"


def test_multiple_candidate_causes_for_resource_and_congestion(db):
    sw = db.query(Device).filter(Device.hostname == "SW-IT-01").first()
    inc = Incident(
        incident_number="INC-6-MULTI-001",
        title="Multi-Symptom IT Switch Degradation",
        description="CPU and packet loss",
        severity="medium",
        priority="P2",
        status="DETECTED",
        lifecycle_state="NEW",
        source_device_id=sw.id,
        source_device_name=sw.hostname,
        affected_device_ids=[sw.id],
    )
    db.add(inc)
    db.flush()
    now = datetime.now(timezone.utc)
    db.add(Event(
        event_type="HIGH_CPU",
        event_code="%SYS-1-CPUHOG",
        severity="HIGH",
        source_type="device",
        source_id=sw.id,
        source_name=sw.hostname,
        device_id=sw.id,
        incident_id=inc.id,
        message="CPU 92%",
        timestamp=now - timedelta(seconds=20),
    ))
    db.add(Event(
        event_type="PACKET_LOSS",
        event_code="%NET-4-LOSS",
        severity="MEDIUM",
        source_type="device",
        source_id=sw.id,
        source_name=sw.hostname,
        device_id=sw.id,
        incident_id=inc.id,
        message="Packet loss 6%",
        timestamp=now - timedelta(seconds=10),
    ))
    db.commit()

    diag = RootCauseAnalysisEngine.diagnose_incident(db, inc)
    assert diag.status == "PROBABLE"
    assert len(diag.candidate_causes) == 2
