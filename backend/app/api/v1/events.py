from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import Event, User
from app.schemas import EventResponse
from app.core.dependencies import require_engineer, require_viewer

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("", response_model=List[EventResponse])
def list_events(
    severity: Optional[str] = None,
    device_id: Optional[str] = None,
    event_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    query = db.query(Event)
    if severity:
        query = query.filter(Event.severity.ilike(severity.strip()))
    if device_id:
        query = query.filter((Event.device_id == device_id) | (Event.source_id == device_id))
    if event_type:
        query = query.filter(Event.event_type == event_type.strip().upper())
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(Event.message.ilike(term), Event.source_name.ilike(term)))
    return query.order_by(Event.timestamp.desc()).offset(offset).limit(limit).all()


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    ev = db.query(Event).filter(Event.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    return ev


@router.post("/{event_id}/acknowledge")
def acknowledge_event(
    event_id: str,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    ev = db.query(Event).filter(Event.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    ev.acknowledged = True
    db.commit()
    return {"id": ev.id, "acknowledged": True, "acknowledged_by": current_user.username}
