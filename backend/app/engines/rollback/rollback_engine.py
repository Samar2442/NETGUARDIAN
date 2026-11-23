from typing import Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import Device, NetworkInterface, Incident, RemediationProposal, AuditLog

class RollbackEngine:
    """
    Controlled Configuration Rollback Engine.
    Reverses configuration changes when verification fails or administrator aborts.
    """

    @staticmethod
    def execute_rollback(db: Session, proposal: RemediationProposal, username: str = "admin") -> Dict[str, Any]:
        device = db.query(Device).filter(Device.id == proposal.device_id).first()
        incident = db.query(Incident).filter(Incident.id == proposal.incident_id).first()

        rollback_log = []
        rollback_log.append(f"[*] CONFIGURATION ROLLBACK INITIATED by {username} at {datetime.now(timezone.utc).isoformat()}")
        rollback_log.append(f"[*] Device: {device.hostname if device else 'Unknown'}")
        rollback_log.append(f"[*] Executing rollback commands:\n{proposal.rollback_commands}")

        # Execute rollback logic on target interface
        if proposal.target_interface and device:
            iface = db.query(NetworkInterface).filter(
                NetworkInterface.device_id == device.id,
                NetworkInterface.name == proposal.target_interface
            ).first()

            if iface:
                # If rollback is removing VLAN
                if "switchport trunk allowed vlan remove" in proposal.rollback_commands:
                    vlan_to_remove = proposal.rollback_commands.split("remove")[-1].strip()
                    allowed_vlans = [v.strip() for v in (iface.allowed_vlans or "").split(",") if v.strip() != vlan_to_remove]
                    iface.allowed_vlans = ",".join(allowed_vlans)
                    db.merge(iface)
                    rollback_log.append(f"[+] Reverted {iface.name} allowed VLAN list to: {iface.allowed_vlans}")

                elif "shutdown" in proposal.rollback_commands and "no shutdown" not in proposal.rollback_commands:
                    iface.admin_status = "down"
                    iface.oper_status = "down"
                    db.merge(iface)
                    rollback_log.append(f"[+] Re-shut interface {iface.name}.")

        rollback_log.append("[+] Rollback commands applied successfully.")
        
        # Update proposal state
        proposal.status = "ROLLED_BACK"
        proposal.rollback_log = "\n".join(rollback_log)
        db.merge(proposal)

        # Update incident state
        if incident:
            incident.status = "ROLLBACK"
            incident.updated_at = datetime.now(timezone.utc)
            db.merge(incident)

        # Audit
        audit = AuditLog(
            username=username,
            action="REMEDIATION_ROLLBACK",
            resource_type="REMEDIATION",
            resource_id=proposal.id,
            details={"device": device.hostname if device else None, "commands": proposal.rollback_commands},
            status="SUCCESS"
        )
        db.add(audit)
        db.commit()

        return {
            "success": True,
            "status": "ROLLED_BACK",
            "rollback_log": proposal.rollback_log
        }
