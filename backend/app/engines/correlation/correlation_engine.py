from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models import Event, Incident, Device, NetworkInterface

class CorrelationEngine:
    """
    Event Normalization and Multi-Symptom Correlation Engine.
    Groups related alerts across devices, VLANs, and topology into unified incidents.
    """

    CORRELATION_WINDOW_SECONDS = 300  # 5 minutes

    @staticmethod
    def correlate_event(db: Session, event: Event) -> Optional[Incident]:
        """
        Attempts to associate a newly generated event with an existing active incident,
        or creates a new incident if this represents a new failure domain.
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=CorrelationEngine.CORRELATION_WINDOW_SECONDS)

        # Look for open incidents in the correlation window
        active_incidents = db.query(Incident).filter(
            Incident.status.in_(["DETECTED", "INVESTIGATING", "ROOT_CAUSE_IDENTIFIED"]),
            Incident.created_at >= window_start
        ).all()

        details = event.details or {}
        event_vlan = details.get("vlan_id")
        event_switch = details.get("switch_name") or details.get("device_name") or event.source_name

        matched_incident: Optional[Incident] = None

        for inc in active_incidents:
            # 1. Match by shared VLAN
            if event_vlan and event_vlan in (inc.affected_vlan_ids or []):
                matched_incident = inc
                break
            # 2. Match by shared source device
            if inc.source_device_name and (inc.source_device_name == event_switch or inc.source_device_name in event.source_name):
                matched_incident = inc
                break
            # 3. Match by affected devices
            if event.source_id and str(event.source_id) in (inc.affected_device_ids or []):
                matched_incident = inc
                break

        if matched_incident:
            # Associate event with matched incident
            event.is_correlated = True
            event.incident_id = matched_incident.id
            
            # Update affected devices in incident if not present
            affected = list(matched_incident.affected_device_ids or [])
            if event.source_id and str(event.source_id) not in affected:
                affected.append(str(event.source_id))
                matched_incident.affected_device_ids = affected
                matched_incident.affected_endpoints_count = len(affected)

            # Update affected VLANs if not present
            if event_vlan:
                vlans = list(matched_incident.affected_vlan_ids or [])
                if event_vlan not in vlans:
                    vlans.append(event_vlan)
                    matched_incident.affected_vlan_ids = vlans

            matched_incident.updated_at = now
            db.commit()
            return matched_incident
        else:
            # Create a new incident for this failure cluster
            incident_number = f"INC-{now.strftime('%Y%m%d')}-{len(db.query(Incident).all()) + 101}"
            
            severity = event.severity
            title = f"{event.event_type.replace('_', ' ').title()}: {event.source_name}"
            description = f"Automated correlation detected network anomaly: {event.message}"

            new_incident = Incident(
                incident_number=incident_number,
                title=title,
                description=description,
                severity=severity,
                status="DETECTED",
                source_device_id=event.source_id,
                source_device_name=event.source_name,
                affected_device_ids=[str(event.source_id)] if event.source_id else [],
                affected_vlan_ids=[event_vlan] if event_vlan else [],
                affected_endpoints_count=1 if event.source_type == "endpoint" else 0,
                created_at=now,
                updated_at=now
            )
            db.add(new_incident)
            db.flush()

            event.is_correlated = True
            event.incident_id = new_incident.id
            db.commit()
            return new_incident
