from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import (
    Event,
    Incident,
    IncidentActivity,
    IncidentEscalation,
    IncidentNote,
    User,
)
from app.schemas import EventResponse, IncidentResponse
from app.services.incident_lifecycle import IncidentLifecycleError, IncidentLifecycleService
from app.core.dependencies import require_admin, require_engineer, require_viewer

router = APIRouter(prefix="/incidents", tags=["Incidents"])


class AssignRequest(BaseModel):
    assigned_to: str
    priority: Optional[str] = None


class TransitionRequest(BaseModel):
    target_state: str
    reason: Optional[str] = None


class NoteCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


@router.get("/escalations")
def list_escalations(
    evaluate_now: bool = Query(default=False),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    if evaluate_now:
        IncidentLifecycleService.evaluate_escalations(db)
    rows = db.query(IncidentEscalation).order_by(IncidentEscalation.escalated_at.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "incident_id": r.incident_id,
            "escalation_level": r.escalation_level,
            "severity": r.severity,
            "reason": r.reason,
            "escalated_to": r.escalated_to,
            "escalated_at": r.escalated_at.isoformat(),
        }
        for r in rows
    ]


@router.get("", response_model=List[IncidentResponse])
def get_incidents(
    status: Optional[str] = None,
    lifecycle_state: Optional[str] = None,
    severity: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    vlan_id: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == status)
    if lifecycle_state:
        query = query.filter(Incident.lifecycle_state == lifecycle_state.strip().upper())
    if severity:
        query = query.filter(Incident.severity.ilike(severity.strip()))
    if priority:
        query = query.filter(Incident.priority == priority.strip().upper())
    if assigned_to:
        query = query.filter(Incident.assigned_to == assigned_to.strip())
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Incident.title.ilike(term), Incident.incident_number.ilike(term)))

    rows = query.order_by(Incident.created_at.desc()).offset(offset).limit(limit).all()
    if vlan_id is not None:
        rows = [r for r in rows if vlan_id in (r.affected_vlan_ids or [])]
    return rows


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
        inc.lifecycle_state = "RESOLVED"
    db.commit()
    db.refresh(inc)
    return inc


@router.post("/{incident_id}/acknowledge", response_model=IncidentResponse)
def acknowledge_incident(
    incident_id: str,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    now = datetime.now(timezone.utc)
    inc.acknowledged_at = now
    inc.acknowledged_by = current_user.username
    if (inc.lifecycle_state or "NEW") == "NEW":
        inc.lifecycle_state = "ACKNOWLEDGED"
    if inc.status == "DETECTED":
        inc.status = "INVESTIGATING"
    inc.updated_at = now
    IncidentLifecycleService.record_activity(
        db, inc.id, current_user.username, "INCIDENT_ACKNOWLEDGED", {}
    )
    db.commit()
    db.refresh(inc)
    return inc


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
def resolve_incident(
    incident_id: str,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    now = datetime.now(timezone.utc)
    inc.status = "RESOLVED"
    inc.lifecycle_state = "RESOLVED"
    inc.resolved_at = now
    inc.updated_at = now
    IncidentLifecycleService.record_activity(
        db, inc.id, current_user.username, "INCIDENT_RESOLVED", {}
    )
    db.commit()
    db.refresh(inc)
    return inc


@router.post("/{incident_id}/assign", response_model=IncidentResponse)
def assign_incident(
    incident_id: str,
    payload: AssignRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        return IncidentLifecycleService.assign_incident(
            db=db,
            incident_id=incident_id,
            assignee_username=payload.assigned_to,
            actor=current_user.username,
            priority=payload.priority,
        )
    except IncidentLifecycleError as e:
        code = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/{incident_id}/transition", response_model=IncidentResponse)
def transition_incident(
    incident_id: str,
    payload: TransitionRequest,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    try:
        return IncidentLifecycleService.transition_incident(
            db=db,
            incident_id=incident_id,
            target_state=payload.target_state,
            actor=current_user.username,
            reason=payload.reason,
        )
    except IncidentLifecycleError as e:
        code = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.post("/{incident_id}/notes")
def add_incident_note(
    incident_id: str,
    payload: NoteCreateRequest,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        note = IncidentLifecycleService.add_note(
            db=db,
            incident_id=incident_id,
            author=current_user.username,
            content=payload.content,
        )
        return {
            "id": note.id,
            "incident_id": note.incident_id,
            "author": note.author,
            "content": note.content,
            "created_at": note.created_at.isoformat(),
        }
    except IncidentLifecycleError as e:
        code = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=code, detail=str(e))


@router.get("/{incident_id}/notes")
def list_incident_notes(
    incident_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    rows = db.query(IncidentNote).filter(IncidentNote.incident_id == incident_id).order_by(IncidentNote.created_at.asc()).all()
    return [
        {"id": n.id, "incident_id": n.incident_id, "author": n.author, "content": n.content, "created_at": n.created_at.isoformat()}
        for n in rows
    ]


@router.get("/{incident_id}/timeline")
def get_incident_timeline(
    incident_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    rows = db.query(IncidentActivity).filter(IncidentActivity.incident_id == incident_id).order_by(IncidentActivity.timestamp.asc()).all()
    return [
        {
            "id": a.id,
            "actor": a.actor,
            "action": a.action,
            "details": a.details,
            "timestamp": a.timestamp.isoformat(),
        }
        for a in rows
    ]


@router.get("/{incident_id}/related-events", response_model=List[EventResponse])
def get_incident_related_events(
    incident_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return db.query(Event).filter(Event.incident_id == incident_id).order_by(Event.timestamp.asc()).all()
