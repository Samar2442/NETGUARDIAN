from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import CampusService, ServiceDependency, User
from app.services.service_intelligence import ServiceIntelligenceEngine
from app.core.dependencies import require_viewer

router = APIRouter(tags=["Service Intelligence & SLA"])


@router.get("/services/summary")
def get_services_summary(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    services = db.query(CampusService).all()
    if not services:
        ServiceIntelligenceEngine.seed_campus_services(db)
        services = db.query(CampusService).all()

    healths = [ServiceIntelligenceEngine.calculate_service_health(db, s) for s in services]
    operational = sum(1 for h in healths if h["status"] == "OPERATIONAL")
    degraded = sum(1 for h in healths if h["status"] in {"DEGRADED", "PARTIALLY_AVAILABLE"})
    outage = sum(1 for h in healths if h["status"] == "OUTAGE")
    return {
        "total_services": len(services),
        "operational": operational,
        "degraded": degraded,
        "outage": outage,
        "overall_service_health_pct": round((operational / max(1, len(services))) * 100.0, 2),
        "data_source": "SIMULATION_DEMONSTRATION",
    }


@router.get("/services")
def list_services(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    services = db.query(CampusService).order_by(CampusService.name.asc()).all()
    if not services:
        ServiceIntelligenceEngine.seed_campus_services(db)
        services = db.query(CampusService).order_by(CampusService.name.asc()).all()

    out = []
    for s in services:
        h = ServiceIntelligenceEngine.calculate_service_health(db, s)
        sla = ServiceIntelligenceEngine.calculate_service_sla(db, s)
        out.append({
            "id": s.id,
            "service_key": s.service_key,
            "name": s.name,
            "description": s.description,
            "service_category": s.service_category,
            "criticality": s.criticality,
            "owner_team": s.owner_team,
            "department_scope": s.department_scope,
            "operational_status": h["status"],
            "sla_target_pct": s.sla_target_pct,
            "availability_pct": sla["availability_pct"],
            "sla_compliant": sla["sla_compliant"],
            "downtime_minutes": sla["downtime_minutes"],
            "active_incidents": h.get("active_incidents", 0),
            "data_source": "SIMULATION_DEMONSTRATION",
        })
    return out


@router.get("/services/{service_id}")
def get_service_detail(
    service_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    s = db.query(CampusService).filter(
        (CampusService.id == service_id) | (CampusService.service_key == service_id)
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Campus service not found")
    h = ServiceIntelligenceEngine.calculate_service_health(db, s)
    sla = ServiceIntelligenceEngine.calculate_service_sla(db, s)
    return {
        "id": s.id,
        "service_key": s.service_key,
        "name": s.name,
        "description": s.description,
        "service_category": s.service_category,
        "criticality": s.criticality,
        "owner_team": s.owner_team,
        "department_scope": s.department_scope,
        "health": h,
        "sla": sla,
    }


@router.get("/services/{service_id}/health")
def get_service_health(
    service_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    s = db.query(CampusService).filter(
        (CampusService.id == service_id) | (CampusService.service_key == service_id)
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Campus service not found")
    return ServiceIntelligenceEngine.calculate_service_health(db, s)


@router.get("/services/{service_id}/dependencies")
def get_service_dependencies(
    service_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    s = db.query(CampusService).filter(
        (CampusService.id == service_id) | (CampusService.service_key == service_id)
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Campus service not found")
    deps = db.query(ServiceDependency).filter(ServiceDependency.service_id == s.id).all()
    return [
        {
            "id": d.id,
            "resource_type": d.resource_type,
            "resource_id": d.resource_id,
            "resource_name": d.resource_name,
            "dependency_role": d.dependency_role,
            "is_critical": d.is_critical,
        }
        for d in deps
    ]


@router.get("/services/{service_id}/sla")
def get_service_sla(
    service_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    s = db.query(CampusService).filter(
        (CampusService.id == service_id) | (CampusService.service_key == service_id)
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Campus service not found")
    return ServiceIntelligenceEngine.calculate_service_sla(db, s)


@router.get("/sla/overview")
def get_sla_overview(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    services = db.query(CampusService).all()
    if not services:
        ServiceIntelligenceEngine.seed_campus_services(db)
        services = db.query(CampusService).all()
    slas = [ServiceIntelligenceEngine.calculate_service_sla(db, s) for s in services]
    compliant = sum(1 for x in slas if x["sla_compliant"])
    return {
        "total_services": len(slas),
        "compliant_services": compliant,
        "compliance_pct": round((compliant / max(1, len(slas))) * 100.0, 2),
        "services": slas,
        "data_source": "SIMULATION_DEMONSTRATION",
    }


@router.get("/sla/metrics")
def get_sla_operational_metrics(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return ServiceIntelligenceEngine.calculate_operational_metrics(db)
