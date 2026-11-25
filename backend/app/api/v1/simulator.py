from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from app.database.session import get_db
from app.models import AuditLog, User
from app.core.dependencies import require_viewer, require_engineer
from app.engines.digital_twin.digital_twin_engine import DigitalTwinEngine
from app.engines.blast_radius.blast_radius_engine import BlastRadiusEngine

router = APIRouter(prefix="/simulator", tags=["Digital Twin Simulator"])


@router.get("/topology")
def get_sim_topology(
    include_endpoints: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return DigitalTwinEngine.get_topology_payload(db, include_endpoints=include_endpoints)


@router.get("/state")
def get_twin_state(
    target_name: Optional[str] = Query(default=None),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    return DigitalTwinEngine.get_intelligence_state(db, target_name=target_name)


@router.get("/recovery-status")
def get_recovery_status(
    target_name: Optional[str] = Query(default=None),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    return DigitalTwinEngine.get_intelligence_state(db, target_name=target_name)


@router.post("/run")
def run_simulation(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db)
):
    scenario_type = payload.get("scenario_type", "vlan_removed_from_trunk")
    target_name = payload.get("target_name", "HQ-Access-SW-02")
    parameters = payload.get("parameters", {"vlan_id": 30})

    result = DigitalTwinEngine.simulate_failure(
        db=db,
        scenario_type=scenario_type,
        target_name=target_name,
        parameters=parameters
    )
    return result


@router.post("/compare")
def compare_before_after_state(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    scenario_type = payload.get("scenario_type", "uplink_failure")
    target_name = payload.get("target_name", "SW-IT-01")
    parameters = payload.get("parameters", {})

    before = DigitalTwinEngine.get_intelligence_state(db, target_name=target_name)
    prediction = DigitalTwinEngine.simulate_failure(
        db=db,
        scenario_type=scenario_type,
        target_name=target_name,
        parameters=parameters,
    )
    db.add(AuditLog(
        username=current_user.username,
        action="DIGITAL_TWIN_COMPARE",
        resource_type="DIGITAL_TWIN",
        resource_id=target_name,
        details={"scenario_type": scenario_type, "severity": prediction.get("severity")},
        status="SUCCESS",
    ))
    db.commit()
    return {
        "before_state": before,
        "predicted_after_state": prediction,
    }


@router.get("/blast-radius")
def get_blast_radius(
    target_type: str = "vlan",
    target_id: str = "HQ-Access-SW-02",
    db: Session = Depends(get_db)
):
    return BlastRadiusEngine.calculate_blast_radius(db, target_type, target_id)
