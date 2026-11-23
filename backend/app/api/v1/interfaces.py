from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from app.database.session import get_db
from app.models import NetworkInterface, Device
from app.schemas import InterfaceResponse

router = APIRouter(prefix="/interfaces", tags=["Interfaces"])

@router.get("", response_model=List[InterfaceResponse])
def get_interfaces(
    device_id: Optional[str] = None,
    oper_status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(NetworkInterface)
    if device_id:
        query = query.filter(NetworkInterface.device_id == device_id)
    if oper_status:
        query = query.filter(NetworkInterface.oper_status == oper_status)
    return query.all()

@router.get("/{interface_id}", response_model=InterfaceResponse)
def get_interface(interface_id: str, db: Session = Depends(get_db)):
    iface = db.query(NetworkInterface).filter(NetworkInterface.id == interface_id).first()
    if not iface:
        raise HTTPException(status_code=404, detail="Interface not found")
    return iface

@router.put("/{interface_id}/admin-status", response_model=InterfaceResponse)
def toggle_interface_admin_status(interface_id: str, status: str, db: Session = Depends(get_db)):
    iface = db.query(NetworkInterface).filter(NetworkInterface.id == interface_id).first()
    if not iface:
        raise HTTPException(status_code=404, detail="Interface not found")
    
    iface.admin_status = status.lower()
    iface.oper_status = status.lower()
    iface.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(iface)
    return iface
