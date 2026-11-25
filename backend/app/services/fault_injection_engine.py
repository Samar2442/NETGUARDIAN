import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    AuditLog,
    Device,
    Event,
    FaultScenario,
    Incident,
    NetworkInterface,
    NetworkLink,
)
from app.services.telemetry_engine import TelemetryEngine
from app.engines.blast_radius.blast_radius_engine import BlastRadiusEngine

SUPPORTED_FAULT_TYPES = {
    "INTERFACE_DOWN",
    "HIGH_CPU",
    "MEMORY_PRESSURE",
    "CONGESTION",
    "PACKET_LOSS",
    "DEVICE_OFFLINE",
    "LINK_FAILURE",
}


class FaultInjectionError(ValueError):
    pass


class FaultInjectionEngine:
    """
    Controlled Network Fault Simulation Engine (SIMULATION ONLY).
    Never connects to or alters real network devices.
    """

    @staticmethod
    def inject_fault(
        db: Session,
        scenario_type: str,
        target_device_id: str,
        created_by: str,
        scenario_name: Optional[str] = None,
        target_interface_id: Optional[str] = None,
        target_link_id: Optional[str] = None,
        severity: str = "HIGH",
        max_duration_seconds: int = 1800,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        stype = (scenario_type or "").strip().upper()
        if stype not in SUPPORTED_FAULT_TYPES:
            raise FaultInjectionError(
                f"Unsupported fault type '{scenario_type}'. Supported: {sorted(SUPPORTED_FAULT_TYPES)}"
            )

        if max_duration_seconds < 1 or max_duration_seconds > settings.TELEMETRY_MAX_FAULT_DURATION_SECONDS:
            raise FaultInjectionError(
                f"max_duration_seconds must be between 1 and {settings.TELEMETRY_MAX_FAULT_DURATION_SECONDS}"
            )

        active_count = db.query(FaultScenario).filter(FaultScenario.status == "ACTIVE").count()
        if active_count >= settings.TELEMETRY_MAX_ACTIVE_FAULTS:
            raise FaultInjectionError(
                f"Maximum active fault limit ({settings.TELEMETRY_MAX_ACTIVE_FAULTS}) reached."
            )

        device = db.query(Device).filter(
            (Device.id == target_device_id) | (Device.hostname == target_device_id)
        ).first()
        if not device:
            raise FaultInjectionError(f"Target device '{target_device_id}' not found.")

        iface = None
        if stype == "INTERFACE_DOWN" or target_interface_id:
            if not target_interface_id:
                iface = db.query(NetworkInterface).filter(NetworkInterface.device_id == device.id).first()
            else:
                iface = db.query(NetworkInterface).filter(
                    (NetworkInterface.id == target_interface_id) | (NetworkInterface.name == target_interface_id),
                    NetworkInterface.device_id == device.id,
                ).first()
            if not iface and stype == "INTERFACE_DOWN":
                raise FaultInjectionError(f"Target interface not found on device '{device.hostname}'.")

        link = None
        if stype == "LINK_FAILURE":
            if target_link_id:
                link = db.query(NetworkLink).filter(NetworkLink.id == target_link_id).first()
            else:
                link = db.query(NetworkLink).filter(
                    (NetworkLink.source_device_id == device.id) | (NetworkLink.target_device_id == device.id)
                ).first()
            if not link:
                raise FaultInjectionError(f"Target network link not found for device '{device.hostname}'.")

        # Prevent duplicate active fault on the exact same target
        dup = db.query(FaultScenario).filter(
            FaultScenario.status == "ACTIVE",
            FaultScenario.scenario_type == stype,
            FaultScenario.target_device_id == device.id,
            FaultScenario.target_interface_id == (iface.id if iface else None),
            FaultScenario.target_link_id == (link.id if link else None),
        ).first()
        if dup:
            raise FaultInjectionError(
                f"An active '{stype}' fault is already running on '{device.hostname}'."
            )

        now = datetime.now(timezone.utc)
        run_id = f"FAULT-{uuid.uuid4().hex[:8]}"
        fault = FaultScenario(
            scenario_name=scenario_name or f"{stype} on {device.hostname}",
            scenario_type=stype,
            target_device_id=device.id,
            target_interface_id=iface.id if iface else None,
            target_link_id=link.id if link else None,
            severity=severity.upper(),
            parameters=parameters or {},
            status="ACTIVE",
            started_at=now,
            max_duration_seconds=max_duration_seconds,
            created_by=created_by,
            simulation_run_id=run_id,
            telemetry_source="SIMULATION",
        )
        db.add(fault)
        db.flush()

        # Emit link failure event explicitly if LINK_FAILURE
        if stype == "LINK_FAILURE" and link:
            TelemetryEngine._emit_deduplicated_event(
                db, now, "LINK_FAILURE", "%LINK-2-FAILURE", "CRITICAL", device,
                f"%LINK-2-FAILURE: Simulated link failure on '{link.name}' [SIMULATION].",
                dedup_window_seconds=5,
            )

        db.add(AuditLog(
            username=created_by,
            action="FAULT_SIMULATION_STARTED",
            resource_type="SIMULATION",
            resource_id=fault.id,
            details={
                "scenario_type": stype,
                "device": device.hostname,
                "interface": iface.name if iface else None,
                "link": link.name if link else None,
                "telemetry_source": "SIMULATION",
            },
            status="SUCCESS",
        ))
        db.commit()
        db.refresh(fault)

        # Immediately collect telemetry so fault effects & incidents appear at once
        telemetry_res = TelemetryEngine.collect_once(db, simulation_run_id=run_id)
        blast = BlastRadiusEngine.calculate_blast_radius(db, "device", device.hostname)

        return {
            "fault": fault,
            "telemetry": telemetry_res,
            "blast_radius": blast,
            "simulation_notice": "SIMULATION MODE — NO REAL NETWORK DEVICE IS MODIFIED",
        }

    @staticmethod
    def recover_fault(db: Session, fault_id: str, recovered_by: str) -> Dict[str, Any]:
        fault = db.query(FaultScenario).filter(FaultScenario.id == fault_id).first()
        if not fault:
            raise FaultInjectionError("Fault scenario not found.")
        if fault.status == "RECOVERED":
            raise FaultInjectionError("Fault scenario is already recovered.")

        now = datetime.now(timezone.utc)
        fault.status = "RECOVERED"
        fault.ended_at = now
        db.merge(fault)

        device = db.query(Device).filter(Device.id == fault.target_device_id).first()
        if device:
            device.status = "online"
            device.cpu_percent = 18.0
            device.memory_percent = 38.0
            db.merge(device)

            # Emit recovery event
            ev = Event(
                timestamp=now,
                source_type="device",
                source_id=str(device.id),
                source_name=device.hostname,
                event_type="FAULT_RECOVERED",
                event_code="%SYS-5-RECOVERED",
                severity="INFO",
                message=f"%SYS-5-RECOVERED: Simulated fault {fault.scenario_type} cleared on {device.hostname} [SIMULATION].",
                device_id=device.id,
                vlan_id=device.vlan_id,
                details={"fault_id": fault.id, "source": "SIMULATION"},
                acknowledged=False,
                resolved=True,
            )
            db.add(ev)

        if fault.target_link_id:
            link = db.query(NetworkLink).filter(NetworkLink.id == fault.target_link_id).first()
            if link:
                link.status = "up"
                db.merge(link)

        db.add(AuditLog(
            username=recovered_by,
            action="FAULT_SIMULATION_RECOVERED",
            resource_type="SIMULATION",
            resource_id=fault.id,
            details={"scenario_type": fault.scenario_type, "device": device.hostname if device else None},
            status="SUCCESS",
        ))
        db.commit()

        # Run verification collection cycle
        telemetry_res = TelemetryEngine.collect_once(db)

        # Resolve open incidents associated with this device only after recovery confirmation
        if device and device.status == "online":
            open_incs = db.query(Incident).filter(
                Incident.source_device_id == device.id,
                Incident.status.in_(["DETECTED", "INVESTIGATING", "ROOT_CAUSE_IDENTIFIED"]),
            ).all()
            for inc in open_incs:
                inc.status = "RESOLVED"
                inc.resolved_at = now
                db.merge(inc)
            db.query(Event).filter(
                Event.device_id == device.id,
                Event.resolved == False,
            ).update({Event.resolved: True})
            db.commit()

        return {
            "status": "RECOVERED",
            "fault_id": fault.id,
            "telemetry": telemetry_res,
            "simulation_notice": "SIMULATION MODE — NO REAL NETWORK DEVICE IS MODIFIED",
        }
