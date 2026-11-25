from typing import Dict, Any, Optional
from datetime import datetime, timezone
import hashlib
import time
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import (
    Device, NetworkInterface, Incident, RemediationProposal, ConfigSnapshot, AuditLog, VLAN
)
from app.engines.verification.verification_engine import VerificationEngine
from app.engines.rollback.rollback_engine import RollbackEngine
from app.engines.remediation.command_validator import (
    RemediationOperation,
    ExecutionMode,
    CommandValidationError,
    ApprovalBindingError,
    ExecutionLockError,
    ExecutionModeError,
    DuplicateExecutionError,
    validate_device_id,
    validate_interface_name,
    build_structured_commands,
    validate_cisco_commands,
    infer_structured_operation,
    compute_approval_digest,
    verify_approval_digest,
    device_execution_locks,
)


class RemediationEngine:
    """
    Phase 5A Hardened Explainable Self-Healing and Controlled Remediation Engine.
    Enforces:
    - Explicit command allowlisting & structured operation validation
    - Cryptographic approval-to-execution digest binding
    - Per-device execution locking & duplicate execution protection
    - Explicit execution modes (SIMULATION, LAB, PRODUCTION)
    - Pre-change snapshots, timeout bounds, verification, and auto-rollback
    """

    @staticmethod
    def create_structured_proposal(
        db: Session,
        incident_id: str,
        device_id: str,
        title: str,
        operation: str,
        target_interface: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        risk_level: str = "low",
        expected_result: str = "Network state restored",
        execution_mode: str = "SIMULATION",
    ) -> RemediationProposal:
        validate_device_id(device_id)
        device = db.query(Device).filter(Device.id == device_id).first()
        if not device:
            raise CommandValidationError(f"Target device '{device_id}' does not exist.")

        mode_upper = (execution_mode or "SIMULATION").strip().upper()
        if mode_upper not in {m.value for m in ExecutionMode}:
            raise ExecutionModeError(f"Unsupported execution mode: '{execution_mode}'.")

        proposed_cmds, rollback_cmds, _, norm_params = build_structured_commands(
            operation=operation,
            interface=target_interface,
            parameters=parameters,
        )

        op_enum = RemediationOperation(operation.strip().upper())
        prop = RemediationProposal(
            incident_id=incident_id,
            device_id=device.id,
            title=title,
            target_interface=target_interface.strip() if target_interface else None,
            operation=op_enum.value,
            parameters=norm_params,
            execution_mode=mode_upper,
            proposed_commands=proposed_cmds,
            rollback_commands=rollback_cmds,
            risk_level=risk_level,
            expected_result=expected_result,
            status="PENDING_APPROVAL",
        )
        db.add(prop)
        db.commit()
        db.refresh(prop)
        return prop

    @staticmethod
    def _resolve_and_validate_proposal(
        db: Session, proposal: RemediationProposal
    ) -> tuple[Device, RemediationOperation, Dict[str, Any]]:
        """Validate device, structured operation, parameters, and command allowlist."""
        validate_device_id(proposal.device_id)
        device = db.query(Device).filter(Device.id == proposal.device_id).first()
        if not device:
            raise CommandValidationError(f"Target device '{proposal.device_id}' not found.")

        if proposal.target_interface:
            validate_interface_name(proposal.target_interface)

        if proposal.operation:
            expected_proposed, _, _, norm_params = build_structured_commands(
                operation=proposal.operation,
                interface=proposal.target_interface,
                parameters=proposal.parameters or {},
            )
            if (proposal.proposed_commands or "").strip() != expected_proposed.strip():
                raise CommandValidationError(
                    "Proposed commands do not match canonical structured operation."
                )
            validate_cisco_commands(
                proposal.proposed_commands, target_interface=proposal.target_interface
            )
            validate_cisco_commands(
                proposal.rollback_commands or "",
                target_interface=proposal.target_interface,
                allow_empty=True,
            )
            return device, RemediationOperation(proposal.operation), norm_params
        else:
            # Backward-compatible strict inference for legacy proposals
            op_enum, norm_params = infer_structured_operation(
                proposal.proposed_commands,
                target_interface=proposal.target_interface,
            )
            validate_cisco_commands(
                proposal.rollback_commands or "",
                target_interface=proposal.target_interface,
                allow_empty=True,
            )
            return device, op_enum, norm_params

    @staticmethod
    def _validate_execution_mode(mode_str: str, device: Device) -> ExecutionMode:
        try:
            mode = ExecutionMode((mode_str or settings.REMEDIATION_EXECUTION_MODE).strip().upper())
        except ValueError:
            raise ExecutionModeError(f"Unsupported execution mode: '{mode_str}'.")

        if mode == ExecutionMode.SIMULATION:
            return mode

        if mode == ExecutionMode.LAB:
            if not settings.ALLOW_LAB_EXECUTION:
                raise ExecutionModeError(
                    "LAB execution mode is disabled. Enable ALLOW_LAB_EXECUTION with authorized lab device configuration."
                )
            if (
                device.hostname not in settings.AUTHORIZED_LAB_DEVICES
                and device.id not in settings.AUTHORIZED_LAB_DEVICES
            ):
                raise ExecutionModeError(
                    f"Device '{device.hostname}' is not in AUTHORIZED_LAB_DEVICES."
                )
            return mode

        if mode == ExecutionMode.PRODUCTION:
            if not settings.ALLOW_PRODUCTION_EXECUTION:
                raise ExecutionModeError(
                    "PRODUCTION execution mode is disabled by default and requires explicit authorization and real-device validation."
                )
            raise ExecutionModeError(
                "PRODUCTION real-device transport is not enabled in this build."
            )

        raise ExecutionModeError(f"Unsupported execution mode: '{mode_str}'.")

    @staticmethod
    def approve_proposal(db: Session, proposal_id: str, approved_by: str) -> RemediationProposal:
        proposal = db.query(RemediationProposal).filter(RemediationProposal.id == proposal_id).first()
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found.")

        if proposal.status != "PENDING_APPROVAL":
            raise DuplicateExecutionError(
                f"Cannot approve proposal in status '{proposal.status}'. Expected 'PENDING_APPROVAL'."
            )

        device, op_enum, norm_params = RemediationEngine._resolve_and_validate_proposal(db, proposal)
        if not proposal.operation:
            proposal.operation = op_enum.value
            proposal.parameters = norm_params

        latest_snap = (
            db.query(ConfigSnapshot)
            .filter(ConfigSnapshot.device_id == device.id)
            .order_by(ConfigSnapshot.created_at.desc())
            .first()
        )
        config_revision = latest_snap.content_hash if latest_snap else "BASELINE"

        approved_at = datetime.now(timezone.utc)
        digest = compute_approval_digest(
            proposal_id=proposal.id,
            device_id=proposal.device_id,
            target_interface=proposal.target_interface,
            operation=proposal.operation,
            parameters=proposal.parameters,
            proposed_commands=proposal.proposed_commands,
            rollback_commands=proposal.rollback_commands,
            config_revision=config_revision,
            approved_by=approved_by,
            approved_at=approved_at,
        )

        proposal.status = "APPROVED"
        proposal.approved_by = approved_by
        proposal.approved_at = approved_at
        proposal.config_revision = config_revision
        proposal.approval_digest = digest

        incident = db.query(Incident).filter(Incident.id == proposal.incident_id).first()
        if incident:
            incident.status = "APPROVED"
            incident.updated_at = datetime.now(timezone.utc)
            db.merge(incident)

        audit = AuditLog(
            username=approved_by,
            action="REMEDIATION_APPROVED",
            resource_type="REMEDIATION",
            resource_id=proposal.id,
            details={
                "title": proposal.title,
                "operation": proposal.operation,
                "device_id": proposal.device_id,
                "approval_digest": digest,
                "config_revision": config_revision,
            },
            status="SUCCESS",
        )
        db.add(audit)
        db.commit()
        db.refresh(proposal)
        return proposal

    @staticmethod
    def reject_proposal(db: Session, proposal_id: str, rejected_by: str) -> RemediationProposal:
        proposal = db.query(RemediationProposal).filter(RemediationProposal.id == proposal_id).first()
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found.")

        if proposal.status not in {"PENDING_APPROVAL", "APPROVED"}:
            raise DuplicateExecutionError(
                f"Cannot reject proposal in status '{proposal.status}'."
            )

        proposal.status = "REJECTED"
        proposal.approval_digest = None
        audit = AuditLog(
            username=rejected_by,
            action="REMEDIATION_REJECTED",
            resource_type="REMEDIATION",
            resource_id=proposal.id,
            details={"title": proposal.title, "operation": proposal.operation},
            status="SUCCESS",
        )
        db.add(audit)
        db.commit()
        db.refresh(proposal)
        return proposal

    @staticmethod
    def _apply_simulated_operation(
        db: Session,
        device: Device,
        proposal: RemediationProposal,
        op_enum: RemediationOperation,
        params: Dict[str, Any],
        exec_lines: list[str],
    ) -> None:
        """Execute a validated structured operation in SIMULATION mode against the digital model."""
        iface = None
        if proposal.target_interface:
            iface = (
                db.query(NetworkInterface)
                .filter(
                    NetworkInterface.device_id == device.id,
                    NetworkInterface.name == proposal.target_interface,
                )
                .first()
            )

        if op_enum == RemediationOperation.ADD_VLAN_TO_TRUNK and iface:
            vlan_to_add = str(params["vlan_id"])
            allowed_vlans = [v.strip() for v in (iface.allowed_vlans or "").split(",") if v.strip()]
            if vlan_to_add not in allowed_vlans:
                allowed_vlans.append(vlan_to_add)
                allowed_vlans = sorted(allowed_vlans, key=lambda x: int(x) if x.isdigit() else 0)
                iface.allowed_vlans = ",".join(allowed_vlans)
                db.merge(iface)
            exec_lines.append(f"[+] Interface {iface.name} updated: allowed VLANs = {iface.allowed_vlans}")

        elif op_enum == RemediationOperation.REMOVE_VLAN_FROM_TRUNK and iface:
            vlan_to_remove = str(params["vlan_id"])
            allowed_vlans = [
                v.strip() for v in (iface.allowed_vlans or "").split(",")
                if v.strip() and v.strip() != vlan_to_remove
            ]
            iface.allowed_vlans = ",".join(allowed_vlans)
            db.merge(iface)
            exec_lines.append(f"[+] Interface {iface.name} updated: allowed VLANs = {iface.allowed_vlans}")

        elif op_enum == RemediationOperation.ENABLE_INTERFACE and iface:
            iface.admin_status = "up"
            iface.oper_status = "up"
            db.merge(iface)
            exec_lines.append(f"[+] Interface {iface.name} is now UP.")

        elif op_enum == RemediationOperation.DISABLE_INTERFACE and iface:
            iface.admin_status = "down"
            iface.oper_status = "down"
            db.merge(iface)
            exec_lines.append(f"[+] Interface {iface.name} is now administratively DOWN.")

        elif op_enum == RemediationOperation.CONFIGURE_ACCESS_VLAN and iface:
            vid = int(params["vlan_id"])
            iface.mode = "access"
            iface.access_vlan = vid
            db.merge(iface)
            exec_lines.append(f"[+] Interface {iface.name} configured as access VLAN {vid}.")

        elif op_enum == RemediationOperation.CREATE_VLAN:
            vid = int(params["vlan_id"])
            existing_vlan = db.query(VLAN).filter(VLAN.vlan_id == vid).first()
            if not existing_vlan:
                new_vlan = VLAN(
                    vlan_id=vid,
                    name=params.get("vlan_name") or f"VLAN_{vid}",
                    subnet=f"10.10.{vid % 254}.0/24",
                    gateway_ip=f"10.10.{vid % 254}.1",
                    status="active",
                )
                db.add(new_vlan)
            exec_lines.append(f"[+] VLAN {vid} verified/created in simulated VLAN database.")

        elif op_enum == RemediationOperation.RESTORE_CONFIG_SNAPSHOT:
            sid = params["snapshot_id"]
            exec_lines.append(f"[+] Simulated config replace from snapshot '{sid}' completed.")

        elif op_enum in {
            RemediationOperation.VERIFY_TRUNK_CONFIG,
            RemediationOperation.VERIFY_VLAN_EXISTS,
            RemediationOperation.VERIFY_INTERFACE_STATUS,
        }:
            exec_lines.append(f"[+] Read-only verification operation {op_enum.value} completed.")

    @staticmethod
    def execute_remediation(
        db: Session,
        proposal_id: str,
        executed_by: str = "admin",
        execution_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute an approved remediation proposal with full Phase 5A security guarantees:
        1. Reload proposal from DB
        2. Verify approval status & duplicate execution protection
        3. Re-validate structured operation, parameters, and command allowlist
        4. Recalculate & verify cryptographic approval_digest
        5. Validate execution mode (SIMULATION / LAB / PRODUCTION)
        6. Acquire per-device execution lock
        7. Take pre-execution snapshot, apply with timeout guard, verify, or auto-rollback
        """
        proposal = db.query(RemediationProposal).filter(RemediationProposal.id == proposal_id).first()
        if not proposal:
            raise ValueError("Proposal not found")
        db.refresh(proposal)

        if proposal.status in {"EXECUTING", "APPLIED", "VERIFIED", "ROLLED_BACK"}:
            raise DuplicateExecutionError(
                f"Duplicate execution blocked: proposal is already in state '{proposal.status}'."
            )
        if proposal.status != "APPROVED":
            raise ApprovalBindingError(
                f"Execution denied: proposal status is '{proposal.status}', expected 'APPROVED'."
            )
        if not proposal.approval_digest:
            raise ApprovalBindingError(
                "Execution denied: proposal lacks a cryptographic approval binding digest."
            )

        # Verify cryptographic approval binding digest BEFORE re-validating parameters
        recalculated_digest = compute_approval_digest(
            proposal_id=proposal.id,
            device_id=proposal.device_id,
            target_interface=proposal.target_interface,
            operation=proposal.operation,
            parameters=proposal.parameters,
            proposed_commands=proposal.proposed_commands,
            rollback_commands=proposal.rollback_commands,
            config_revision=proposal.config_revision,
            approved_by=proposal.approved_by,
            approved_at=proposal.approved_at,
        )
        if not verify_approval_digest(proposal.approval_digest, recalculated_digest):
            audit = AuditLog(
                username=executed_by,
                action="REMEDIATION_TAMPER_DETECTED",
                resource_type="REMEDIATION",
                resource_id=proposal.id,
                details={
                    "expected_digest": proposal.approval_digest,
                    "actual_digest": recalculated_digest,
                },
                status="FAILED",
            )
            db.add(audit)
            db.commit()
            raise ApprovalBindingError(
                "Approval digest mismatch: proposal modified after approval. A new approval is required."
            )

        device, op_enum, norm_params = RemediationEngine._resolve_and_validate_proposal(db, proposal)
        mode = RemediationEngine._validate_execution_mode(
            execution_mode or proposal.execution_mode, device
        )

        incident = db.query(Incident).filter(Incident.id == proposal.incident_id).first()

        with device_execution_locks.acquire(device.id, timeout=0.0):
            start_mono = time.monotonic()
            proposal.status = "EXECUTING"
            proposal.executed_by = executed_by
            proposal.execution_mode = mode.value
            proposal.execution_started_at = datetime.now(timezone.utc)
            db.commit()

            try:
                # Step 1: Pre-Execution Configuration Snapshot
                pre_config = f"! Pre-remediation snapshot for {device.hostname}\nhostname {device.hostname}\n"
                if proposal.target_interface:
                    iface = (
                        db.query(NetworkInterface)
                        .filter(
                            NetworkInterface.device_id == device.id,
                            NetworkInterface.name == proposal.target_interface,
                        )
                        .first()
                    )
                    if iface:
                        pre_config += (
                            f"interface {iface.name}\n"
                            f" switchport trunk allowed vlan {iface.allowed_vlans}\n"
                        )

                snap = ConfigSnapshot(
                    device_id=device.id,
                    config_type="running-config",
                    content=pre_config,
                    content_hash=hashlib.sha256(pre_config.encode("utf-8")).hexdigest(),
                )
                db.add(snap)
                proposal.backup_snapshot = pre_config

                # Step 2: Execute Commands in validated mode
                exec_lines = [
                    f"[MODE: {mode.value}] CONNECTING TO {device.hostname} ({device.management_ip})...",
                    f"[*] Authenticated as {executed_by} (Privilege Level 15).",
                    f"{device.hostname}#configure terminal",
                    "Enter configuration commands, one per line. End with CNTL/Z.",
                ]

                for cmd in proposal.proposed_commands.strip().splitlines():
                    exec_lines.append(f"{device.hostname}(config)#{cmd.strip()}")

                exec_lines.append(f"{device.hostname}(config)#end")
                exec_lines.append(f"{device.hostname}#write memory")
                exec_lines.append("Building configuration... [OK]")

                # Enforce timeout before state mutation
                elapsed = time.monotonic() - start_mono
                if elapsed > settings.REMEDIATION_EXECUTION_TIMEOUT_SECONDS:
                    raise TimeoutError(
                        f"Execution exceeded timeout of {settings.REMEDIATION_EXECUTION_TIMEOUT_SECONDS}s."
                    )

                RemediationEngine._apply_simulated_operation(
                    db, device, proposal, op_enum, norm_params, exec_lines
                )

                proposal.execution_log = "\n".join(exec_lines)
                proposal.applied_at = datetime.now(timezone.utc)
                proposal.execution_finished_at = datetime.now(timezone.utc)
                proposal.status = "APPLIED"

                if incident:
                    incident.status = "APPLIED"
                    db.merge(incident)
                db.commit()

                # Step 3: Run Automated Verification
                verification_result = VerificationEngine.verify_remediation(db, proposal)
                proposal.verification_status = "VERIFIED" if verification_result["success"] else "FAILED"
                proposal.execution_log += "\n\n" + verification_result["verification_log"]

                if verification_result["success"]:
                    proposal.status = "VERIFIED"
                    if incident:
                        incident.status = "RESOLVED"
                        incident.resolved_at = datetime.now(timezone.utc)
                        db.merge(incident)

                    audit = AuditLog(
                        username=executed_by,
                        action="REMEDIATION_VERIFIED_SUCCESS",
                        resource_type="REMEDIATION",
                        resource_id=proposal.id,
                        details={
                            "status": "RESOLVED",
                            "execution_mode": mode.value,
                            "operation": op_enum.value,
                            "incident_id": incident.incident_number if incident else None,
                        },
                        status="SUCCESS",
                    )
                    db.add(audit)
                    db.commit()

                    return {
                        "success": True,
                        "status": "RESOLVED",
                        "proposal_status": "VERIFIED",
                        "execution_mode": mode.value,
                        "execution_log": proposal.execution_log,
                        "verification": verification_result,
                    }
                else:
                    # Step 4: Auto-rollback on verification failure (device lock already held)
                    rollback_res = RollbackEngine.execute_rollback(
                        db, proposal, username="NetGuardian-AutoRollback", lock_already_held=True
                    )
                    return {
                        "success": False,
                        "status": "ROLLBACK",
                        "proposal_status": "ROLLED_BACK",
                        "execution_mode": mode.value,
                        "execution_log": proposal.execution_log,
                        "rollback": rollback_res,
                    }
            except Exception as exc:
                proposal.status = "FAILED"
                proposal.execution_finished_at = datetime.now(timezone.utc)
                proposal.execution_log = (proposal.execution_log or "") + f"\n[ERROR] Execution aborted: {exc}"
                audit = AuditLog(
                    username=executed_by,
                    action="REMEDIATION_EXECUTION_FAILED",
                    resource_type="REMEDIATION",
                    resource_id=proposal.id,
                    details={"error": str(exc)},
                    status="FAILED",
                )
                db.add(audit)
                db.commit()
                raise
