from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone, timedelta
import networkx as nx
from sqlalchemy.orm import Session
from app.models import (
    Event,
    Incident,
    IncidentActivity,
    NetworkLink,
    ServiceDependency,
)

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

    @staticmethod
    def analyze_incident_correlations(db: Session, incident: Incident) -> Dict[str, Any]:
        """
        Multi-event correlation & timeline reconstruction for an incident.
        Uses event type, device/interface/VLAN identity, network topology,
        timestamps, and service dependencies to separate related events from
        independent failures.
        """
        linked_events = incident.events.order_by(Event.timestamp.asc()).all()
        ref_time = incident.created_at or datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)

        window_start = ref_time - timedelta(seconds=CorrelationEngine.CORRELATION_WINDOW_SECONDS)
        window_end = ref_time + timedelta(seconds=CorrelationEngine.CORRELATION_WINDOW_SECONDS * 2)

        nearby_events = (
            db.query(Event)
            .filter(
                Event.timestamp >= window_start,
                Event.timestamp <= window_end,
                Event.resolved == False,
            )
            .order_by(Event.timestamp.asc())
            .limit(200)
            .all()
        )

        # Build topology adjacency
        links = db.query(NetworkLink).all()
        G = nx.Graph()
        for l in links:
            if l.source_device_id and l.target_device_id:
                G.add_edge(str(l.source_device_id), str(l.target_device_id), link_id=l.id, status=l.status)

        inc_dev_ids: Set[str] = set(str(d) for d in (incident.affected_device_ids or []) if d)
        if incident.source_device_id:
            inc_dev_ids.add(str(incident.source_device_id))
        for e in linked_events:
            if e.device_id:
                inc_dev_ids.add(str(e.device_id))
            elif e.source_id:
                inc_dev_ids.add(str(e.source_id))

        inc_vlans: Set[int] = set(int(v) for v in (incident.affected_vlan_ids or []) if isinstance(v, int))
        for e in linked_events:
            if e.vlan_id:
                inc_vlans.add(int(e.vlan_id))

        # Service dependencies touching incident devices or VLANs
        svc_ids: Set[str] = set()
        if inc_dev_ids:
            for dep in db.query(ServiceDependency).filter(
                ServiceDependency.resource_type == "device",
                ServiceDependency.resource_id.in_(list(inc_dev_ids)),
            ).all():
                svc_ids.add(dep.service_id)

        # Causal symptom families
        reachability_family = {
            "VLAN_TRUNK_PRUNED", "VLAN_MISSING", "GATEWAY_UNREACHABLE",
            "LINK_DOWN", "LINK_FAILURE", "INTERFACE_DOWN", "DEVICE_UNREACHABLE",
            "HIGH_LATENCY", "PACKET_LOSS",
        }
        inc_types = {e.event_type for e in linked_events}
        is_reachability_inc = bool(inc_types & reachability_family) or any(
            kw in (incident.title or "").lower() for kw in ("vlan", "trunk", "link", "interface", "gateway", "down")
        )

        seen_ids: Set[str] = set()
        related_events: List[Event] = []
        independent_failures: List[Dict[str, Any]] = []

        # Linked events are always related
        for e in linked_events:
            seen_ids.add(e.id)
            related_events.append(e)

        for e in nearby_events:
            if e.id in seen_ids:
                continue
            seen_ids.add(e.id)
            e_dev = str(e.device_id or e.source_id or "")
            e_vlan = e.vlan_id or (e.details or {}).get("vlan_id")

            same_corr = bool(incident.correlation_id and e.correlation_id and e.correlation_id == incident.correlation_id)
            shared_vlan = bool(e_vlan and int(e_vlan) in inc_vlans and e.event_type in reachability_family and is_reachability_inc)
            topo_neighbor = False
            if e_dev and e_dev in G and inc_dev_ids:
                for d_id in inc_dev_ids:
                    if d_id in G and nx.has_path(G, e_dev, d_id):
                        dist = nx.shortest_path_length(G, e_dev, d_id)
                        if dist <= 1 and (e.event_type in inc_types or (is_reachability_inc and e.event_type in reachability_family)):
                            topo_neighbor = True
                            break

            if same_corr or shared_vlan or topo_neighbor:
                related_events.append(e)
            else:
                independent_failures.append({
                    "event_id": e.id,
                    "event_type": e.event_type,
                    "device": e.source_name,
                    "severity": e.severity,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "reason": "No shared correlation ID, affected VLAN, or compatible topological fault chain.",
                })

        related_events.sort(key=lambda ev: ev.timestamp or ref_time)

        # Timeline reconstruction from events + incident activities
        timeline: List[Dict[str, Any]] = []
        for ev in related_events:
            role = "PRIMARY_TRIGGER" if (incident.root_event_id and ev.id == incident.root_event_id) else "CORRELATED_EVENT"
            timeline.append({
                "timestamp": ev.timestamp.isoformat() if ev.timestamp else ref_time.isoformat(),
                "source": ev.source_name,
                "event_type": ev.event_type,
                "device": ev.source_name,
                "message": ev.message,
                "role": role,
            })

        activities = (
            db.query(IncidentActivity)
            .filter(IncidentActivity.incident_id == incident.id)
            .order_by(IncidentActivity.timestamp.asc())
            .all()
        )
        for act in activities:
            timeline.append({
                "timestamp": act.timestamp.isoformat() if act.timestamp else ref_time.isoformat(),
                "source": act.actor,
                "event_type": act.action,
                "device": incident.source_device_name or "NOC",
                "message": f"Incident activity: {act.action}",
                "role": "LIFECYCLE_ACTIVITY",
            })

        timeline.sort(key=lambda item: item["timestamp"])

        return {
            "related_events": related_events,
            "independent_failures": independent_failures,
            "timeline": timeline,
            "affected_service_ids": list(svc_ids),
        }
