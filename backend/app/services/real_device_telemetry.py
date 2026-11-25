from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from app.models import CredentialVault, DeviceConnectionProfile
from app.services.snmpv3_collector import SNMPv3Collector
from app.services.telemetry_normalizer import TelemetryNormalizer


class RealDeviceTelemetryService:
    """
    Polls approved LAB/PRODUCTION devices via SNMPv3 or SSH without competing
    with TelemetryScheduler (called inside TelemetryScheduler's background cycle).
    """

    @staticmethod
    def poll_profile(db: Session, profile: DeviceConnectionProfile) -> Dict[str, Any]:
        cred = db.query(CredentialVault).filter(
            CredentialVault.credential_ref == profile.credential_ref
        ).first()
        if not cred:
            profile.connection_status = "ERROR"
            profile.last_connection_error = "Missing credential reference."
            db.commit()
            return {"success": False, "device_name": profile.device_name, "error": profile.last_connection_error}

        try:
            collected = SNMPv3Collector.collect_device_metrics(profile, cred)
            cpu = collected["metrics"].get("cpu_utilization")
            mem = collected["metrics"].get("memory_utilization")
            quality = "PARTIAL" if collected["unsupported_oids"] else "VALID"
            norm = TelemetryNormalizer.record_device_metrics(
                db=db,
                device_id=profile.device_id,
                device_name=profile.device_name,
                telemetry_source=profile.environment,
                collection_method="SNMPV3",
                cpu_pct=cpu,
                mem_pct=mem,
                data_quality=quality,
            )
            if profile.device_id:
                for iface in collected.get("interfaces", []):
                    TelemetryNormalizer.record_interface_metrics(
                        db=db,
                        device_id=profile.device_id,
                        iface_name=iface.get("name", ""),
                        telemetry_source=profile.environment,
                        collection_method="SNMPV3",
                        oper_status=iface.get("oper_status", "up"),
                        utilization_pct=float(iface.get("utilization_pct", 0.0)),
                        input_errors=int(iface.get("input_errors", 0)),
                        output_errors=int(iface.get("output_errors", 0)),
                    )
            profile.connection_status = "CONNECTED"
            profile.last_successful_connection = datetime.now(timezone.utc)
            profile.last_connection_error = None
            db.commit()
            return {**norm, "unsupported_oids": collected["unsupported_oids"]}
        except Exception as exc:
            profile.connection_status = "ERROR"
            profile.last_connection_error = str(exc)[:240]
            db.commit()
            return {
                "success": False,
                "device_name": profile.device_name,
                "telemetry_source": profile.environment,
                "error": profile.last_connection_error,
            }

    @staticmethod
    def poll_all_approved(db: Session) -> Dict[str, Any]:
        profiles = db.query(DeviceConnectionProfile).filter(
            DeviceConnectionProfile.is_approved == True,
            DeviceConnectionProfile.environment.in_(["LAB", "PRODUCTION"]),
            DeviceConnectionProfile.protocol == "SNMPV3",
        ).all()
        results = [RealDeviceTelemetryService.poll_profile(db, p) for p in profiles]
        return {
            "polled_count": len(results),
            "success_count": sum(1 for r in results if r.get("success")),
            "results": results,
        }

    @staticmethod
    def get_polling_health(db: Session) -> Dict[str, Any]:
        profiles = db.query(DeviceConnectionProfile).all()
        stale = TelemetryNormalizer.detect_stale_telemetry(db)
        return {
            "total_profiles": len(profiles),
            "connected": sum(1 for p in profiles if p.connection_status == "CONNECTED"),
            "error": sum(1 for p in profiles if p.connection_status == "ERROR"),
            "disconnected": sum(1 for p in profiles if p.connection_status == "DISCONNECTED"),
            "stale_devices": stale,
        }
