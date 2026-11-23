from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.models import VLAN
from app.schemas import VLANResponse, VLANCreate

router = APIRouter(prefix="/vlans", tags=["VLANs"])

@router.get("", response_model=List[VLANResponse])
def get_vlans(db: Session = Depends(get_db)):
    return db.query(VLAN).order_by(VLAN.vlan_id.asc()).all()

@router.post("", response_model=VLANResponse)
def create_vlan(payload: VLANCreate, db: Session = Depends(get_db)):
    existing = db.query(VLAN).filter(VLAN.vlan_id == payload.vlan_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="VLAN ID already exists")
    
    vlan = VLAN(
        vlan_id=payload.vlan_id,
        name=payload.name,
        description=payload.description,
        subnet=payload.subnet,
        gateway_ip=payload.gateway_ip,
        status=payload.status
    )
    db.add(vlan)
    db.commit()
    db.refresh(vlan)
    return vlan
