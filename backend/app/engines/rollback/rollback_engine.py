from typing import Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import Device, NetworkInterface, Incident, RemediationProposal, AuditLog
from app.engines.remediation.command_validator import (
    RollbackEligibilityError,
    validate_cisco_commands,
    device_execution_locks,
)


class RollbackEngine:
    """
    Controlled Configuration Rollback Engine.
    Reverses configuration changes when verification fails or administrator aborts.
    Enforces rollback eligibility checks, command allowlist validation, and per-device locking.
    """

    @staticmethod
    def ensure_rollback_eligible(proposal: RemediationProposal) -> None:
        eligible_statuses = {"APPLIED", "VERIFIED", "FAILED"}
        if proposal.status not in eligible_statuses:
            raise RollbackEligibilityError(
                f"Proposal in state '{proposal.status}' is not eligible for rollback. "
                f"Eligible states: {sorted(eligible_statuses)}."
            )
        if not (proposal.rollback_commands and proposal.rollback_commands.strip()) and not proposal.backup_snapshot:
            raise RollbackEligibilityError(
                "Proposal has neither rollback commands nor a configuration backup snapshot."
            )

    @staticmethod
    def _apply_rollback_impl(
        db: Session, proposal: RemediationProposal, username: str
    ) -> Dict[str, Any]:
        RollbackEngine.ensure_rollback_eligible(proposal)
        validate_cisco_commands(
            proposal.rollback_commands or "",
            target_interface=proposal.target_interface,
            allow_empty=True,
        )

        device = db.query(Device).filter(Device.id == proposal.device_id).first()
        incident = db.query(Incident).filter(Incident.id == proposal.incident_id).first()

        rollback_log = [
            f"[*] CONFIGURATION ROLLBACK INITIATED by {username} at {datetime.now(timezone.utc).isoformat()}",
            f"[*] Device: {device.hostname if device else 'Unknown'}",
            f"[*] Executing rollback commands:\n{proposal.rollback_commands}",
        ]

        if proposal.target_interface and device:
            iface = (
                db.query(NetworkInterface)
                .filter(
                    NetworkInterface.device_id == device.id,
                    NetworkInterface.name == proposal.target_interface,
                )
                .first()
            )

            if iface:
                if "switchport trunk allowed vlan remove" in proposal.rollback_commands:
                    vlan_to_remove = proposal.rollback_commands.split("remove")[-1].strip()
                    allowed_vlans = [
                        v.strip()
                        for v in (iface.allowed_vlans or "").split(",")
                        if v.strip() and v.strip() != vlan_to_remove
                    ]
                    iface.allowed_vlans = ",".join(allowed_vlans)
                    db.merge(iface)
                    rollback_log.append(
                        f"[+] Reverted {iface.name} allowed VLAN list to: {iface.allowed_vlans}"
                    )

                elif "switchport trunk allowed vlan add" in proposal.rollback_commands:
                    vlan_to_add = proposal.rollback_commands.split("add")[-1].strip()
                    allowed_vlans = [
                        v.strip() for v in (iface.allowed_vlans or "").split(",") if v.strip()
                    ]
                    if vlan_to_add not in allowed_vlans:
                        allowed_vlans.append(vlan_to_add)
                        allowed_vlans = sorted(allowed_vlans, key=lambda x: int(x) if x.isdigit() else 0)
                        iface.allowed_vlans = ",".join(allowed_vlans)
                        db.merge(iface)
                    rollback_log.append(
                        f"[+] Reverted {iface.name} allowed VLAN list to: {iface.allowed_vlans}"
                    )

                elif (
                    "shutdown" in proposal.rollback_commands
                    and "no shutdown" not in proposal.rollback_commands
                ):
                    iface.admin_status = "down"
                    iface.oper_status = "down"
                    db.merge(iface)
                    rollback_log.append(f"[+] Re-shut interface {iface.name}.")

                elif "no shutdown" in proposal.rollback_commands:
                    iface.admin_status = "up"
                    iface.oper_status = "up"
                    db.merge(iface)
                    rollback_log.append(f"[+] Re-enabled interface {iface.name}.")

        rollback_log.append("[+] Rollback commands applied successfully.")

        proposal.status = "ROLLED_BACK"
        proposal.rollback_log = "\n".join(rollback_log)
        db.merge(proposal)

        if incident:
            incident.status = "ROLLBACK"
            incident.updated_at = datetime.now(timezone.utc)
            db.merge(incident)

        audit = AuditLog(
            username=username,
            action="REMEDIATION_ROLLBACK",
            resource_type="REMEDIATION",
            resource_id=proposal.id,
            details={
                "device": device.hostname if device else None,
                "commands": proposal.rollback_commands,
            },
            status="SUCCESS",
        )
        db.add(audit)
        db.commit()

        return {
            "success": True,
            "status": "ROLLED_BACK",
            "rollback_log": proposal.rollback_log,
        }

    @staticmethod
    def execute_rollback(
        db: Session,
        proposal: RemediationProposal,
        username: str = "admin",
        lock_already_held: bool = False,
    ) -> Dict[str, Any]:
        if lock_already_held:
            return RollbackEngine._apply_rollback_impl(db, proposal, username)
        with device_execution_locks.acquire(proposal.device_id, timeout=0.0):
            return RollbackEngine._apply_rollback_impl(db, proposal, username)
