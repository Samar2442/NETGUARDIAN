from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database.session import get_db
from app.models import AuditLog, User
from app.schemas import AuditLogResponse
from app.core.dependencies import require_viewer

router = APIRouter(prefix="/audit", tags=["Audit Logs"])

@router.get("", response_model=List[AuditLogResponse])
def get_audit_logs(
    limit: int = 100,
    action: Optional[str] = None,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db)
):
    """Retrieve audit logs. Requires authenticated user with at least VIEWER role."""
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
