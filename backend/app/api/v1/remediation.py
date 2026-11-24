from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.database.session import get_db
from app.models import RemediationProposal, User
from app.schemas import RemediationResponse
from app.engines.remediation.remediation_engine import RemediationEngine
from app.engines.rollback.rollback_engine import RollbackEngine
from app.core.dependencies import require_admin, require_engineer

router = APIRouter(prefix="/remediation", tags=["Remediation"])

@router.get("", response_model=List[RemediationResponse])
def get_proposals(db: Session = Depends(get_db)):
    return db.query(RemediationProposal).order_by(RemediationProposal.created_at.desc()).all()

@router.get("/{id}", response_model=RemediationResponse)
def get_proposal(id: str, db: Session = Depends(get_db)):
    prop = db.query(RemediationProposal).filter(RemediationProposal.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return prop

@router.post("/{id}/approve", response_model=RemediationResponse)
def approve_proposal(
    id: str,
    payload: Dict[str, str] = Body(default={}),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    approved_by = current_user.username if isinstance(current_user, User) else payload.get("approved_by", "admin")
    prop = RemediationEngine.approve_proposal(db, id, approved_by)
    return prop

@router.post("/{id}/reject", response_model=RemediationResponse)
def reject_proposal(
    id: str,
    payload: Dict[str, str] = Body(default={}),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    rejected_by = current_user.username if isinstance(current_user, User) else payload.get("rejected_by", "admin")
    prop = RemediationEngine.reject_proposal(db, id, rejected_by)
    return prop

@router.post("/{id}/execute")
def execute_remediation(
    id: str,
    payload: Dict[str, str] = Body(default={}),
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db)
):
    executed_by = current_user.username if isinstance(current_user, User) else payload.get("executed_by", "admin")
    res = RemediationEngine.execute_remediation(db, id, executed_by)
    return res

@router.post("/{id}/rollback")
def rollback_remediation(
    id: str,
    payload: Dict[str, str] = Body(default={}),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    username = current_user.username if isinstance(current_user, User) else payload.get("username", "admin")
    prop = db.query(RemediationProposal).filter(RemediationProposal.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    res = RollbackEngine.execute_rollback(db, prop, username)
    return res
