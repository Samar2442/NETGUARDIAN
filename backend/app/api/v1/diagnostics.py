from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.database.session import get_db
from app.models import Incident, Diagnosis, Event, AuditLog, User
from app.schemas import DiagnosisResponse
from app.engines.diagnosis.rca_engine import RootCauseAnalysisEngine
from app.core.dependencies import require_viewer, require_engineer

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])


def _get_diagnosis_or_404(db: Session, incident_id: str) -> Diagnosis:
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    diag = db.query(Diagnosis).filter(Diagnosis.incident_id == incident_id).first()
    if not diag:
        raise HTTPException(status_code=404, detail="Diagnosis not found for this incident")
    return diag


@router.post("/run", response_model=DiagnosisResponse)
def run_diagnostics(
    incident_id: str,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    diag = RootCauseAnalysisEngine.diagnose_incident(db, inc)
    db.add(AuditLog(
        username=current_user.username,
        action="RCA_EXECUTED",
        resource_type="DIAGNOSIS",
        resource_id=inc.id,
        details={"status": diag.status, "confidence": diag.confidence, "category": diag.category},
        status="SUCCESS",
    ))
    db.commit()
    db.refresh(diag)
    return diag


@router.get("/{incident_id}", response_model=DiagnosisResponse)
def get_diagnosis(
    incident_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    return _get_diagnosis_or_404(db, incident_id)


@router.get("/{incident_id}/evidence")
def get_evidence(
    incident_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    diag = _get_diagnosis_or_404(db, incident_id)
    return {
        "incident_id": incident_id,
        "root_cause": diag.root_cause,
        "status": diag.status,
        "confidence": diag.confidence,
        "supporting_evidence": diag.supporting_evidence or [],
        "contradicting_evidence": diag.contradicting_evidence or [],
        "secondary_symptoms": diag.secondary_symptoms or [],
        "independent_failures": diag.independent_failures or [],
        "evidence_graph": diag.evidence_graph or {},
        "verification_steps": diag.verification_steps or [],
        "analysis_timestamp": diag.analysis_timestamp.isoformat() if diag.analysis_timestamp else None,
    }


@router.get("/{incident_id}/related-events")
def get_rca_related_events(
    incident_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    diag = _get_diagnosis_or_404(db, incident_id)
    ev_ids = diag.related_event_ids or []
    events = db.query(Event).filter(Event.id.in_(ev_ids)).order_by(Event.timestamp.asc()).all() if ev_ids else []
    return {
        "incident_id": incident_id,
        "related_event_ids": ev_ids,
        "related_events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "event_code": e.event_code,
                "severity": e.severity,
                "source_name": e.source_name,
                "vlan_id": e.vlan_id,
                "message": e.message,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in events
        ],
        "secondary_symptoms": diag.secondary_symptoms or [],
        "independent_failures": diag.independent_failures or [],
    }


@router.get("/{incident_id}/affected-services")
def get_rca_affected_services(
    incident_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    diag = _get_diagnosis_or_404(db, incident_id)
    return {
        "incident_id": incident_id,
        "affected_devices": diag.affected_devices or [],
        "affected_vlans": diag.affected_vlans or [],
        "affected_services": diag.affected_services or [],
    }


@router.get("/{incident_id}/timeline")
def get_rca_timeline(
    incident_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    diag = _get_diagnosis_or_404(db, incident_id)
    return {
        "incident_id": incident_id,
        "timeline": diag.timeline or [],
    }


@router.get("/{incident_id}/candidates")
def get_rca_candidates(
    incident_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    diag = _get_diagnosis_or_404(db, incident_id)
    return {
        "incident_id": incident_id,
        "status": diag.status,
        "confidence": diag.confidence,
        "candidate_causes": diag.candidate_causes or [],
    }
