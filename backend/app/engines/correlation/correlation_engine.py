from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models import Event, Incident, IncidentActivity

_SEV_TO_PRIORITY = {
    "CRITICAL": "P1",
    "HIGH": "P2",
    "MAJOR": "P2",
    "MEDIUM": "P3",
    "WARNING": "P3",
    "MINOR": "P3",
    "LOW": "P4",
    "INFO": "P4",
}


class CorrelationEngine:
    """
    Event Normalization and Multi-Symptom Correlation Engine.
    Groups related alerts from the same root cause without merging unrelated
    incidents that merely happen to touch the same device.
    """

    CORRELATION_WINDOW_SECONDS = 300  # 5 minutes

    @staticmethod
    def correlate_event(db: Session, event: Event) -> Optional[Incident]:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=CorrelationEngine.CORRELATION_WINDOW_SECONDS)

        active_incidents = db.query(Incident).filter(
            Incident.status.in_(["DETECTED", "INVESTIGATING", "ROOT_CAUSE_IDENTIFIED", "ACKNOWLEDGED", "IN_PROGRESS"]),
            Incident.created_at >= window_start,
        ).all()

        details = event.details or {}
        event_vlan = details.get("vlan_id") or event.vlan_id
        event_corr_id = event.correlation_id

        matched_incident: Optional[Incident] = None

        for inc in active_incidents:
            # 1. Exact correlation_id match
            if event_corr_id and inc.correlation_id and inc.correlation_id == event_corr_id:
                matched_incident = inc
                break
            # 2. Shared VLAN root-cause match (only for VLAN/trunk/gateway events)
            if event_vlan and event_vlan in (inc.affected_vlan_ids or []) and event.event_type in {
                "GATEWAY_UNREACHABLE", "VLAN_TRUNK_PRUNED", "VLAN_MISSING", "LINK_FAILURE"
            }:
                matched_incident = inc
                break
            # 3. Same device AND same event_type (do NOT merge unrelated fault types on same device)
            if (
                inc.source_device_id
                and event.source_id
                and str(inc.source_device_id) == str(event.source_id)
                and event.event_type.replace("_", " ").lower() in inc.title.lower()
            ):
                matched_incident = inc
                break

        if matched_incident:
            event.is_correlated = True
            event.incident_id = matched_incident.id

            affected = list(matched_incident.affected_device_ids or [])
            if event.source_id and str(event.source_id) not in affected:
                affected.append(str(event.source_id))
                matched_incident.affected_device_ids = affected
                matched_incident.affected_endpoints_count = len(affected)

            if event.interface_id:
                ifaces = list(matched_incident.affected_interface_ids or [])
                if str(event.interface_id) not in ifaces:
                    ifaces.append(str(event.interface_id))
                    matched_incident.affected_interface_ids = ifaces

            if event_vlan:
                vlans = list(matched_incident.affected_vlan_ids or [])
                if event_vlan not in vlans:
                    vlans.append(event_vlan)
                    matched_incident.affected_vlan_ids = vlans

            matched_incident.updated_at = now
            db.commit()
            return matched_incident
        else:
            incident_number = f"INC-{now.strftime('%Y%m%d')}-{db.query(Incident).count() + 101}"
            severity = event.severity
            priority = _SEV_TO_PRIORITY.get(str(severity).upper(), "P2")
            title = f"{event.event_type.replace('_', ' ').title()}: {event.source_name}"
            description = f"Automated correlation detected network anomaly: {event.message}"

            new_incident = Incident(
                incident_number=incident_number,
                title=title,
                description=description,
                severity=severity,
                priority=priority,
                status="DETECTED",
                lifecycle_state="NEW",
                source_device_id=event.source_id,
                source_device_name=event.source_name,
                affected_device_ids=[str(event.source_id)] if event.source_id else [],
                affected_interface_ids=[str(event.interface_id)] if event.interface_id else [],
                affected_vlan_ids=[event_vlan] if event_vlan else [],
                affected_endpoints_count=1 if event.source_type == "endpoint" else 0,
                root_event_id=event.id,
                correlation_id=event_corr_id,
                created_at=now,
                updated_at=now,
            )
            db.add(new_incident)
            db.flush()

            db.add(IncidentActivity(
                incident_id=new_incident.id,
                actor="correlation-engine",
                action="INCIDENT_CREATED",
                details={"root_event_id": event.id, "event_type": event.event_type},
                timestamp=now,
            ))

            event.is_correlated = True
            event.incident_id = new_incident.id
            db.commit()
            return new_incident
