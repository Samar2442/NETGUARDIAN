from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models import (
    Device,
    DeviceTelemetry,
    Event,
    FaultScenario,
    HealthMetric,
    Incident,
    InterfaceTelemetry,
    NetworkInterface,
    User,
    VLAN,
)
from app.services.telemetry_engine import TelemetryEngine
from app.core.dependencies import require_engineer, require_viewer

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.get("/overview")
def get_telemetry_overview(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    devices = db.query(Device).all()
    ifaces = db.query(NetworkInterface).all()
    active_faults = db.query(FaultScenario).filter(FaultScenario.status == "ACTIVE").count()
    active_incidents = db.query(Incident).filter(Incident.status != "RESOLVED").count()
    critical_alerts = db.query(Event).filter(
        Event.severity.in_(["CRITICAL", "critical", "high", "MAJOR"]),
        Event.resolved == False,
    ).count()

    online = sum(1 for d in devices if d.status == "online")
    degraded = sum(1 for d in devices if d.status == "degraded")
    offline = sum(1 for d in devices if d.status == "offline")
    n = max(1, len(devices))
    avg_cpu = round(sum(d.cpu_percent or 0.0 for d in devices) / n, 2)
    avg_mem = round(sum(d.memory_percent or 0.0 for d in devices) / n, 2)
    avg_util = round(sum(i.bandwidth_utilization_pct or 0.0 for i in ifaces) / max(1, len(ifaces)), 2)

    latest_metric = db.query(HealthMetric).order_by(HealthMetric.timestamp.desc()).first()
    return {
        "telemetry_source": "SIMULATION",
        "timestamp": (latest_metric.timestamp if latest_metric else datetime.now(timezone.utc)).isoformat(),
        "total_devices": len(devices),
        "online_devices": online,
        "degraded_devices": degraded,
        "offline_devices": offline,
        "availability_pct": round(((online + degraded) / n) * 100.0, 2),
        "avg_cpu_pct": avg_cpu,
        "avg_memory_pct": avg_mem,
        "avg_bandwidth_utilization_pct": avg_util,
        "avg_latency_ms": latest_metric.avg_latency_ms if latest_metric else 1.5,
        "avg_packet_loss_pct": latest_metric.avg_packet_loss_pct if latest_metric else 0.0,
        "active_incidents": active_incidents,
        "critical_alerts": critical_alerts,
        "active_faults": active_faults,
    }


@router.get("/devices")
def list_device_telemetry(
    device_type: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    query = db.query(Device)
    if device_type:
        query = query.filter(Device.device_type == device_type)
    if department:
        query = query.filter(Device.department == department)
    if status:
        query = query.filter(Device.status == status)
    if search:
        query = query.filter(Device.hostname.ilike(f"%{search.strip()}%"))

    devs = query.order_by(Device.hostname.asc()).offset(offset).limit(limit).all()
    results = []
    for d in devs:
        latest = (
            db.query(DeviceTelemetry)
            .filter(DeviceTelemetry.device_id == d.id)
            .order_by(DeviceTelemetry.timestamp.desc())
            .first()
        )
        results.append({
            "device_id": d.id,
            "hostname": d.hostname,
            "device_type": d.device_type,
            "department": d.department,
            "management_ip": d.management_ip,
            "cpu_usage_pct": latest.cpu_usage_pct if latest else d.cpu_percent,
            "memory_usage_pct": latest.memory_usage_pct if latest else d.memory_percent,
            "availability_pct": latest.availability_pct if latest else (100.0 if d.status != "offline" else 0.0),
            "latency_ms": latest.latency_ms if latest else 1.5,
            "packet_loss_pct": latest.packet_loss_pct if latest else 0.0,
            "status": d.status,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            "telemetry_source": "SIMULATION",
        })
    return results


@router.get("/devices/{device_id}")
def get_device_telemetry_detail(
    device_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    d = db.query(Device).filter((Device.id == device_id) | (Device.hostname == device_id)).first()
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    latest = (
        db.query(DeviceTelemetry)
        .filter(DeviceTelemetry.device_id == d.id)
        .order_by(DeviceTelemetry.timestamp.desc())
        .first()
    )
    return {
        "device_id": d.id,
        "hostname": d.hostname,
        "device_type": d.device_type,
        "department": d.department,
        "management_ip": d.management_ip,
        "status": d.status,
        "cpu_usage_pct": latest.cpu_usage_pct if latest else d.cpu_percent,
        "memory_usage_pct": latest.memory_usage_pct if latest else d.memory_percent,
        "temperature_celsius": latest.temperature_celsius if latest else 38.0,
        "uptime_seconds": d.uptime_seconds,
        "availability_pct": latest.availability_pct if latest else 100.0,
        "latency_ms": latest.latency_ms if latest else 1.5,
        "packet_loss_pct": latest.packet_loss_pct if latest else 0.0,
        "telemetry_source": "SIMULATION",
    }


@router.get("/devices/{device_id}/history")
def get_device_telemetry_history(
    device_id: str,
    minutes: int = Query(default=60, ge=5, le=1440),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    d = db.query(Device).filter((Device.id == device_id) | (Device.hostname == device_id)).first()
    if not d:
        raise HTTPException(status_code=404, detail="Device not found")
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    rows = (
        db.query(DeviceTelemetry)
        .filter(DeviceTelemetry.device_id == d.id, DeviceTelemetry.timestamp >= cutoff)
        .order_by(DeviceTelemetry.timestamp.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return {
        "device_id": d.id,
        "hostname": d.hostname,
        "telemetry_source": "SIMULATION",
        "points": [
            {
                "timestamp": r.timestamp.isoformat(),
                "cpu_usage_pct": r.cpu_usage_pct,
                "memory_usage_pct": r.memory_usage_pct,
                "latency_ms": r.latency_ms,
                "packet_loss_pct": r.packet_loss_pct,
                "availability_pct": r.availability_pct,
                "status": r.status,
            }
            for r in rows
        ],
    }


@router.get("/interfaces")
def list_interface_telemetry(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    ifaces = db.query(NetworkInterface).offset(offset).limit(limit).all()
    dev_map = {d.id: d.hostname for d in db.query(Device).all()}
    out = []
    for iface in ifaces:
        latest = (
            db.query(InterfaceTelemetry)
            .filter(InterfaceTelemetry.interface_id == iface.id)
            .order_by(InterfaceTelemetry.timestamp.desc())
            .first()
        )
        out.append({
            "interface_id": iface.id,
            "device_id": iface.device_id,
            "device_hostname": dev_map.get(iface.device_id, "unknown"),
            "name": iface.name,
            "operational_status": latest.operational_status if latest else iface.oper_status,
            "inbound_bps": latest.inbound_bps if latest else 0.0,
            "outbound_bps": latest.outbound_bps if latest else 0.0,
            "utilization_pct": latest.utilization_pct if latest else iface.bandwidth_utilization_pct,
            "input_errors": latest.input_errors if latest else iface.in_errors,
            "output_errors": latest.output_errors if latest else iface.out_errors,
            "input_discards": latest.input_discards if latest else 0,
            "output_discards": latest.output_discards if latest else 0,
            "duplex": iface.duplex,
            "telemetry_source": "SIMULATION",
        })
    return out


@router.get("/interfaces/{interface_id}/history")
def get_interface_telemetry_history(
    interface_id: str,
    minutes: int = Query(default=60, ge=5, le=1440),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    iface = db.query(NetworkInterface).filter(NetworkInterface.id == interface_id).first()
    if not iface:
        raise HTTPException(status_code=404, detail="Interface not found")
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    rows = (
        db.query(InterfaceTelemetry)
        .filter(InterfaceTelemetry.interface_id == iface.id, InterfaceTelemetry.timestamp >= cutoff)
        .order_by(InterfaceTelemetry.timestamp.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return {
        "interface_id": iface.id,
        "name": iface.name,
        "telemetry_source": "SIMULATION",
        "points": [
            {
                "timestamp": r.timestamp.isoformat(),
                "inbound_bps": r.inbound_bps,
                "outbound_bps": r.outbound_bps,
                "utilization_pct": r.utilization_pct,
                "input_errors": r.input_errors,
                "output_errors": r.output_errors,
                "operational_status": r.operational_status,
            }
            for r in rows
        ],
    }


@router.get("/vlans")
def get_vlan_telemetry(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    vlans = db.query(VLAN).order_by(VLAN.vlan_id.asc()).all()
    devices = db.query(Device).all()
    open_incidents = db.query(Incident).filter(Incident.status != "RESOLVED").all()

    results = []
    for v in vlans:
        eps = [d for d in devices if d.vlan_id == v.vlan_id and d.asset_category == "student_endpoint"]
        online_eps = sum(1 for d in eps if d.status != "offline")
        offline_eps = len(eps) - online_eps

        # Latest telemetry for endpoints in this VLAN
        ep_ids = [d.id for d in eps]
        avg_lat = 1.4
        avg_loss = 0.0
        if ep_ids:
            latest_telem = (
                db.query(DeviceTelemetry)
                .filter(DeviceTelemetry.device_id.in_(ep_ids))
                .order_by(DeviceTelemetry.timestamp.desc())
                .limit(len(ep_ids))
                .all()
            )
            if latest_telem:
                avg_lat = round(sum(t.latency_ms for t in latest_telem) / len(latest_telem), 2)
                avg_loss = round(sum(t.packet_loss_pct for t in latest_telem) / len(latest_telem), 2)

        active_inc_count = sum(1 for inc in open_incidents if v.vlan_id in (inc.affected_vlan_ids or []))
        switches = [d.hostname for d in devices if d.vlan_id == v.vlan_id and d.device_type == "access_switch"]
        health_pct = round((online_eps / max(1, len(eps))) * 100.0, 2)

        results.append({
            "vlan_id": v.vlan_id,
            "department": v.department or v.name,
            "subnet": v.subnet,
            "total_endpoints": len(eps),
            "online_endpoints": online_eps,
            "offline_endpoints": offline_eps,
            "vlan_health_pct": health_pct,
            "avg_latency_ms": avg_lat,
            "avg_packet_loss_pct": avg_loss,
            "active_incidents": active_inc_count,
            "switches": switches,
            "telemetry_source": "SIMULATION",
        })
    return results


@router.get("/health")
def get_telemetry_health_history(
    limit: int = Query(default=24, ge=1, le=200),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    metrics = db.query(HealthMetric).order_by(HealthMetric.timestamp.desc()).limit(limit).all()
    metrics.reverse()
    return {
        "telemetry_source": "SIMULATION",
        "history": [
            {
                "timestamp": m.timestamp.isoformat(),
                "overall_health": m.overall_health,
                "availability": m.availability,
                "performance": m.performance,
                "avg_latency_ms": m.avg_latency_ms,
                "avg_packet_loss_pct": m.avg_packet_loss_pct,
                "active_incidents": m.active_incidents,
            }
            for m in metrics
        ],
    }


@router.post("/collect")
def trigger_manual_collection(
    seed: Optional[int] = None,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return TelemetryEngine.collect_once(db, seed=seed)
