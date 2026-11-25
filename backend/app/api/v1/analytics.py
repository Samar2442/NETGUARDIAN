from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.dependencies import require_viewer
from app.database.session import get_db
from app.models import User
from app.services.predictive_analytics import PredictiveAnalyticsService

router = APIRouter(prefix="/analytics", tags=["Predictive Analytics"])


@router.get("/overview")
def get_analytics_overview(
    hours: int = Query(default=24, ge=1, le=168),
    horizon_minutes: int = Query(default=60, ge=15, le=1440),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return PredictiveAnalyticsService.get_overview(db, hours=hours, horizon_minutes=horizon_minutes)


@router.get("/devices/{device_id}")
def get_device_analytics(
    device_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    horizon_minutes: int = Query(default=60, ge=15, le=1440),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    res = PredictiveAnalyticsService.get_device_analytics(db, device_id, hours=hours, horizon_minutes=horizon_minutes)
    if not res:
        raise HTTPException(status_code=404, detail="Device not found")
    return res


@router.get("/interfaces/{interface_id}")
def get_interface_analytics(
    interface_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    horizon_minutes: int = Query(default=60, ge=15, le=1440),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    res = PredictiveAnalyticsService.get_interface_analytics(db, interface_id, hours=hours, horizon_minutes=horizon_minutes)
    if not res:
        raise HTTPException(status_code=404, detail="Interface not found")
    return res


@router.get("/vlans/{vlan_id}")
def get_vlan_analytics(
    vlan_id: int,
    hours: int = Query(default=24, ge=1, le=168),
    horizon_minutes: int = Query(default=60, ge=15, le=1440),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    res = PredictiveAnalyticsService.get_vlan_analytics(db, vlan_id, hours=hours, horizon_minutes=horizon_minutes)
    if not res:
        raise HTTPException(status_code=404, detail="VLAN not found")
    return res


@router.get("/anomalies")
def list_anomalies(
    hours: int = Query(default=24, ge=1, le=168),
    anomaly_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return PredictiveAnalyticsService.list_anomalies(
        db, hours=hours, anomaly_type=anomaly_type, limit=limit, offset=offset
    )


@router.get("/capacity-forecast")
def get_capacity_forecast(
    hours: int = Query(default=24, ge=1, le=168),
    horizon_minutes: int = Query(default=60, ge=15, le=1440),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return PredictiveAnalyticsService.get_capacity_forecasts(
        db, hours=hours, horizon_minutes=horizon_minutes, limit=limit, offset=offset
    )


@router.get("/trends")
def get_historical_trends(
    entity_type: str = Query(default="device", pattern="^(device|interface)$"),
    entity_id: Optional[str] = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return PredictiveAnalyticsService.get_historical_trends(
        db, entity_type=entity_type, entity_id=entity_id, hours=hours, limit=limit
    )
