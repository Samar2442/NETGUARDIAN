from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from app.database.session import get_db
from app.models import Incident, Diagnosis, RemediationProposal
from app.schemas import IncidentResponse

router = APIRouter(prefix="/incidents", tags=["Incidents"])

@router.get("", response_model=List[IncidentResponse])
def get_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == status)
    if severity:
        query = query.filter(Incident.severity == severity)
    return query.order_by(Incident.created_at.desc()).all()

@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc

@router.put("/{incident_id}/status", response_model=IncidentResponse)
def update_incident_status(incident_id: str, status: str, db: Session = Depends(get_db)):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    inc.status = status.upper()
    inc.updated_at = datetime.now(timezone.utc)
    if status.upper() == "RESOLVED":
        inc.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(inc)
    return inc
