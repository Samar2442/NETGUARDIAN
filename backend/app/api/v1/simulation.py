from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import FaultScenario, User
from app.services.fault_injection_engine import (
    SUPPORTED_FAULT_TYPES,
    FaultInjectionEngine,
    FaultInjectionError,
)
from app.services.telemetry_scheduler import telemetry_scheduler
from app.core.dependencies import require_admin, require_viewer

router = APIRouter(prefix="/simulation", tags=["Fault Simulation"])


class FaultCreateRequest(BaseModel):
    scenario_type: str
    target_device_id: str
    scenario_name: Optional[str] = Field(default=None, max_length=120)
    target_interface_id: Optional[str] = None
    target_link_id: Optional[str] = None
    severity: str = "HIGH"
    max_duration_seconds: int = Field(default=1800, ge=1, le=3600)
    parameters: Dict[str, Any] = Field(default_factory=dict)


@router.get("/scenarios")
def list_supported_scenarios(current_user: User = Depends(require_viewer)) -> List[Dict[str, str]]:
    return [
        {"type": "INTERFACE_DOWN", "description": "Simulate interface operational DOWN and zero traffic"},
        {"type": "HIGH_CPU", "description": "Simulate >90% CPU utilization and elevated temperature"},
        {"type": "MEMORY_PRESSURE", "description": "Simulate >90% memory utilization"},
        {"type": "CONGESTION", "description": "Simulate >90% interface utilization, discards, and latency"},
        {"type": "PACKET_LOSS", "description": "Simulate elevated packet loss and unstable latency"},
        {"type": "DEVICE_OFFLINE", "description": "Simulate complete device outage and downstream impact"},
        {"type": "LINK_FAILURE", "description": "Simulate network link failure respecting redundant paths"},
    ]


@router.get("/faults")
def list_faults(
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    query = db.query(FaultScenario)
    if status:
        query = query.filter(FaultScenario.status == status.strip().upper())
    rows = query.order_by(FaultScenario.started_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "scenario_name": r.scenario_name,
            "scenario_type": r.scenario_type,
            "target_device_id": r.target_device_id,
            "target_interface_id": r.target_interface_id,
            "target_link_id": r.target_link_id,
            "severity": r.severity,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "ended_at": r.ended_at.isoformat() if r.ended_at else None,
            "created_by": r.created_by,
            "telemetry_source": r.telemetry_source,
        }
        for r in rows
    ]


@router.post("/faults", status_code=201)
def inject_fault(
    payload: FaultCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        res = FaultInjectionEngine.inject_fault(
            db=db,
            scenario_type=payload.scenario_type,
            target_device_id=payload.target_device_id,
            created_by=current_user.username,
            scenario_name=payload.scenario_name,
            target_interface_id=payload.target_interface_id,
            target_link_id=payload.target_link_id,
            severity=payload.severity,
            max_duration_seconds=payload.max_duration_seconds,
            parameters=payload.parameters,
        )
        f = res["fault"]
        return {
            "fault_id": f.id,
            "scenario_name": f.scenario_name,
            "scenario_type": f.scenario_type,
            "status": f.status,
            "telemetry_source": f.telemetry_source,
            "simulation_notice": res["simulation_notice"],
            "telemetry": res["telemetry"],
            "blast_radius": res["blast_radius"],
        }
    except FaultInjectionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/faults/{fault_id}/recover")
def recover_fault(
    fault_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        return FaultInjectionEngine.recover_fault(db=db, fault_id=fault_id, recovered_by=current_user.username)
    except FaultInjectionError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
def get_simulation_status(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    active_faults = db.query(FaultScenario).filter(FaultScenario.status == "ACTIVE").count()
    return {
        "mode": "SIMULATION",
        "simulation_notice": "SIMULATION MODE — NO REAL NETWORK DEVICE IS MODIFIED",
        "scheduler_running": telemetry_scheduler.is_running,
        "cycles_completed": telemetry_scheduler.cycles_completed,
        "active_faults": active_faults,
        "supported_fault_types": sorted(SUPPORTED_FAULT_TYPES),
    }
