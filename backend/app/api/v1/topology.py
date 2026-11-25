from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.database.session import get_db
from app.models import Device, NetworkLink, VLAN, AuditLog, User
from app.schemas import NetworkLinkResponse, NetworkLinkCreate
from app.engines.digital_twin.digital_twin_engine import DigitalTwinEngine
from app.engines.topology.validation_engine import TopologyValidationEngine
from app.database.campus_seed import seed_campus_network
from app.core.dependencies import require_viewer, require_engineer, require_admin

router = APIRouter(prefix="/topology", tags=["Topology"])


@router.get("", response_model=Dict[str, Any])
def get_topology(
    include_endpoints: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Returns nodes and edges formatted for React Flow."""
    return DigitalTwinEngine.get_topology_payload(db, include_endpoints=include_endpoints)


@router.get("/links", response_model=List[NetworkLinkResponse])
def get_links(
    link_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(NetworkLink)
    if link_type:
        query = query.filter(NetworkLink.link_type == link_type)
    if status:
        query = query.filter(NetworkLink.status == status)
    return query.all()


@router.post("/links", response_model=NetworkLinkResponse, status_code=201)
def create_link(
    payload: NetworkLinkCreate,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    """Create a validated network link between two existing devices."""
    try:
        TopologyValidationEngine.validate_new_link(
            db=db,
            source_device_id=payload.source_device_id,
            source_interface_name=payload.source_interface_name,
            target_device_id=payload.target_device_id,
            target_interface_name=payload.target_interface_name,
            allowed_vlans=payload.allowed_vlans,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    link = NetworkLink(
        name=payload.name,
        source_device_id=payload.source_device_id,
        source_interface_name=payload.source_interface_name,
        target_device_id=payload.target_device_id,
        target_interface_name=payload.target_interface_name,
        link_type=payload.link_type,
        admin_status=payload.admin_status,
        status=payload.status,
        bandwidth_mbps=payload.bandwidth_mbps,
        duplex=payload.duplex,
        allowed_vlans=payload.allowed_vlans,
        is_redundant=payload.is_redundant,
    )
    db.add(link)
    db.add(AuditLog(
        username=current_user.username,
        action="TOPOLOGY_LINK_CREATED",
        resource_type="TOPOLOGY",
        resource_id=payload.name,
        details={"source": payload.source_device_id, "target": payload.target_device_id},
        status="SUCCESS",
    ))
    db.commit()
    db.refresh(link)
    return link


@router.get("/dependencies")
def get_dependencies(db: Session = Depends(get_db)):
    links = db.query(NetworkLink).all()
    deps = []
    for l in links:
        deps.append({
            "link": l.name,
            "type": l.link_type,
            "source": l.source_device_id,
            "target": l.target_device_id,
            "redundant": l.is_redundant,
        })
    return {"dependencies": deps}


@router.get("/campus-overview")
def get_campus_overview(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    """Structured campus infrastructure & departmental endpoint summary."""
    devices = db.query(Device).all()
    vlans = db.query(VLAN).order_by(VLAN.vlan_id.asc()).all()
    links = db.query(NetworkLink).all()

    by_type: Dict[str, int] = {}
    online = 0
    offline = 0
    student_endpoints = 0

    for d in devices:
        by_type[d.device_type] = by_type.get(d.device_type, 0) + 1
        if d.status == "online":
            online += 1
        elif d.status == "offline":
            offline += 1
        if d.asset_category == "student_endpoint":
            student_endpoints += 1

    departments = []
    for v in vlans:
        dept_devs = [d for d in devices if d.vlan_id == v.vlan_id]
        dept_eps = [d for d in dept_devs if d.asset_category == "student_endpoint"]
        dept_switches = [d for d in dept_devs if d.device_type == "access_switch" and d.asset_category == "infrastructure"]
        dept_aps = [d for d in dept_devs if d.device_type == "wireless_ap"]
        departments.append({
            "vlan_id": v.vlan_id,
            "name": v.name,
            "department": v.department or v.name,
            "subnet": v.subnet,
            "gateway_ip": v.gateway_ip,
            "status": v.status,
            "student_endpoints": len(dept_eps),
            "access_switches": len(dept_switches),
            "wireless_aps": len(dept_aps),
        })

    return {
        "total_devices": len(devices),
        "online_devices": online,
        "offline_devices": offline,
        "core_switches": by_type.get("l3_switch", 0),
        "distribution_switches": by_type.get("l2_switch", 0),
        "access_switches": by_type.get("access_switch", 0),
        "routers": by_type.get("router", 0),
        "firewalls": by_type.get("firewall", 0),
        "wireless_aps": by_type.get("wireless_ap", 0),
        "servers": by_type.get("server", 0),
        "student_endpoints": student_endpoints,
        "total_links": len(links),
        "departments": departments,
    }


@router.get("/validate")
def validate_campus_topology(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    """Run read-only topology, VLAN, subnet, IP/MAC, and link consistency validation."""
    return TopologyValidationEngine.validate_topology(db)


@router.post("/reset")
def reset_campus_topology(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Explicitly reset campus topology, VLANs, links, and incidents back to the
    deterministic baseline. Preserves User accounts and AuditLog history.
    """
    summary = seed_campus_network(db, force_reset=True)
    db.add(AuditLog(
        username=current_user.username,
        action="CAMPUS_TOPOLOGY_RESET",
        resource_type="TOPOLOGY",
        resource_id="CAMPUS_BASELINE",
        details={
            "reset_scope": "devices,interfaces,links,vlans,incidents,remediations,snapshots",
            "preserved": "users,audit_logs",
            **summary,
        },
        status="SUCCESS",
    ))
    db.commit()
    return {"status": "reset_complete", **summary}
