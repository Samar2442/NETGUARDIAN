from datetime import datetime, timezone
from app.models import Device, Event, NetworkLink, CampusService
from app.engines.correlation.correlation_engine import CorrelationEngine
from app.engines.diagnosis.rca_engine import RootCauseAnalysisEngine
from app.engines.digital_twin.digital_twin_engine import DigitalTwinEngine
from app.services.fault_injection_engine import FaultInjectionEngine
from app.services.service_intelligence import ServiceIntelligenceEngine


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_digital_twin_state_classification_and_before_after_comparison(client, db):
    ServiceIntelligenceEngine.seed_campus_services(db)
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")

    # Topology includes state_classification and health_summary
    topo = DigitalTwinEngine.get_topology_payload(db, include_endpoints=False)
    assert topo["state_classification"] in ("SIMULATED", "RECOVERY_VERIFIED")
    assert "health_summary" in topo
    assert len(topo["health_summary"]["vlans"]) == 3
    assert len(topo["health_summary"]["services"]) == 7

    # RBAC on /simulator/compare: viewer -> 403, engineer -> 200
    assert client.post(
        "/api/v1/simulator/compare",
        json={"scenario_type": "uplink_failure", "target_name": "SW-IT-01"},
        headers={"Authorization": f"Bearer {viewer_tok}"},
    ).status_code == 403

    comp = client.post(
        "/api/v1/simulator/compare",
        json={"scenario_type": "uplink_failure", "target_name": "SW-IT-01"},
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert comp.status_code == 200
    body = comp.json()
    assert body["before_state"]["state_classification"] in ("SIMULATED", "RECOVERY_VERIFIED")
    pred = body["predicted_after_state"]
    assert pred["state_classification"] == "PREDICTED"
    assert "before_state" in pred and "after_state" in pred
    assert pred["before_state"]["classification"] == "SIMULATED"
    assert pred["after_state"]["classification"] == "PREDICTED"
    assert "SW-IT-01" in pred["affected_devices"]


def test_end_to_end_it_uplink_failure_rca_twin_and_recovery_verified(client, db):
    ServiceIntelligenceEngine.seed_campus_services(db)
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")

    it_sw = db.query(Device).filter(Device.hostname == "SW-IT-01").first()
    link = db.query(NetworkLink).filter(
        (NetworkLink.source_device_id == it_sw.id) | (NetworkLink.target_device_id == it_sw.id)
    ).first()
    assert it_sw is not None and link is not None

    # 1. Inject uplink failure on SW-IT-01
    inj = FaultInjectionEngine.inject_fault(
        db=db,
        scenario_type="LINK_FAILURE",
        target_device_id="SW-IT-01",
        target_link_id=link.id,
        created_by="admin",
    )

    # 2. Correlate & run RCA
    ev = Event(
        event_type="LINK_DOWN",
        event_code="%LINK-3-UPDOWN",
        severity="HIGH",
        source_type="device",
        source_id=it_sw.id,
        source_name=it_sw.hostname,
        device_id=it_sw.id,
        vlan_id=20,
        message="SW-IT-01 uplink down",
        timestamp=datetime.now(timezone.utc),
    )
    db.add(ev)
    db.flush()
    inc = CorrelationEngine.correlate_event(db, ev)
    diag = RootCauseAnalysisEngine.diagnose_incident(db, inc)
    assert diag.status == "CONFIRMED"
    assert diag.category == "link_failure"

    # 3. Digital Twin predicts affected segment
    pred = DigitalTwinEngine.simulate_failure(db, "switch_failure", "SW-IT-01")
    assert pred["state_classification"] == "PREDICTED"
    assert len(pred["affected_endpoints"]) > 0

    # 4. Recover fault -> Digital Twin transitions to RECOVERY_VERIFIED
    FaultInjectionEngine.recover_fault(db, inj["fault"].id, recovered_by="admin")
    ev.resolved = True
    db.commit()

    rec = client.get(
        "/api/v1/simulator/recovery-status?target_name=SW-IT-01",
        headers={"Authorization": f"Bearer {viewer_tok}"},
    )
    assert rec.status_code == 200
    assert rec.json()["state_classification"] == "RECOVERY_VERIFIED"
