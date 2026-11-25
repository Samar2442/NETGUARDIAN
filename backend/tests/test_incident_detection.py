from app.models import Device, Incident, NetworkLink
from app.services.fault_injection_engine import FaultInjectionEngine


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_fault_triggers_incident_rca_blast_radius_and_recovery(client, db):
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")

    # Inject HIGH_CPU on SW-CORE-01
    res_inj = client.post(
        "/api/v1/simulation/faults",
        json={"scenario_type": "HIGH_CPU", "target_device_id": "SW-CORE-01"},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert res_inj.status_code == 201
    data = res_inj.json()
    fault_id = data["fault_id"]
    assert data["blast_radius"]["target"] == "SW-CORE-01"

    core = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()
    inc = db.query(Incident).filter(
        Incident.source_device_id == core.id,
        Incident.status != "RESOLVED",
    ).order_by(Incident.created_at.desc()).first()
    assert inc is not None

    # Acknowledge incident as engineer
    res_ack = client.post(
        f"/api/v1/incidents/{inc.id}/acknowledge",
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert res_ack.status_code == 200
    assert res_ack.json()["acknowledged_at"] is not None
    assert res_ack.json()["status"] in {"INVESTIGATING", "ROOT_CAUSE_IDENTIFIED"}

    # Recover fault -> verifies recovery & resolves incident
    res_rec = client.post(
        f"/api/v1/simulation/faults/{fault_id}/recover",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert res_rec.status_code == 200
    db.refresh(inc)
    assert inc.status == "RESOLVED"


def test_redundant_link_failure_preserves_connectivity(db):
    dist1 = db.query(Device).filter(Device.hostname == "SW-DIST-01").first()
    core = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()
    link = db.query(NetworkLink).filter(
        NetworkLink.source_device_id == core.id,
        NetworkLink.target_device_id == dist1.id,
    ).first()
    assert link is not None

    res = FaultInjectionEngine.inject_fault(
        db=db,
        scenario_type="LINK_FAILURE",
        target_device_id="SW-DIST-01",
        target_link_id=link.id,
        created_by="admin",
    )
    # Because SW-DIST-01 has redundant link to SW-DIST-02 -> SW-CORE-01, SW-DIST-01 remains online!
    db.refresh(dist1)
    assert dist1.status != "offline"

    FaultInjectionEngine.recover_fault(db, res["fault"].id, recovered_by="admin")
