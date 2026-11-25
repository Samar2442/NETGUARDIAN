from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.models import (
    Device,
    DeviceTelemetry,
    InterfaceTelemetry,
    NetworkInterface,
    VLAN,
)
from app.services.anomaly_detection import AnomalyDetectionService, compute_stats
from app.services.capacity_forecasting import CapacityForecastingService


class PredictiveAnalyticsService:
    """
    Orchestrates statistical trend analysis, anomaly detection, and capacity
    forecasting over existing DeviceTelemetry and InterfaceTelemetry tables.
    """

    @staticmethod
    def _cutoff(hours: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(hours=hours)

    @staticmethod
    def get_device_analytics(
        db: Session,
        device_id: str,
        hours: int = 24,
        horizon_minutes: int = 60,
    ) -> Optional[Dict[str, Any]]:
        dev = db.query(Device).filter((Device.id == device_id) | (Device.hostname == device_id)).first()
        if not dev:
            return None

        cutoff = PredictiveAnalyticsService._cutoff(hours)
        src_env = (dev.environment or "SIMULATION").upper()
        rows = (
            db.query(DeviceTelemetry)
            .filter(
                DeviceTelemetry.device_id == dev.id,
                DeviceTelemetry.timestamp >= cutoff,
                DeviceTelemetry.telemetry_source == src_env,
            )
            .order_by(DeviceTelemetry.timestamp.asc())
            .limit(500)
            .all()
        )
        n = len(rows)
        last_ts = rows[-1].timestamp.isoformat() if rows else None

        if n < 3:
            return {
                "device_id": dev.id,
                "hostname": dev.hostname,
                "status": "INSUFFICIENT_DATA",
                "classification": "INSUFFICIENT_DATA",
                "data_source": src_env,
                "analysis_period_hours": hours,
                "sample_count": n,
                "last_sample_timestamp": last_ts,
                "forecast_horizon_minutes": horizon_minutes,
                "confidence": 0.0,
                "anomalies": [],
                "forecasts": [],
                "trends": {},
            }

        timestamps = [r.timestamp for r in rows]
        cpu_vals = [float(r.cpu_usage_pct or 0.0) for r in rows]
        mem_vals = [float(r.memory_usage_pct or 0.0) for r in rows]
        loss_vals = [float(r.packet_loss_pct or 0.0) for r in rows]
        lat_vals = [float(r.latency_ms or 0.0) for r in rows]

        anomalies: List[Dict[str, Any]] = []
        for spec in (
            ("cpu_usage_pct", "CPU_ANOMALY", cpu_vals, 80.0, 92.0),
            ("memory_usage_pct", "MEMORY_ANOMALY", mem_vals, 82.0, 93.0),
            ("packet_loss_pct", "PACKET_LOSS_ANOMALY", loss_vals, 2.0, 8.0),
            ("latency_ms", "TRAFFIC_DEVIATION", lat_vals, 40.0, 100.0),
        ):
            anom = AnomalyDetectionService.evaluate_metric_series(
                "device", dev.id, dev.hostname, spec[0], spec[1],
                spec[2], timestamps, spec[3], spec[4], hours,
            )
            if anom:
                anomalies.append(anom)

        forecasts = [
            CapacityForecastingService.forecast_metric(
                "device", dev.id, dev.hostname, "cpu_usage_pct",
                cpu_vals, timestamps, horizon_minutes, 85.0, hours,
            ),
            CapacityForecastingService.forecast_metric(
                "device", dev.id, dev.hostname, "memory_usage_pct",
                mem_vals, timestamps, horizon_minutes, 85.0, hours,
            ),
        ]

        return {
            "device_id": dev.id,
            "hostname": dev.hostname,
            "device_type": dev.device_type,
            "department": dev.department,
            "status": "ANOMALY_DETECTED" if anomalies else "NORMAL",
            "classification": "OBSERVED",
            "data_source": "SIMULATION",
            "analysis_period_hours": hours,
            "sample_count": n,
            "last_sample_timestamp": last_ts,
            "forecast_horizon_minutes": horizon_minutes,
            "confidence": round(min(95.0, 55.0 + n * 1.5), 1),
            "trends": {
                "cpu": compute_stats(cpu_vals),
                "memory": compute_stats(mem_vals),
                "packet_loss": compute_stats(loss_vals),
                "latency": compute_stats(lat_vals),
            },
            "anomalies": anomalies,
            "forecasts": forecasts,
        }

    @staticmethod
    def get_interface_analytics(
        db: Session,
        interface_id: str,
        hours: int = 24,
        horizon_minutes: int = 60,
    ) -> Optional[Dict[str, Any]]:
        iface = db.query(NetworkInterface).filter(NetworkInterface.id == interface_id).first()
        if not iface:
            return None
        dev = iface.device
        label = f"{dev.hostname if dev else 'device'}:{iface.name}"

        cutoff = PredictiveAnalyticsService._cutoff(hours)
        rows = (
            db.query(InterfaceTelemetry)
            .filter(InterfaceTelemetry.interface_id == iface.id, InterfaceTelemetry.timestamp >= cutoff)
            .order_by(InterfaceTelemetry.timestamp.asc())
            .limit(500)
            .all()
        )
        n = len(rows)
        last_ts = rows[-1].timestamp.isoformat() if rows else None

        if n < 3:
            return {
                "interface_id": iface.id,
                "interface_name": label,
                "status": "INSUFFICIENT_DATA",
                "classification": "INSUFFICIENT_DATA",
                "data_source": "SIMULATION",
                "analysis_period_hours": hours,
                "sample_count": n,
                "last_sample_timestamp": last_ts,
                "forecast_horizon_minutes": horizon_minutes,
                "confidence": 0.0,
                "anomalies": [],
                "forecasts": [],
                "trends": {},
            }

        timestamps = [r.timestamp for r in rows]
        util_vals = [float(r.utilization_pct or 0.0) for r in rows]
        err_vals = [float((r.input_errors or 0) + (r.output_errors or 0)) for r in rows]
        disc_vals = [float((r.input_discards or 0) + (r.output_discards or 0)) for r in rows]

        anomalies: List[Dict[str, Any]] = []
        for spec in (
            ("utilization_pct", "BANDWIDTH_ANOMALY", util_vals, 75.0, 90.0),
            ("interface_errors", "INTERFACE_ERROR_ANOMALY", err_vals, 5.0, 20.0),
            ("interface_discards", "PACKET_LOSS_ANOMALY", disc_vals, 5.0, 20.0),
        ):
            anom = AnomalyDetectionService.evaluate_metric_series(
                "interface", iface.id, label, spec[0], spec[1],
                spec[2], timestamps, spec[3], spec[4], hours,
            )
            if anom:
                anomalies.append(anom)

        forecasts = [
            CapacityForecastingService.forecast_metric(
                "interface", iface.id, label, "utilization_pct",
                util_vals, timestamps, horizon_minutes, 85.0, hours,
            )
        ]

        return {
            "interface_id": iface.id,
            "interface_name": label,
            "status": "CONGESTED" if any(u >= 80.0 for u in util_vals[-2:]) else (
                "ANOMALY_DETECTED" if anomalies else "NORMAL"
            ),
            "classification": "OBSERVED",
            "data_source": "SIMULATION",
            "analysis_period_hours": hours,
            "sample_count": n,
            "last_sample_timestamp": last_ts,
            "forecast_horizon_minutes": horizon_minutes,
            "confidence": round(min(95.0, 55.0 + n * 1.5), 1),
            "trends": {
                "utilization": compute_stats(util_vals),
                "errors": compute_stats(err_vals),
                "discards": compute_stats(disc_vals),
            },
            "anomalies": anomalies,
            "forecasts": forecasts,
        }

    @staticmethod
    def get_vlan_analytics(db: Session, vlan_id: int, hours: int = 24, horizon_minutes: int = 60) -> Optional[Dict[str, Any]]:
        vlan = db.query(VLAN).filter(VLAN.vlan_id == vlan_id).first()
        if not vlan:
            return None

        devs = db.query(Device).filter(Device.vlan_id == vlan_id).limit(100).all()
        dev_ids = [d.id for d in devs]
        cutoff = PredictiveAnalyticsService._cutoff(hours)
        rows = (
            db.query(DeviceTelemetry)
            .filter(DeviceTelemetry.device_id.in_(dev_ids), DeviceTelemetry.timestamp >= cutoff)
            .order_by(DeviceTelemetry.timestamp.asc())
            .limit(500)
            .all()
        ) if dev_ids else []

        n = len(rows)
        last_ts = rows[-1].timestamp.isoformat() if rows else None
        if n < 3:
            return {
                "vlan_id": vlan_id,
                "vlan_name": vlan.name,
                "department": vlan.department,
                "status": "INSUFFICIENT_DATA",
                "classification": "INSUFFICIENT_DATA",
                "data_source": "SIMULATION",
                "analysis_period_hours": hours,
                "sample_count": n,
                "last_sample_timestamp": last_ts,
                "forecast_horizon_minutes": horizon_minutes,
                "confidence": 0.0,
                "trends": {},
            }

        cpu_vals = [float(r.cpu_usage_pct or 0.0) for r in rows]
        loss_vals = [float(r.packet_loss_pct or 0.0) for r in rows]
        lat_vals = [float(r.latency_ms or 0.0) for r in rows]
        return {
            "vlan_id": vlan_id,
            "vlan_name": vlan.name,
            "department": vlan.department,
            "status": "DEGRADED" if vlan.status != "active" else "NORMAL",
            "classification": "OBSERVED",
            "data_source": "SIMULATION",
            "analysis_period_hours": hours,
            "sample_count": n,
            "last_sample_timestamp": last_ts,
            "forecast_horizon_minutes": horizon_minutes,
            "confidence": round(min(95.0, 55.0 + min(n, 30) * 1.2), 1),
            "trends": {
                "cpu": compute_stats(cpu_vals),
                "packet_loss": compute_stats(loss_vals),
                "latency": compute_stats(lat_vals),
            },
        }

    @staticmethod
    def list_anomalies(
        db: Session,
        hours: int = 24,
        anomaly_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        cutoff = PredictiveAnalyticsService._cutoff(hours)
        infra_devs = (
            db.query(Device)
            .filter(Device.asset_category != "student_endpoint")
            .order_by(Device.hostname.asc())
            .limit(40)
            .all()
        )
        dev_ids = [d.id for d in infra_devs]
        dev_map = {d.id: d for d in infra_devs}

        rows = (
            db.query(DeviceTelemetry)
            .filter(DeviceTelemetry.device_id.in_(dev_ids), DeviceTelemetry.timestamp >= cutoff)
            .order_by(DeviceTelemetry.timestamp.asc())
            .limit(1500)
            .all()
        ) if dev_ids else []

        grouped: Dict[str, List[DeviceTelemetry]] = {}
        for r in rows:
            grouped.setdefault(r.device_id, []).append(r)

        anomalies: List[Dict[str, Any]] = []
        for did, series in grouped.items():
            d = dev_map[did]
            ts = [r.timestamp for r in series]
            for metric, atype, vals, warn, crit in (
                ("cpu_usage_pct", "CPU_ANOMALY", [float(r.cpu_usage_pct or 0) for r in series], 80.0, 92.0),
                ("memory_usage_pct", "MEMORY_ANOMALY", [float(r.memory_usage_pct or 0) for r in series], 82.0, 93.0),
                ("packet_loss_pct", "PACKET_LOSS_ANOMALY", [float(r.packet_loss_pct or 0) for r in series], 2.0, 8.0),
                ("latency_ms", "TRAFFIC_DEVIATION", [float(r.latency_ms or 0) for r in series], 40.0, 100.0),
            ):
                if anomaly_type and atype != anomaly_type:
                    continue
                anom = AnomalyDetectionService.evaluate_metric_series(
                    "device", d.id, d.hostname, metric, atype, vals, ts, warn, crit, hours
                )
                if anom:
                    anomalies.append(anom)

        # Also check interface bandwidth/errors
        ifaces = db.query(NetworkInterface).filter(NetworkInterface.is_uplink == True).limit(30).all()
        if_ids = [i.id for i in ifaces]
        if_map = {i.id: i for i in ifaces}
        if_rows = (
            db.query(InterfaceTelemetry)
            .filter(InterfaceTelemetry.interface_id.in_(if_ids), InterfaceTelemetry.timestamp >= cutoff)
            .order_by(InterfaceTelemetry.timestamp.asc())
            .limit(1500)
            .all()
        ) if if_ids else []
        if_grouped: Dict[str, List[InterfaceTelemetry]] = {}
        for r in if_rows:
            if_grouped.setdefault(r.interface_id, []).append(r)

        for iid, series in if_grouped.items():
            iface = if_map[iid]
            label = f"{iface.device.hostname if iface.device else 'device'}:{iface.name}"
            ts = [r.timestamp for r in series]
            for metric, atype, vals, warn, crit in (
                ("utilization_pct", "BANDWIDTH_ANOMALY", [float(r.utilization_pct or 0) for r in series], 75.0, 90.0),
                ("interface_errors", "INTERFACE_ERROR_ANOMALY", [float((r.input_errors or 0) + (r.output_errors or 0)) for r in series], 5.0, 20.0),
            ):
                if anomaly_type and atype != anomaly_type:
                    continue
                anom = AnomalyDetectionService.evaluate_metric_series(
                    "interface", iface.id, label, metric, atype, vals, ts, warn, crit, hours
                )
                if anom:
                    anomalies.append(anom)

        total = len(anomalies)
        return {
            "data_source": "SIMULATION",
            "analysis_period_hours": hours,
            "total": total,
            "limit": limit,
            "offset": offset,
            "anomalies": anomalies[offset: offset + limit],
        }

    @staticmethod
    def get_capacity_forecasts(
        db: Session,
        hours: int = 24,
        horizon_minutes: int = 60,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        cutoff = PredictiveAnalyticsService._cutoff(hours)
        infra_devs = (
            db.query(Device)
            .filter(Device.asset_category != "student_endpoint")
            .order_by(Device.hostname.asc())
            .limit(30)
            .all()
        )
        dev_ids = [d.id for d in infra_devs]
        dev_map = {d.id: d for d in infra_devs}

        rows = (
            db.query(DeviceTelemetry)
            .filter(DeviceTelemetry.device_id.in_(dev_ids), DeviceTelemetry.timestamp >= cutoff)
            .order_by(DeviceTelemetry.timestamp.asc())
            .limit(1500)
            .all()
        ) if dev_ids else []

        grouped: Dict[str, List[DeviceTelemetry]] = {}
        for r in rows:
            grouped.setdefault(r.device_id, []).append(r)

        forecasts: List[Dict[str, Any]] = []
        for d in infra_devs:
            series = grouped.get(d.id, [])
            ts = [r.timestamp for r in series]
            forecasts.append(CapacityForecastingService.forecast_metric(
                "device", d.id, d.hostname, "cpu_usage_pct",
                [float(r.cpu_usage_pct or 0) for r in series], ts, horizon_minutes, 85.0, hours,
            ))

        total = len(forecasts)
        warnings_count = sum(1 for f in forecasts if f.get("predictive_warning"))
        return {
            "data_source": "SIMULATION",
            "analysis_period_hours": hours,
            "forecast_horizon_minutes": horizon_minutes,
            "total": total,
            "predictive_warnings_count": warnings_count,
            "limit": limit,
            "offset": offset,
            "forecasts": forecasts[offset: offset + limit],
        }

    @staticmethod
    def get_overview(db: Session, hours: int = 24, horizon_minutes: int = 60) -> Dict[str, Any]:
        anom_res = PredictiveAnalyticsService.list_anomalies(db, hours=hours, limit=200, offset=0)
        fc_res = PredictiveAnalyticsService.get_capacity_forecasts(db, hours=hours, horizon_minutes=horizon_minutes, limit=200, offset=0)
        telem_count = db.query(DeviceTelemetry).filter(
            DeviceTelemetry.timestamp >= PredictiveAnalyticsService._cutoff(hours)
        ).count()
        latest = db.query(DeviceTelemetry).order_by(DeviceTelemetry.timestamp.desc()).first()

        return {
            "data_source": "SIMULATION",
            "analysis_period_hours": hours,
            "forecast_horizon_minutes": horizon_minutes,
            "sample_count": telem_count,
            "last_sample_timestamp": latest.timestamp.isoformat() if latest else None,
            "classification": "INSUFFICIENT_DATA" if telem_count < 3 else "OBSERVED_AND_PREDICTED",
            "anomalies_detected": anom_res["total"],
            "predictive_warnings": fc_res["predictive_warnings_count"],
            "top_anomalies": anom_res["anomalies"][:5],
            "top_forecasts": fc_res["forecasts"][:8],
        }

    @staticmethod
    def get_historical_trends(
        db: Session,
        entity_type: str = "device",
        entity_id: Optional[str] = None,
        hours: int = 24,
        limit: int = 100,
    ) -> Dict[str, Any]:
        cutoff = PredictiveAnalyticsService._cutoff(hours)
        if entity_type == "interface" and entity_id:
            rows = (
                db.query(InterfaceTelemetry)
                .filter(InterfaceTelemetry.interface_id == entity_id, InterfaceTelemetry.timestamp >= cutoff)
                .order_by(InterfaceTelemetry.timestamp.asc())
                .limit(limit)
                .all()
            )
            points = [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "utilization_pct": r.utilization_pct,
                    "interface_errors": (r.input_errors or 0) + (r.output_errors or 0),
                    "interface_discards": (r.input_discards or 0) + (r.output_discards or 0),
                }
                for r in rows
            ]
        else:
            target_id = entity_id
            if not target_id:
                core = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()
                target_id = core.id if core else None
            rows = (
                db.query(DeviceTelemetry)
                .filter(DeviceTelemetry.device_id == target_id, DeviceTelemetry.timestamp >= cutoff)
                .order_by(DeviceTelemetry.timestamp.asc())
                .limit(limit)
                .all()
            ) if target_id else []
            points = [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "cpu_usage_pct": r.cpu_usage_pct,
                    "memory_usage_pct": r.memory_usage_pct,
                    "latency_ms": r.latency_ms,
                    "packet_loss_pct": r.packet_loss_pct,
                }
                for r in rows
            ]

        return {
            "data_source": "SIMULATION",
            "classification": "INSUFFICIENT_DATA" if len(points) < 3 else "OBSERVED",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "analysis_period_hours": hours,
            "sample_count": len(points),
            "last_sample_timestamp": points[-1]["timestamp"] if points else None,
            "points": points,
        }
