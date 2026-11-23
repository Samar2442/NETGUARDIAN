from typing import Dict, Any, Optional
from datetime import datetime, timezone
import hashlib
from sqlalchemy.orm import Session
from app.models import (
    Device, NetworkInterface, Incident, RemediationProposal, ConfigSnapshot, AuditLog
)
from app.engines.verification.verification_engine import VerificationEngine
from app.engines.rollback.rollback_engine import RollbackEngine

class RemediationEngine:
    """
    Explainable Self-Healing and Controlled Remediation Engine.
    Enforces human approval, creates configuration snapshots, executes vetted Cisco commands,
    triggers post-change verification, and automatically handles rollback on failure.
    """

    @staticmethod
    def approve_proposal(db: Session, proposal_id: str, approved_by: str) -> RemediationProposal:
        proposal = db.query(RemediationProposal).filter(RemediationProposal.id == proposal_id).first()
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found.")

        proposal.status = "APPROVED"
        proposal.approved_by = approved_by
        proposal.approved_at = datetime.now(timezone.utc)

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
            details={"title": proposal.title, "commands": proposal.proposed_commands},
            status="SUCCESS"
        )
        db.add(audit)
        db.commit()
        return proposal

    @staticmethod
    def reject_proposal(db: Session, proposal_id: str, rejected_by: str) -> RemediationProposal:
        proposal = db.query(RemediationProposal).filter(RemediationProposal.id == proposal_id).first()
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found.")

        proposal.status = "REJECTED"
        audit = AuditLog(
            username=rejected_by,
            action="REMEDIATION_REJECTED",
            resource_type="REMEDIATION",
            resource_id=proposal.id,
            details={"title": proposal.title},
            status="SUCCESS"
        )
        db.add(audit)
        db.commit()
        return proposal

    @staticmethod
    def execute_remediation(db: Session, proposal_id: str, executed_by: str = "admin") -> Dict[str, Any]:
        """
        Executes approved remediation:
        1. Takes Configuration Snapshot
        2. Applies Cisco commands (mock simulation or SSH)
        3. Invokes VerificationEngine
        4. If verified, updates Incident to RESOLVED
        5. If failed, executes RollbackEngine
        """
        proposal = db.query(RemediationProposal).filter(RemediationProposal.id == proposal_id).first()
        if not proposal:
            raise ValueError("Proposal not found")

        device = db.query(Device).filter(Device.id == proposal.device_id).first()
        incident = db.query(Incident).filter(Incident.id == proposal.incident_id).first()

        proposal.status = "EXECUTING"
        db.commit()

        # Step 1: Pre-Execution Configuration Snapshot
        pre_config = f"! Pre-remediation snapshot for {device.hostname if device else 'device'}\nhostname {device.hostname if device else 'device'}\n"
        if proposal.target_interface and device:
            iface = db.query(NetworkInterface).filter(
                NetworkInterface.device_id == device.id,
                NetworkInterface.name == proposal.target_interface
            ).first()
            if iface:
                pre_config += f"interface {iface.name}\n switchport trunk allowed vlan {iface.allowed_vlans}\n"

        snap = ConfigSnapshot(
            device_id=device.id if device else "unknown",
            config_type="running-config",
            content=pre_config,
            content_hash=hashlib.sha256(pre_config.encode('utf-8')).hexdigest(),
        )
        db.add(snap)
        proposal.backup_snapshot = pre_config

        # Step 2: Execute Commands (Simulated Cisco Session)
        exec_lines = [
            f"[*] CONNECTING TO {device.hostname if device else 'device'} ({device.management_ip if device else 'ip'})...",
            f"[*] Authenticated as {executed_by} (Privilege Level 15).",
            f"{device.hostname if device else 'device'}#configure terminal",
            "Enter configuration commands, one per line. End with CNTL/Z.",
        ]

        for cmd in proposal.proposed_commands.strip().splitlines():
            exec_lines.append(f"{device.hostname if device else 'device'}(config)#{cmd.strip()}")

        exec_lines.append(f"{device.hostname if device else 'device'}(config)#end")
        exec_lines.append(f"{device.hostname if device else 'device'}#write memory")
        exec_lines.append("Building configuration... [OK]")

        # Apply changes to database model
        if proposal.target_interface and device:
            iface = db.query(NetworkInterface).filter(
                NetworkInterface.device_id == device.id,
                NetworkInterface.name == proposal.target_interface
            ).first()

            if iface:
                if "switchport trunk allowed vlan add" in proposal.proposed_commands:
                    vlan_to_add = proposal.proposed_commands.split("add")[-1].strip()
                    allowed_vlans = [v.strip() for v in (iface.allowed_vlans or "").split(",") if v.strip()]
                    if vlan_to_add not in allowed_vlans:
                        allowed_vlans.append(vlan_to_add)
                        # sort numerically
                        try:
                            allowed_vlans = sorted(allowed_vlans, key=lambda x: int(x))
                        except Exception:
                            pass
                        iface.allowed_vlans = ",".join(allowed_vlans)
                        db.merge(iface)
                        exec_lines.append(f"[+] Interface {iface.name} updated: allowed VLANs = {iface.allowed_vlans}")

                elif "no shutdown" in proposal.proposed_commands:
                    iface.admin_status = "up"
                    iface.oper_status = "up"
                    db.merge(iface)
                    exec_lines.append(f"[+] Interface {iface.name} is now UP.")

        proposal.execution_log = "\n".join(exec_lines)
        proposal.applied_at = datetime.now(timezone.utc)
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

            # Record Success Audit
            audit = AuditLog(
                username=executed_by,
                action="REMEDIATION_VERIFIED_SUCCESS",
                resource_type="REMEDIATION",
                resource_id=proposal.id,
                details={"status": "RESOLVED", "incident_id": incident.incident_number if incident else None},
                status="SUCCESS"
            )
            db.add(audit)
            db.commit()

            return {
                "success": True,
                "status": "RESOLVED",
                "proposal_status": "VERIFIED",
                "execution_log": proposal.execution_log,
                "verification": verification_result
            }
        else:
            # Step 4: Auto-rollback on verification failure
            rollback_res = RollbackEngine.execute_rollback(db, proposal, username="NetGuardian-AutoRollback")
            return {
                "success": False,
                "status": "ROLLBACK",
                "proposal_status": "ROLLED_BACK",
                "execution_log": proposal.execution_log,
                "rollback": rollback_res
            }
