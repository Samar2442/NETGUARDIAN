import pytest
from app.models import RemediationProposal, Incident, Device, NetworkInterface
from app.engines.remediation.remediation_engine import RemediationEngine
from app.engines.rollback.rollback_engine import RollbackEngine

def test_remediation_approval_and_execution_lifecycle(db):
    sw = db.query(Device).filter(Device.hostname == "HQ-Access-SW-02").first()
    trunk = db.query(NetworkInterface).filter(
        NetworkInterface.device_id == sw.id,
        NetworkInterface.name == "GigabitEthernet0/1"
    ).first()

    # Pre-condition: VLAN 30 is missing
    trunk.allowed_vlans = "1,10,20,99"
    db.commit()

    inc = Incident(
        incident_number="TEST-INC-REM-01",
        title="Trunk VLAN 30 Missing",
        description="Remediation lifecycle test",
        severity="high",
        status="ROOT_CAUSE_IDENTIFIED",
        source_device_id=sw.id,
        source_device_name=sw.hostname
    )
    db.add(inc)
    db.commit()

    prop = RemediationProposal(
        incident_id=inc.id,
        device_id=sw.id,
        title="Restore VLAN 30 on Gi0/1",
        target_interface="GigabitEthernet0/1",
        proposed_commands="interface GigabitEthernet0/1\n switchport trunk allowed vlan add 30",
        rollback_commands="interface GigabitEthernet0/1\n switchport trunk allowed vlan remove 30",
        risk_level="low",
        expected_result="VLAN 30 traffic restored",
        status="PENDING_APPROVAL"
    )
    db.add(prop)
    db.commit()

    # Step 1: Admin Approval
    approved_prop = RemediationEngine.approve_proposal(db, prop.id, approved_by="admin")
    assert approved_prop.status == "APPROVED"
    assert inc.status == "APPROVED"

    # Step 2: Execute Remediation (with backup & verification)
    exec_result = RemediationEngine.execute_remediation(db, prop.id, executed_by="admin")
    assert exec_result["success"] is True
    assert exec_result["status"] == "RESOLVED"
    assert approved_prop.status == "VERIFIED"
    assert "30" in trunk.allowed_vlans

    # Step 3: Rollback
    rollback_result = RollbackEngine.execute_rollback(db, approved_prop, username="admin")
    assert rollback_result["success"] is True
    assert approved_prop.status == "ROLLED_BACK"
    assert "30" not in trunk.allowed_vlans

    # Restore clean state
    trunk.allowed_vlans = "1,10,20,30,99"
    db.commit()
