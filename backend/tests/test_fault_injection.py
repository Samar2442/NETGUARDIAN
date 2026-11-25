import pytest
from app.models import AuditLog, Device, FaultScenario, NetworkInterface, NetworkLink
from app.services.fault_injection_engine import FaultInjectionEngine, FaultInjectionError


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.mark.parametrize("scenario_type", [
    "HIGH_CPU",
    "MEMORY_PRESSURE",
    "CONGESTION",
    "PACKET_LOSS",
    "INTERFACE_DOWN",
    "DEVICE_OFFLINE",
    "LINK_FAILURE",
])
def test_all_fault_scenarios_and_recovery(db, scenario_type):
    target = "SW-CSE-01" if scenario_type != "HIGH_CPU" else "SW-CORE-01"
    res = FaultInjectionEngine.inject_fault(
        db=db,
        scenario_type=scenario_type,
        target_device_id=target,
        created_by="admin",
    )
    fault = res["fault"]
    assert fault.status == "ACTIVE"
    assert fault.telemetry_source == "SIMULATION"
    assert "NO REAL NETWORK DEVICE IS MODIFIED" in res["simulation_notice"]

    dev = db.query(Device).filter(Device.hostname == target).first()
    if scenario_type == "HIGH_CPU":
        assert dev.cpu_percent >= 90.0
    elif scenario_type == "MEMORY_PRESSURE":
        assert dev.memory_percent >= 90.0
    elif scenario_type == "DEVICE_OFFLINE":
        assert dev.status == "offline"

    # Recover
    rec = FaultInjectionEngine.recover_fault(db, fault.id, recovered_by="admin")
    assert rec["status"] == "RECOVERED"
    db.refresh(dev)
    assert dev.status == "online"


def test_duplicate_active_fault_and_invalid_params_rejected(db):
    res = FaultInjectionEngine.inject_fault(
        db=db,
        scenario_type="HIGH_CPU",
        target_device_id="SW-IT-01",
        created_by="admin",
    )
    fault_id = res["fault"].id

    # Duplicate active fault on same target rejected
    with pytest.raises(FaultInjectionError):
        FaultInjectionEngine.inject_fault(
            db=db,
            scenario_type="HIGH_CPU",
            target_device_id="SW-IT-01",
            created_by="admin",
        )

    # Invalid duration rejected
    with pytest.raises(FaultInjectionError):
        FaultInjectionEngine.inject_fault(
            db=db,
            scenario_type="HIGH_CPU",
            target_device_id="SW-IT-02",
            created_by="admin",
            max_duration_seconds=999999,
        )

    FaultInjectionEngine.recover_fault(db, fault_id, recovered_by="admin")


def test_unauthorized_fault_injection_rejected_and_audit_logged(client, db):
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")

    res_eng = client.post(
        "/api/v1/simulation/faults",
        json={"scenario_type": "HIGH_CPU", "target_device_id": "SW-CORE-01"},
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert res_eng.status_code == 403

    res_admin = client.post(
        "/api/v1/simulation/faults",
        json={"scenario_type": "HIGH_CPU", "target_device_id": "SW-CORE-01"},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert res_admin.status_code == 201
    fid = res_admin.json()["fault_id"]

    assert db.query(AuditLog).filter(AuditLog.action == "FAULT_SIMULATION_STARTED", AuditLog.resource_id == fid).first() is not None

    res_rec = client.post(
        f"/api/v1/simulation/faults/{fid}/recover",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert res_rec.status_code == 200
    assert db.query(AuditLog).filter(AuditLog.action == "FAULT_SIMULATION_RECOVERED", AuditLog.resource_id == fid).first() is not None
