from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from app.database.session import get_db
from app.models import RemediationProposal, User
from app.schemas import RemediationResponse
from app.engines.remediation.remediation_engine import RemediationEngine
from app.engines.rollback.rollback_engine import RollbackEngine
from app.engines.remediation.command_validator import (
    CommandValidationError,
    ApprovalBindingError,
    ExecutionLockError,
    ExecutionModeError,
    DuplicateExecutionError,
    RollbackEligibilityError,
)
from app.core.dependencies import require_admin, require_engineer

router = APIRouter(prefix="/remediation", tags=["Remediation"])


class StructuredRemediationCreate(BaseModel):
    incident_id: str
    device_id: str
    title: str
    operation: str
    target_interface: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "low"
    expected_result: str = "Network state restored"
    execution_mode: str = "SIMULATION"


def _handle_remediation_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ExecutionModeError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, (ExecutionLockError, DuplicateExecutionError, ApprovalBindingError)):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, (CommandValidationError, RollbackEligibilityError, ValueError)):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail="Remediation operation failed.")


@router.get("", response_model=List[RemediationResponse])
def get_proposals(db: Session = Depends(get_db)):
    return db.query(RemediationProposal).order_by(RemediationProposal.created_at.desc()).all()


@router.post("", response_model=RemediationResponse, status_code=201)
def create_structured_proposal(
    payload: StructuredRemediationCreate,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    """Create a structured remediation proposal. Arbitrary command strings are never accepted."""
    try:
        return RemediationEngine.create_structured_proposal(
            db=db,
            incident_id=payload.incident_id,
            device_id=payload.device_id,
            title=payload.title,
            operation=payload.operation,
            target_interface=payload.target_interface,
            parameters=payload.parameters,
            risk_level=payload.risk_level,
            expected_result=payload.expected_result,
            execution_mode=payload.execution_mode,
        )
    except Exception as exc:
        raise _handle_remediation_error(exc)


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
    db: Session = Depends(get_db),
):
    prop = db.query(RemediationProposal).filter(RemediationProposal.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    approved_by = current_user.username if isinstance(current_user, User) else payload.get("approved_by", "admin")
    try:
        return RemediationEngine.approve_proposal(db, id, approved_by)
    except Exception as exc:
        raise _handle_remediation_error(exc)


@router.post("/{id}/reject", response_model=RemediationResponse)
def reject_proposal(
    id: str,
    payload: Dict[str, str] = Body(default={}),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    prop = db.query(RemediationProposal).filter(RemediationProposal.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    rejected_by = current_user.username if isinstance(current_user, User) else payload.get("rejected_by", "admin")
    try:
        return RemediationEngine.reject_proposal(db, id, rejected_by)
    except Exception as exc:
        raise _handle_remediation_error(exc)


@router.post("/{id}/execute")
def execute_remediation(
    id: str,
    payload: Dict[str, Any] = Body(default={}),
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    prop = db.query(RemediationProposal).filter(RemediationProposal.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    executed_by = current_user.username if isinstance(current_user, User) else payload.get("executed_by", "admin")
    execution_mode = payload.get("execution_mode") if isinstance(payload, dict) else None
    try:
        return RemediationEngine.execute_remediation(
            db, id, executed_by, execution_mode=execution_mode
        )
    except Exception as exc:
        raise _handle_remediation_error(exc)


@router.post("/{id}/rollback")
def rollback_remediation(
    id: str,
    payload: Dict[str, str] = Body(default={}),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    prop = db.query(RemediationProposal).filter(RemediationProposal.id == id).first()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    username = current_user.username if isinstance(current_user, User) else payload.get("username", "admin")
    try:
        return RollbackEngine.execute_rollback(db, prop, username)
    except Exception as exc:
        raise _handle_remediation_error(exc)
