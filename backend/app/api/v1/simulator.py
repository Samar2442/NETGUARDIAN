from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from app.database.session import get_db
from app.engines.digital_twin.digital_twin_engine import DigitalTwinEngine
from app.engines.blast_radius.blast_radius_engine import BlastRadiusEngine

router = APIRouter(prefix="/simulator", tags=["Digital Twin Simulator"])

@router.get("/topology")
def get_sim_topology(db: Session = Depends(get_db)):
    return DigitalTwinEngine.get_topology_payload(db)

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

@router.get("/blast-radius")
def get_blast_radius(
    target_type: str = "vlan",
    target_id: str = "HQ-Access-SW-02",
    db: Session = Depends(get_db)
):
    return BlastRadiusEngine.calculate_blast_radius(db, target_type, target_id)
