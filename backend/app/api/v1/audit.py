from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models import AuditLog
from app.schemas import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit Logs"])

@router.get("", response_model=List[AuditLogResponse])
def get_audit_logs(
    limit: int = 100,
    action: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
