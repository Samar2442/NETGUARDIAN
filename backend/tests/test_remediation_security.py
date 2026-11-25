import threading
import time
import pytest
from app.core.config import settings
from app.models import Device, Incident, NetworkInterface, RemediationProposal, AuditLog
from app.engines.remediation.command_validator import (
    RemediationOperation,
    ExecutionMode,
    CommandValidationError,
    ApprovalBindingError,
    ExecutionLockError,
    ExecutionModeError,
    DuplicateExecutionError,
    RollbackEligibilityError,
    build_structured_commands,
    validate_cisco_commands,
    validate_interface_name,
    validate_vlan_id,
    device_execution_locks,
)
from app.engines.remediation.remediation_engine import RemediationEngine
from app.engines.rollback.rollback_engine import RollbackEngine
from app.database.migrations import run_safe_migrations
from app.database.session import engine as default_engine


def _create_test_incident_and_device(db):
    dev = db.query(Device).filter(Device.hostname == "HQ-Access-SW-02").first()
    assert dev is not None
    inc = Incident(
        incident_number=f"INC-5A-{int(time.time() * 1000) % 100000}",
        title="Phase 5A Security Test Incident",
        description="Structured remediation test",
        severity="high",
        status="ROOT_CAUSE_IDENTIFIED",
        source_device_id=dev.id,
        source_device_name=dev.hostname,
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return dev, inc


# ==============================================================================
# 1. Command Allowlisting & Injection Prevention Tests
# ==============================================================================

@pytest.mark.parametrize("malicious_cmd", [
    "interface GigabitEthernet0/1; rm -rf /",
    "interface GigabitEthernet0/1\n reload",
    "interface GigabitEthernet0/1\n write erase",
    "username backdoor privilege 15 secret pwned",
    "tclsh\n exec ls",
    "interface GigabitEthernet0/1\n switchport trunk allowed vlan add 30 | cat /etc/passwd",
    "interface GigabitEthernet0/1\n switchport trunk allowed vlan add $(whoami)",
    "interface GigabitEthernet0/1\n switchport trunk allowed vlan add `id`",
    "interface GigabitEthernet0/1 && shutdown",
])
def test_shell_and_command_injection_rejected(malicious_cmd):
    with pytest.raises(CommandValidationError):
        validate_cisco_commands(malicious_cmd)


@pytest.mark.parametrize("bad_vlan", [0, -1, 4095, 9999, "30; shutdown", True, False, "abc"])
def test_invalid_vlan_ids_rejected(bad_vlan):
    with pytest.raises(CommandValidationError):
        validate_vlan_id(bad_vlan)


@pytest.mark.parametrize("bad_iface", [
    "",
    "GigabitEthernet0/1; no shut",
    "../../../etc/passwd",
    "eth0",
    "GigabitEthernet0/1 | include up",
])
def test_invalid_interface_names_rejected(bad_iface):
    with pytest.raises(CommandValidationError):
        validate_interface_name(bad_iface)


def test_configuration_mode_violations_rejected():
    # Interface command without entering interface mode
    with pytest.raises(CommandValidationError):
        validate_cisco_commands("no shutdown")

    # Global VLAN command inside interface mode
    with pytest.raises(CommandValidationError):
        validate_cisco_commands("interface GigabitEthernet0/1\n vlan 30")

    # Mixing EXEC show command after config mode
    with pytest.raises(CommandValidationError):
        validate_cisco_commands("interface GigabitEthernet0/1\n no shutdown\n show vlan id 30")


# ==============================================================================
# 2. Structured Operations (All 10 Supported Operations)
# ==============================================================================

def test_all_10_structured_operations_generate_valid_commands():
    cases = [
        (RemediationOperation.CREATE_VLAN.value, None, {"vlan_id": 30, "vlan_name": "ECE_LAB"}),
        (RemediationOperation.ADD_VLAN_TO_TRUNK.value, "GigabitEthernet0/1", {"vlan_id": 30}),
        (RemediationOperation.REMOVE_VLAN_FROM_TRUNK.value, "GigabitEthernet0/1", {"vlan_id": 30}),
        (RemediationOperation.ENABLE_INTERFACE.value, "GigabitEthernet0/1", {}),
        (RemediationOperation.DISABLE_INTERFACE.value, "GigabitEthernet0/1", {}),
        (RemediationOperation.CONFIGURE_ACCESS_VLAN.value, "GigabitEthernet0/2", {"vlan_id": 20}),
        (RemediationOperation.RESTORE_CONFIG_SNAPSHOT.value, None, {"snapshot_id": "snap_001"}),
        (RemediationOperation.VERIFY_TRUNK_CONFIG.value, "GigabitEthernet0/1", {"vlan_id": 30}),
        (RemediationOperation.VERIFY_VLAN_EXISTS.value, None, {"vlan_id": 30}),
        (RemediationOperation.VERIFY_INTERFACE_STATUS.value, "GigabitEthernet0/1", {}),
    ]
    for op, iface, params in cases:
        proposed, rollback, _, norm = build_structured_commands(op, iface, params)
        validate_cisco_commands(proposed, target_interface=iface)
        validate_cisco_commands(rollback, target_interface=iface, allow_empty=True)
        assert isinstance(norm, dict)


def test_unexpected_or_missing_parameters_rejected():
    with pytest.raises(CommandValidationError):
        build_structured_commands(
            RemediationOperation.ADD_VLAN_TO_TRUNK.value,
            "GigabitEthernet0/1",
            {"vlan_id": 30, "extra_shell": "; reboot"},
        )
    with pytest.raises(CommandValidationError):
        build_structured_commands(
            RemediationOperation.ADD_VLAN_TO_TRUNK.value,
            "GigabitEthernet0/1",
            {},
        )
    with pytest.raises(CommandValidationError):
        build_structured_commands("DROP_DATABASE", "GigabitEthernet0/1", {})


# ==============================================================================
# 3. Approval-to-Execution Cryptographic Binding
# ==============================================================================

def test_approval_digest_binding_detects_post_approval_tampering(db):
    dev, inc = _create_test_incident_and_device(db)
    prop = RemediationEngine.create_structured_proposal(
        db=db,
        incident_id=inc.id,
        device_id=dev.id,
        title="Add VLAN 30 to Gi0/1",
        operation=RemediationOperation.ADD_VLAN_TO_TRUNK.value,
        target_interface="GigabitEthernet0/1",
        parameters={"vlan_id": 30},
    )
    approved = RemediationEngine.approve_proposal(db, prop.id, approved_by="admin")
    assert approved.approval_digest is not None
    assert len(approved.approval_digest) == 64

    # Tamper with parameters after approval!
    approved.parameters = {"vlan_id": 99}
    db.commit()

    with pytest.raises(ApprovalBindingError) as exc:
        RemediationEngine.execute_remediation(db, approved.id, executed_by="neteng")
    assert "digest mismatch" in str(exc.value).lower()

    tamper_audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "REMEDIATION_TAMPER_DETECTED",
            AuditLog.resource_id == approved.id,
        )
        .first()
    )
    assert tamper_audit is not None


def test_unapproved_proposal_execution_rejected(db):
    dev, inc = _create_test_incident_and_device(db)
    prop = RemediationEngine.create_structured_proposal(
        db=db,
        incident_id=inc.id,
        device_id=dev.id,
        title="Unapproved Op",
        operation=RemediationOperation.ENABLE_INTERFACE.value,
        target_interface="GigabitEthernet0/1",
        parameters={},
    )
    with pytest.raises(ApprovalBindingError):
        RemediationEngine.execute_remediation(db, prop.id, executed_by="neteng")


# ==============================================================================
# 4. Execution Safety: Locking, Duplicate Protection, Timeout, Rollback Eligibility
# ==============================================================================

def test_duplicate_execution_blocked(db):
    dev, inc = _create_test_incident_and_device(db)
    trunk = db.query(NetworkInterface).filter(
        NetworkInterface.device_id == dev.id,
        NetworkInterface.name == "GigabitEthernet0/1",
    ).first()
    trunk.allowed_vlans = "1,10,20,99"
    db.commit()

    prop = RemediationEngine.create_structured_proposal(
        db=db,
        incident_id=inc.id,
        device_id=dev.id,
        title="Restore VLAN 30",
        operation=RemediationOperation.ADD_VLAN_TO_TRUNK.value,
        target_interface="GigabitEthernet0/1",
        parameters={"vlan_id": 30},
    )
    RemediationEngine.approve_proposal(db, prop.id, approved_by="admin")
    res = RemediationEngine.execute_remediation(db, prop.id, executed_by="neteng")
    assert res["success"] is True

    # Second execution must be blocked
    with pytest.raises(DuplicateExecutionError):
        RemediationEngine.execute_remediation(db, prop.id, executed_by="neteng")


def test_per_device_execution_lock_prevents_concurrent_execution(db):
    dev, inc = _create_test_incident_and_device(db)
    prop = RemediationEngine.create_structured_proposal(
        db=db,
        incident_id=inc.id,
        device_id=dev.id,
        title="Locked Device Test",
        operation=RemediationOperation.VERIFY_TRUNK_CONFIG.value,
        target_interface="GigabitEthernet0/1",
        parameters={},
    )
    RemediationEngine.approve_proposal(db, prop.id, approved_by="admin")

    # Simulate another thread holding the lock for this device
    with device_execution_locks.acquire(dev.id, timeout=0.5):
        with pytest.raises(ExecutionLockError):
            RemediationEngine.execute_remediation(db, prop.id, executed_by="neteng")


def test_rollback_eligibility_enforced(db):
    dev, inc = _create_test_incident_and_device(db)
    prop = RemediationEngine.create_structured_proposal(
        db=db,
        incident_id=inc.id,
        device_id=dev.id,
        title="Rollback Eligibility Test",
        operation=RemediationOperation.ENABLE_INTERFACE.value,
        target_interface="GigabitEthernet0/1",
        parameters={},
    )
    # Cannot rollback PENDING_APPROVAL
    with pytest.raises(RollbackEligibilityError):
        RollbackEngine.execute_rollback(db, prop, username="admin")


# ==============================================================================
# 5. Execution Modes (SIMULATION, LAB, PRODUCTION)
# ==============================================================================

def test_production_and_unauthorized_lab_modes_rejected(db):
    dev, inc = _create_test_incident_and_device(db)
    prop = RemediationEngine.create_structured_proposal(
        db=db,
        incident_id=inc.id,
        device_id=dev.id,
        title="Mode Guard Test",
        operation=RemediationOperation.VERIFY_INTERFACE_STATUS.value,
        target_interface="GigabitEthernet0/1",
        parameters={},
    )
    RemediationEngine.approve_proposal(db, prop.id, approved_by="admin")

    with pytest.raises(ExecutionModeError):
        RemediationEngine.execute_remediation(
            db, prop.id, executed_by="neteng", execution_mode="PRODUCTION"
        )

    with pytest.raises(ExecutionModeError):
        RemediationEngine.execute_remediation(
            db, prop.id, executed_by="neteng", execution_mode="LAB"
        )


# ==============================================================================
# 6. API Endpoints & Safe Migration
# ==============================================================================

def test_structured_remediation_api_and_rbac(client, db):
    dev, inc = _create_test_incident_and_device(db)

    # Viewer cannot create structured remediation proposal
    viewer_tok = client.post(
        "/api/v1/auth/login",
        json={"username": "auditor", "password": "ViewerAuditor2026!"},
    ).json()["access_token"]
    res_viewer = client.post(
        "/api/v1/remediation",
        json={
            "incident_id": inc.id,
            "device_id": dev.id,
            "title": "Viewer Create",
            "operation": "ENABLE_INTERFACE",
            "target_interface": "GigabitEthernet0/1",
            "parameters": {},
        },
        headers={"Authorization": f"Bearer {viewer_tok}"},
    )
    assert res_viewer.status_code == 403

    # Engineer can create structured proposal
    eng_tok = client.post(
        "/api/v1/auth/login",
        json={"username": "neteng", "password": "CiscoEngineer2026!"},
    ).json()["access_token"]
    res_create = client.post(
        "/api/v1/remediation",
        json={
            "incident_id": inc.id,
            "device_id": dev.id,
            "title": "API Structured Op",
            "operation": "ADD_VLAN_TO_TRUNK",
            "target_interface": "GigabitEthernet0/1",
            "parameters": {"vlan_id": 30},
        },
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert res_create.status_code == 201
    prop_data = res_create.json()
    assert prop_data["operation"] == "ADD_VLAN_TO_TRUNK"
    assert prop_data["execution_mode"] == "SIMULATION"

    # Admin approves, engineer executes
    admin_tok = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "NetGuardianAdmin2026!"},
    ).json()["access_token"]
    res_app = client.post(
        f"/api/v1/remediation/{prop_data['id']}/approve",
        json={},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert res_app.status_code == 200
    assert res_app.json()["approval_digest"] is not None

    res_exec = client.post(
        f"/api/v1/remediation/{prop_data['id']}/execute",
        json={"execution_mode": "PRODUCTION"},
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert res_exec.status_code == 403  # Production blocked

    res_sim = client.post(
        f"/api/v1/remediation/{prop_data['id']}/execute",
        json={"execution_mode": "SIMULATION"},
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert res_sim.status_code == 200
    assert res_sim.json()["execution_mode"] == "SIMULATION"


def test_safe_migration_is_idempotent():
    run_safe_migrations(default_engine)
    run_safe_migrations(default_engine)
