from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.database.session import get_db
from app.models import VLAN, Device, NetworkInterface, User, AuditLog
from app.schemas import VLANResponse, VLANCreate
from app.engines.topology.validation_engine import TopologyValidationEngine
from app.core.dependencies import require_admin, require_viewer

router = APIRouter(prefix="/vlans", tags=["VLANs"])


@router.get("", response_model=List[VLANResponse])
def get_vlans(db: Session = Depends(get_db)):
    return db.query(VLAN).order_by(VLAN.vlan_id.asc()).all()


@router.get("/departments/overview")
def get_department_vlan_overview(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    vlans = db.query(VLAN).order_by(VLAN.vlan_id.asc()).all()
    devices = db.query(Device).all()
    result = []
    for v in vlans:
        eps = [d for d in devices if d.vlan_id == v.vlan_id and d.asset_category == "student_endpoint"]
        switches = [d for d in devices if d.vlan_id == v.vlan_id and d.device_type == "access_switch"]
        aps = [d for d in devices if d.vlan_id == v.vlan_id and d.device_type == "wireless_ap"]
        result.append({
            "id": v.id,
            "vlan_id": v.vlan_id,
            "name": v.name,
            "department": v.department or v.name,
            "subnet": v.subnet,
            "gateway_ip": v.gateway_ip,
            "status": v.status,
            "description": v.description,
            "endpoint_count": len(eps),
            "switch_count": len(switches),
            "ap_count": len(aps),
        })
    return result


@router.get("/{vlan_id}")
def get_vlan_details(
    vlan_id: int,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    vlan = db.query(VLAN).filter(VLAN.vlan_id == vlan_id).first()
    if not vlan:
        raise HTTPException(status_code=404, detail=f"VLAN {vlan_id} not found")

    assoc_devices = db.query(Device).filter(Device.vlan_id == vlan_id).all()
    assoc_ifaces = db.query(NetworkInterface).filter(
        (NetworkInterface.access_vlan == vlan_id)
        | (NetworkInterface.allowed_vlans.contains(str(vlan_id)))
    ).all()

    return {
        "id": vlan.id,
        "vlan_id": vlan.vlan_id,
        "name": vlan.name,
        "department": vlan.department,
        "subnet": vlan.subnet,
        "gateway_ip": vlan.gateway_ip,
        "status": vlan.status,
        "description": vlan.description,
        "endpoint_count": sum(1 for d in assoc_devices if d.asset_category == "student_endpoint"),
        "associated_devices": [
            {"id": d.id, "hostname": d.hostname, "device_type": d.device_type, "ip": d.management_ip}
            for d in assoc_devices[:50]
        ],
        "associated_interfaces_count": len(assoc_ifaces),
    }


@router.post("", response_model=VLANResponse, status_code=201)
def create_vlan(
    payload: VLANCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        TopologyValidationEngine.validate_new_vlan(
            db=db,
            vlan_id=payload.vlan_id,
            subnet=payload.subnet,
            gateway_ip=payload.gateway_ip,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    vlan = VLAN(
        vlan_id=payload.vlan_id,
        name=payload.name,
        department=payload.department,
        description=payload.description,
        subnet=payload.subnet,
        gateway_ip=payload.gateway_ip,
        status=payload.status,
    )
    db.add(vlan)
    db.add(AuditLog(
        username=current_user.username,
        action="VLAN_CREATED",
        resource_type="VLAN",
        resource_id=str(payload.vlan_id),
        details={"name": payload.name, "subnet": payload.subnet, "gateway": payload.gateway_ip},
        status="SUCCESS",
    ))
    db.commit()
    db.refresh(vlan)
    return vlan
