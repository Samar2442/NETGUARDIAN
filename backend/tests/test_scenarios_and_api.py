import pytest
from app.api.v1.devices import get_devices
from app.api.v1.topology import get_topology
from app.api.v1.training import get_scenarios, inject_training_fault, grade_diagnosis
from app.api.v1.drift import compare_device_config
from app.models import Device

def test_api_devices_and_topology(db):
    devs = get_devices(db=db)
    assert len(devs) >= 10

    topo = get_topology(db=db)
    assert "nodes" in topo
    assert "edges" in topo
    assert len(topo["nodes"]) >= 10

def test_training_scenarios_and_fault_injection(db):
    scenarios = get_scenarios(db=db)
    assert len(scenarios) >= 5

    # Test fault injection for Acceptance Criteria scenario
    inj_result = inject_training_fault(
        payload={
            "scenario_key": "vlan_30_trunk_missing",
            "username": "admin"
        },
        db=db
    )
    assert inj_result["success"] is True
    assert "HQ-Access-SW-02" in inj_result["target_device"]

    # Test student diagnosis grading
    grade_res = grade_diagnosis(
        payload={
            "expected_root_cause": "VLAN 30 missing from HQ-Access-SW-02 trunk port GigabitEthernet0/1 allowed VLAN list",
            "student_diagnosis": "VLAN 30 is missing and pruned from allowed trunk port Gi0/1 on HQ-Access-SW-02"
        }
    )
    assert grade_res["score"] >= 75

def test_config_drift_api(db):
    sw02 = db.query(Device).filter(Device.hostname == "HQ-Access-SW-02").first()
    assert sw02 is not None

    drift_data = compare_device_config(sw02.id, db=db)
    assert "comparison" in drift_data
    assert "current_config" in drift_data
    assert drift_data["hostname"] == "HQ-Access-SW-02"
