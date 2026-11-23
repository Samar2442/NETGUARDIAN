from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from app.database.session import get_db
from app.models import Event, HealthMetric, Device, NetworkInterface
from app.schemas import EventResponse, HealthOverviewResponse
from app.engines.scoring.health_engine import HealthScoringEngine
from app.engines.monitoring.monitoring_engine import MonitoringEngine

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

@router.get("/overview", response_model=HealthOverviewResponse)
def get_overview(db: Session = Depends(get_db)):
    return HealthScoringEngine.calculate_health(db)

@router.get("/metrics")
def get_metrics_history(limit: int = 24, db: Session = Depends(get_db)):
    metrics = db.query(HealthMetric).order_by(HealthMetric.timestamp.desc()).limit(limit).all()
    return list(reversed(metrics))

@router.get("/events", response_model=List[EventResponse])
def get_events(limit: int = 50, db: Session = Depends(get_db)):
    return db.query(Event).order_by(Event.timestamp.desc()).limit(limit).all()

@router.post("/poll")
def trigger_poll(db: Session = Depends(get_db)):
    res = MonitoringEngine.run_polling_cycle(db)
    return res
