from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import networkx as nx
from sqlalchemy.orm import Session
from app.models import (
    CampusService,
    Device,
    DeviceTelemetry,
    Incident,
    NetworkLink,
    ServiceDependency,
    VLAN,
)

CAMPUS_SERVICE_CATALOG = [
    {
        "service_key": "CAMPUS_INTERNET",
        "name": "Campus Internet Connectivity",
        "description": "External WAN routing, perimeter firewall, and core internet transit.",
        "service_category": "CONNECTIVITY",
        "criticality": "CRITICAL",
        "owner_team": "Core Infrastructure",
        "department_scope": "All",
        "sla_target_pct": 99.5,
        "devices": ["RTR-EDGE-01", "FW-CAMPUS-01", "SW-CORE-01"],
        "vlans": [],
    },
    {
        "service_key": "CSE_NETWORK",
        "name": "CSE Department Network",
        "description": "Computer Science & Engineering VLAN 10 switching and distribution.",
        "service_category": "DEPARTMENT_NETWORK",
        "criticality": "HIGH",
        "owner_team": "Campus Switching & Routing",
        "department_scope": "CSE",
        "sla_target_pct": 99.5,
        "devices": ["SW-CORE-01", "SW-DIST-01", "SW-DIST-02", "SW-CSE-01", "SW-CSE-02"],
        "vlans": [10],
    },
    {
        "service_key": "IT_NETWORK",
        "name": "IT Department Network",
        "description": "Information Technology VLAN 20 switching and distribution.",
        "service_category": "DEPARTMENT_NETWORK",
        "criticality": "HIGH",
        "owner_team": "Campus Switching & Routing",
        "department_scope": "IT",
        "sla_target_pct": 99.5,
        "devices": ["SW-CORE-01", "SW-DIST-01", "SW-DIST-02", "SW-IT-01", "SW-IT-02"],
        "vlans": [20],
    },
    {
        "service_key": "ECE_NETWORK",
        "name": "ECE Department Network",
        "description": "Electronics & Communication Engineering VLAN 30 switching and distribution.",
        "service_category": "DEPARTMENT_NETWORK",
        "criticality": "HIGH",
        "owner_team": "Campus Switching & Routing",
        "department_scope": "ECE",
        "sla_target_pct": 99.5,
        "devices": ["SW-CORE-01", "SW-DIST-01", "SW-DIST-02", "SW-ECE-01", "SW-ECE-02"],
        "vlans": [30],
    },
    {
        "service_key": "CAMPUS_DNS",
        "name": "Campus DNS",
        "description": "Authoritative and recursive campus name resolution service.",
        "service_category": "CORE_SERVICE",
        "criticality": "CRITICAL",
        "owner_team": "Compute & Directory Services",
        "department_scope": "All",
        "sla_target_pct": 99.9,
        "devices": ["SRV-DNS-01", "SW-CORE-01"],
        "vlans": [],
    },
    {
        "service_key": "CAMPUS_DHCP",
        "name": "Campus DHCP",
        "description": "Dynamic IPv4 address allocation for CSE, IT, and ECE subnets.",
        "service_category": "CORE_SERVICE",
        "criticality": "CRITICAL",
        "owner_team": "Compute & Directory Services",
        "department_scope": "All",
        "sla_target_pct": 99.5,
        "devices": ["SRV-DHCP-01", "SW-CORE-01"],
        "vlans": [],
    },
    {
        "service_key": "CAMPUS_APP_SERVER",
        "name": "Campus Application Server",
        "description": "Internal academic portal and lab application services.",
        "service_category": "APPLICATION",
        "criticality": "HIGH",
        "owner_team": "Compute & Directory Services",
        "department_scope": "All",
        "sla_target_pct": 99.5,
        "devices": ["SRV-APP-01", "SW-CORE-01"],
        "vlans": [],
    },
]


class ServiceIntelligenceEngine:
    """
    Campus Service Intelligence, Dependency Graph Health, and SLA/MTTR Engine.
    All availability and SLA figures are explicitly labeled as SIMULATION / DEMONSTRATION.
    """

    @staticmethod
    def seed_campus_services(db: Session) -> int:
        dev_by_name = {d.hostname: d for d in db.query(Device).all()}
        vlan_by_id = {v.vlan_id: v for v in db.query(VLAN).all()}
        links = db.query(NetworkLink).all()
        existing_services = {s.service_key: s for s in db.query(CampusService).all()}

        for spec in CAMPUS_SERVICE_CATALOG:
            svc = existing_services.get(spec["service_key"])
            if not svc:
                svc = CampusService(
                    service_key=spec["service_key"],
                    name=spec["name"],
                    description=spec["description"],
                    service_category=spec["service_category"],
                    criticality=spec["criticality"],
                    owner_team=spec["owner_team"],
                    department_scope=spec["department_scope"],
                    sla_target_pct=spec["sla_target_pct"],
                    operational_status="OPERATIONAL",
                )
                db.add(svc)
                db.flush()

            # Ensure dependencies from actual DB records
            existing_deps = db.query(ServiceDependency).filter(ServiceDependency.service_id == svc.id).count()
            if existing_deps == 0:
                dep_dev_ids = set()
                for dname in spec["devices"]:
                    d = dev_by_name.get(dname)
                    if d:
                        dep_dev_ids.add(d.id)
                        role = "REDUNDANT_PATH" if d.device_type == "l2_switch" else "PRIMARY"
                        db.add(ServiceDependency(
                            service_id=svc.id,
                            resource_type="device",
                            resource_id=d.id,
                            resource_name=d.hostname,
                            dependency_role=role,
                            is_critical=not (d.device_type == "l2_switch"),
                        ))
                for vid in spec["vlans"]:
                    v = vlan_by_id.get(vid)
                    if v:
                        db.add(ServiceDependency(
                            service_id=svc.id,
                            resource_type="vlan",
                            resource_id=v.id,
                            resource_name=f"VLAN {v.vlan_id} ({v.department})",
                            dependency_role="PRIMARY",
                            is_critical=True,
                        ))
                for l in links:
                    if l.source_device_id in dep_dev_ids and l.target_device_id in dep_dev_ids:
                        db.add(ServiceDependency(
                            service_id=svc.id,
                            resource_type="link",
                            resource_id=l.id,
                            resource_name=l.name,
                            dependency_role="REDUNDANT_PATH" if l.is_redundant else "CORE_PATH",
                            is_critical=not l.is_redundant,
                        ))
        db.commit()
        return db.query(CampusService).count()

    @staticmethod
    def calculate_service_health(db: Session, service: CampusService) -> Dict[str, Any]:
        deps = db.query(ServiceDependency).filter(ServiceDependency.service_id == service.id).all()
        if not deps:
            return {
                "service_id": service.id,
                "service_key": service.service_key,
                "name": service.name,
                "status": "UNKNOWN",
                "reason": "No dependencies configured.",
                "telemetry_source": "SIMULATION",
            }

        devices = {d.id: d for d in db.query(Device).all()}
        links = db.query(NetworkLink).all()

        # Check if any telemetry exists or if devices have unknown status
        telem_count = db.query(DeviceTelemetry).count()
        dep_devices = [devices.get(dep.resource_id) for dep in deps if dep.resource_type == "device"]
        dep_devices = [d for d in dep_devices if d is not None]

        if telem_count == 0 or any(d.status == "unknown" for d in dep_devices):
            return {
                "service_id": service.id,
                "service_key": service.service_key,
                "name": service.name,
                "status": "UNKNOWN",
                "reason": "Telemetry unavailable for service dependencies.",
                "telemetry_source": "SIMULATION",
            }

        # Build live operational graph (only up links & non-offline devices)
        G = nx.Graph()
        for did, d in devices.items():
            if d.status != "offline":
                G.add_node(did)
        for l in links:
            if l.status != "down" and l.source_device_id in G and l.target_device_id in G:
                G.add_edge(l.source_device_id, l.target_device_id)

        core = next((d for d in devices.values() if d.hostname == "SW-CORE-01"), None)
        reachable = set(nx.node_connected_component(G, core.id)) if (core and core.id in G) else set()

        # Evaluate device health & reachability (respecting redundant paths!)
        offline_critical = []
        degraded_devs = []
        access_switches = [d for d in dep_devices if d.device_type == "access_switch"]
        offline_access = [d for d in access_switches if d.status == "offline" or d.id not in reachable]

        for d in dep_devices:
            if d.device_type in {"l2_switch", "access_switch"}:
                if d.status == "degraded":
                    degraded_devs.append(d.hostname)
                continue
            if d.status == "offline" or (core and d.id != core.id and d.id not in reachable):
                offline_critical.append(d.hostname)
            elif d.status == "degraded":
                degraded_devs.append(d.hostname)

        # Check active incidents touching service devices/VLANs
        dep_dev_ids = {d.id for d in dep_devices}
        open_incs = db.query(Incident).filter(
            Incident.status.notin_(["RESOLVED", "CLOSED"])
        ).all()
        matching_incs = [
            inc for inc in open_incs
            if inc.source_device_id in dep_dev_ids
            or any(did in dep_dev_ids for did in (inc.affected_device_ids or []))
        ]

        if offline_critical or (access_switches and len(offline_access) == len(access_switches)):
            status = "OUTAGE"
        elif offline_access:
            status = "PARTIALLY_AVAILABLE"
        elif degraded_devs or matching_incs:
            status = "DEGRADED"
        else:
            status = "OPERATIONAL"

        service.operational_status = status
        db.merge(service)
        db.commit()

        return {
            "service_id": service.id,
            "service_key": service.service_key,
            "name": service.name,
            "department_scope": service.department_scope,
            "criticality": service.criticality,
            "status": status,
            "active_incidents": len(matching_incs),
            "offline_critical_dependencies": offline_critical,
            "degraded_dependencies": degraded_devs,
            "offline_access_switches": [d.hostname for d in offline_access],
            "telemetry_source": "SIMULATION",
        }

    @staticmethod
    def calculate_service_sla(db: Session, service: CampusService, window_hours: int = 24) -> Dict[str, Any]:
        health = ServiceIntelligenceEngine.calculate_service_health(db, service)
        deps = db.query(ServiceDependency).filter(
            ServiceDependency.service_id == service.id,
            ServiceDependency.resource_type == "device",
        ).all()
        dep_ids = [d.resource_id for d in deps]

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=window_hours)

        # Calculate incident-related downtime in window
        incs = db.query(Incident).filter(Incident.created_at >= cutoff).all()
        service_incs = [
            inc for inc in incs
            if inc.source_device_id in dep_ids
            or any(did in dep_ids for did in (inc.affected_device_ids or []))
        ]

        incident_downtime_sec = 0.0
        for inc in service_incs:
            if (inc.severity or "").upper() in {"CRITICAL", "HIGH"}:
                start = inc.created_at.replace(tzinfo=timezone.utc) if inc.created_at.tzinfo is None else inc.created_at
                end = inc.resolved_at or now
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                incident_downtime_sec += max(0.0, (end - start).total_seconds())

        # Also check DeviceTelemetry availability if available
        telem_rows = (
            db.query(DeviceTelemetry)
            .filter(DeviceTelemetry.device_id.in_(dep_ids), DeviceTelemetry.timestamp >= cutoff)
            .all()
            if dep_ids else []
        )
        total_window_sec = window_hours * 3600.0
        if telem_rows:
            avg_avail = sum(r.availability_pct for r in telem_rows) / len(telem_rows)
            availability_pct = round(avg_avail, 3)
        else:
            availability_pct = round(max(0.0, (1.0 - (incident_downtime_sec / total_window_sec)) * 100.0), 3)

        downtime_minutes = round((1.0 - availability_pct / 100.0) * window_hours * 60.0, 2)
        allowed_downtime_min = (1.0 - service.sla_target_pct / 100.0) * window_hours * 60.0
        breach_minutes = round(max(0.0, downtime_minutes - allowed_downtime_min), 2)

        return {
            "service_id": service.id,
            "service_key": service.service_key,
            "name": service.name,
            "current_status": health["status"],
            "sla_target_pct": service.sla_target_pct,
            "availability_pct": availability_pct,
            "sla_compliant": availability_pct >= service.sla_target_pct,
            "downtime_minutes": downtime_minutes,
            "incident_downtime_minutes": round(incident_downtime_sec / 60.0, 2),
            "breach_duration_minutes": breach_minutes,
            "window_hours": window_hours,
            "data_source": "SIMULATION_DEMONSTRATION",
        }

    @staticmethod
    def calculate_operational_metrics(db: Session) -> Dict[str, Any]:
        incs = db.query(Incident).all()
        ack_deltas = []
        res_deltas = []
        for inc in incs:
            created = inc.created_at.replace(tzinfo=timezone.utc) if inc.created_at.tzinfo is None else inc.created_at
            if inc.acknowledged_at:
                ack = inc.acknowledged_at.replace(tzinfo=timezone.utc) if inc.acknowledged_at.tzinfo is None else inc.acknowledged_at
                ack_deltas.append(max(0.0, (ack - created).total_seconds()))
            if inc.resolved_at:
                res = inc.resolved_at.replace(tzinfo=timezone.utc) if inc.resolved_at.tzinfo is None else inc.resolved_at
                res_deltas.append(max(0.0, (res - created).total_seconds()))

        # Count repeated outages per source_device_id
        by_device: Dict[str, int] = {}
        for inc in incs:
            if inc.source_device_id:
                by_device[inc.source_device_id] = by_device.get(inc.source_device_id, 0) + 1
        repeated_outages = sum(1 for c in by_device.values() if c > 1)

        return {
            "total_incidents": len(incs),
            "open_incidents": sum(1 for i in incs if i.status not in {"RESOLVED", "CLOSED"}),
            "mttd_seconds": 5.0 if incs else None,
            "mtta_seconds": round(sum(ack_deltas) / len(ack_deltas), 2) if ack_deltas else None,
            "mttr_seconds": round(sum(res_deltas) / len(res_deltas), 2) if res_deltas else None,
            "mtta_sample_size": len(ack_deltas),
            "mttr_sample_size": len(res_deltas),
            "repeated_outage_count": repeated_outages,
            "data_source": "SIMULATION",
        }
