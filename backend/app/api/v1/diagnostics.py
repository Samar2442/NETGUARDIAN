from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from app.database.session import get_db
from app.models import Incident, Diagnosis
from app.schemas import DiagnosisResponse
from app.engines.diagnosis.rca_engine import RootCauseAnalysisEngine

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])

@router.post("/run", response_model=DiagnosisResponse)
def run_diagnostics(incident_id: str, db: Session = Depends(get_db)):
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    diag = RootCauseAnalysisEngine.diagnose_incident(db, inc)
    db.commit()
    db.refresh(diag)
    return diag

@router.get("/{incident_id}", response_model=DiagnosisResponse)
def get_diagnosis(incident_id: str, db: Session = Depends(get_db)):
    diag = db.query(Diagnosis).filter(Diagnosis.incident_id == incident_id).first()
    if not diag:
        raise HTTPException(status_code=404, detail="Diagnosis not found for this incident")
    return diag

@router.get("/{incident_id}/evidence")
def get_evidence(incident_id: str, db: Session = Depends(get_db)):
    diag = db.query(Diagnosis).filter(Diagnosis.incident_id == incident_id).first()
    if not diag:
        raise HTTPException(status_code=404, detail="Diagnosis not found")
    return {
        "incident_id": incident_id,
        "root_cause": diag.root_cause,
        "confidence": diag.confidence,
        "supporting_evidence": diag.supporting_evidence,
        "contradicting_evidence": diag.contradicting_evidence,
        "evidence_graph": diag.evidence_graph,
        "verification_steps": diag.verification_steps
    }
