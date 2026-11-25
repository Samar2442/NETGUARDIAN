from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from app.database.session import get_db
from app.models import Device, AuditLog, User
from app.schemas import DeviceResponse, DeviceCreate, DeviceUpdate
from app.core.dependencies import require_engineer

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.get("", response_model=List[DeviceResponse])
def get_devices(
    device_type: Optional[str] = None,
    status: Optional[str] = None,
    department: Optional[str] = None,
    vlan_id: Optional[int] = None,
    asset_category: Optional[str] = None,
    layer: Optional[str] = None,
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Device)
    if device_type:
        query = query.filter(Device.device_type == device_type)
    if status:
        query = query.filter(Device.status == status)
    if department:
        query = query.filter(Device.department == department)
    if vlan_id is not None:
        query = query.filter(Device.vlan_id == vlan_id)
    if asset_category:
        query = query.filter(Device.asset_category == asset_category)
    if layer:
        query = query.filter(Device.layer == layer)
    return query.offset(offset).limit(limit).all()


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: str, db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    return dev


@router.post("", response_model=DeviceResponse, status_code=201)
def create_device(
    payload: DeviceCreate,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    if db.query(Device).filter(Device.hostname == payload.hostname).first():
        raise HTTPException(status_code=400, detail="Device with this hostname already exists")
    if payload.management_ip and db.query(Device).filter(Device.management_ip == payload.management_ip).first():
        raise HTTPException(status_code=400, detail="Duplicate IP address assignment rejected")
    if payload.mac_address and db.query(Device).filter(Device.mac_address == payload.mac_address).first():
        raise HTTPException(status_code=400, detail="Duplicate MAC address assignment rejected")

    dev = Device(
        hostname=payload.hostname,
        management_ip=payload.management_ip,
        device_type=payload.device_type,
        vendor=payload.vendor,
        model=payload.model,
        os_version=payload.os_version,
        location=payload.location,
        department=payload.department,
        vlan_id=payload.vlan_id,
        mac_address=payload.mac_address,
        connected_switch_id=payload.connected_switch_id,
        connected_interface=payload.connected_interface,
        asset_category=payload.asset_category,
        layer=payload.layer,
        status=payload.status,
        monitoring_status=payload.monitoring_status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(dev)
    db.add(AuditLog(
        username=current_user.username,
        action="DEVICE_CREATED",
        resource_type="DEVICE",
        resource_id=payload.hostname,
        details={"ip": payload.management_ip, "device_type": payload.device_type},
        status="SUCCESS",
    ))
    db.commit()
    db.refresh(dev)
    return dev


@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: str,
    payload: DeviceUpdate,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(dev, key, value)

    dev.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(dev)
    return dev


@router.delete("/{device_id}")
def delete_device(
    device_id: str,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(dev)
    db.commit()
    return {"message": "Device deleted successfully"}
