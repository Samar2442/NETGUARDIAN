from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import Device, DeviceTelemetry, InterfaceTelemetry, NetworkInterface


class TelemetryNormalizer:
    """
    Normalizes SIMULATION, LAB, and PRODUCTION device/interface metrics
    into DeviceTelemetry & InterfaceTelemetry with explicit source & quality tags.
    """

    @staticmethod
    def classify_freshness(
        latest_timestamp: Optional[datetime],
        device_status: Optional[str] = None,
        threshold_seconds: Optional[int] = None,
    ) -> str:
        if (device_status or "").lower() == "unknown":
            return "UNKNOWN"
        if latest_timestamp is None:
            return "MISSING"
        if (device_status or "").lower() == "offline":
            return "STALE"
        limit = threshold_seconds if threshold_seconds is not None else settings.TELEMETRY_FRESHNESS_SECONDS
        ts = latest_timestamp.replace(tzinfo=timezone.utc) if latest_timestamp.tzinfo is None else latest_timestamp
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return "FRESH" if age <= limit else "STALE"

    @staticmethod
    def record_device_metrics(
        db: Session,
        device_id: Optional[str],
        device_name: str,
        telemetry_source: str,
        collection_method: str,
        cpu_pct: Optional[float],
        mem_pct: Optional[float],
        availability_pct: float = 100.0,
        latency_ms: float = 2.0,
        packet_loss_pct: float = 0.0,
        data_quality: str = "VALID",
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        src = telemetry_source.upper()
        if src not in {"SIMULATION", "LAB", "PRODUCTION"}:
            src = "LAB"

        if device_id:
            db.add(DeviceTelemetry(
                device_id=device_id,
                timestamp=now,
                cpu_usage_pct=float(cpu_pct or 0.0),
                memory_usage_pct=float(mem_pct or 0.0),
                availability_pct=availability_pct,
                latency_ms=latency_ms,
                packet_loss_pct=packet_loss_pct,
                telemetry_source=src,
                collection_method=collection_method,
                data_quality=data_quality,
            ))
            db.commit()

        return {
            "source_device": device_name,
            "telemetry_source": src,
            "collection_method": collection_method,
            "collection_timestamp": now.isoformat(),
            "success": True,
            "data_quality": data_quality,
            "metrics": [
                {"metric_name": "cpu_utilization", "metric_value": cpu_pct, "unit": "%"},
                {"metric_name": "memory_utilization", "metric_value": mem_pct, "unit": "%"},
            ],
        }

    @staticmethod
    def record_interface_metrics(
        db: Session,
        device_id: str,
        iface_name: str,
        telemetry_source: str,
        collection_method: str,
        oper_status: str = "up",
        utilization_pct: float = 0.0,
        input_errors: int = 0,
        output_errors: int = 0,
        inbound_bps: float = 0.0,
        outbound_bps: float = 0.0,
    ) -> Optional[InterfaceTelemetry]:
        iface = db.query(NetworkInterface).filter(
            NetworkInterface.device_id == device_id,
            NetworkInterface.name == iface_name,
        ).first()
        if not iface:
            return None
        row = InterfaceTelemetry(
            interface_id=iface.id,
            device_id=device_id,
            timestamp=datetime.now(timezone.utc),
            inbound_bps=inbound_bps,
            outbound_bps=outbound_bps,
            utilization_pct=utilization_pct,
            input_errors=input_errors,
            output_errors=output_errors,
            operational_status=oper_status,
            telemetry_source=telemetry_source.upper(),
            collection_method=collection_method,
            data_quality="VALID",
        )
        db.add(row)
        db.commit()
        return row

    @staticmethod
    def detect_stale_telemetry(db: Session, max_age_seconds: int = 120) -> List[Dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        devs = db.query(Device).filter(Device.environment.in_(["LAB", "PRODUCTION"])).all()
        stale: List[Dict[str, Any]] = []
        for d in devs:
            latest = (
                db.query(DeviceTelemetry)
                .filter(DeviceTelemetry.device_id == d.id)
                .order_by(DeviceTelemetry.timestamp.desc())
                .first()
            )
            ts = latest.timestamp.replace(tzinfo=timezone.utc) if latest and latest.timestamp.tzinfo is None else (
                latest.timestamp if latest else None
            )
            if not ts or ts < cutoff:
                stale.append({
                    "device_id": d.id,
                    "hostname": d.hostname,
                    "environment": d.environment,
                    "last_sample_timestamp": ts.isoformat() if ts else None,
                    "status": "STALE",
                })
        return stale
