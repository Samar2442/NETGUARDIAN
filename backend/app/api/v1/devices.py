from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from app.database.session import get_db
from app.models import Device, NetworkInterface, AuditLog
from app.schemas import DeviceResponse, DeviceCreate, DeviceUpdate, InterfaceResponse

router = APIRouter(prefix="/devices", tags=["Devices"])

@router.get("", response_model=List[DeviceResponse])
def get_devices(
    device_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Device)
    if device_type:
        query = query.filter(Device.device_type == device_type)
    if status:
        query = query.filter(Device.status == status)
    return query.all()

@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(device_id: str, db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    return dev

@router.post("", response_model=DeviceResponse)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)):
    existing = db.query(Device).filter(Device.hostname == payload.hostname).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device with this hostname already exists")
    
    dev = Device(
        hostname=payload.hostname,
        management_ip=payload.management_ip,
        device_type=payload.device_type,
        vendor=payload.vendor,
        model=payload.model,
        os_version=payload.os_version,
        location=payload.location,
        status=payload.status,
        monitoring_status=payload.monitoring_status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return dev

@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(device_id: str, payload: DeviceUpdate, db: Session = Depends(get_db)):
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
def delete_device(device_id: str, db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(dev)
    db.commit()
    return {"message": "Device deleted successfully"}
