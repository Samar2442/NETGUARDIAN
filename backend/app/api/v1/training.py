from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.database.session import get_db
from app.models import TrainingScenario, TrainingSession
from app.engines.training.training_engine import TrainingEngine

router = APIRouter(prefix="/training", tags=["CCNA Training Lab"])

@router.get("/scenarios")
def get_scenarios(db: Session = Depends(get_db)):
    scenarios = db.query(TrainingScenario).all()
    return scenarios

@router.post("/inject-fault")
def inject_training_fault(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    scenario_key = payload.get("scenario_key", "vlan_30_trunk_missing")
    username = payload.get("username", "admin")
    result = TrainingEngine.inject_fault(db, scenario_key, username)
    return result

@router.post("/grade-diagnosis")
def grade_diagnosis(
    payload: Dict[str, Any] = Body(...)
):
    expected = payload.get("expected_root_cause", "")
    student_text = payload.get("student_diagnosis", "")
    return TrainingEngine.grade_student_diagnosis(expected, student_text)
