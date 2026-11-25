import math
import random
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import networkx as nx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Device,
    DeviceTelemetry,
    Event,
    FaultScenario,
    HealthMetric,
    Incident,
    InterfaceTelemetry,
    NetworkInterface,
    NetworkLink,
    VLAN,
)
from app.engines.correlation.correlation_engine import CorrelationEngine
from app.engines.diagnosis.rca_engine import RootCauseAnalysisEngine

# Baseline simulation profiles by device_type: (cpu_min, cpu_max, mem_min, mem_max, util_min, util_max)
DEVICE_BASELINES: Dict[str, Tuple[float, float, float, float, float, float]] = {
    "l3_switch": (10.0, 35.0, 30.0, 65.0, 15.0, 60.0),
    "l2_switch": (10.0, 35.0, 30.0, 65.0, 10.0, 55.0),
    "access_switch": (5.0, 30.0, 25.0, 60.0, 5.0, 45.0),
    "router": (10.0, 40.0, 30.0, 70.0, 10.0, 65.0),
    "firewall": (10.0, 45.0, 35.0, 75.0, 10.0, 70.0),
    "server": (15.0, 55.0, 35.0, 80.0, 5.0, 75.0),
    "wireless_ap": (5.0, 30.0, 25.0, 60.0, 5.0, 50.0),
    "endpoint": (2.0, 35.0, 20.0, 75.0, 1.0, 40.0),
}

_COLLECT_LOCK = threading.Lock()


class TelemetryEngine:
    """
    Realistic Time-Varying Campus Telemetry Simulation Engine.
    - Generates continuous, bounded, device-profiled metrics (SIMULATION ONLY).
    - Evaluates active FaultScenario records and redundant paths.
    - Emits deduplicated Cisco-style syslog events and correlates incidents.
    - Enforces high-resolution telemetry retention without touching AuditLog.
    """

    @staticmethod
    def _smooth_step(current: float, low: float, high: float, max_delta: float, rng: random.Random) -> float:
        mid = (low + high) / 2.0
        # Gentle mean-reversion + bounded random walk
        pull = (mid - current) * 0.12
        nxt = current + pull + rng.uniform(-max_delta, max_delta)
        return round(max(low, min(high, nxt)), 2)

    @staticmethod
    def _emit_deduplicated_event(
        db: Session,
        now: datetime,
        event_type: str,
        event_code: str,
        severity: str,
        device: Device,
        message: str,
        interface: Optional[NetworkInterface] = None,
        vlan_id: Optional[int] = None,
        correlation_id: Optional[str] = None,
        dedup_window_seconds: int = 60,
    ) -> Optional[Event]:
        cutoff = now - timedelta(seconds=dedup_window_seconds)
        existing = (
            db.query(Event)
            .filter(
                Event.event_type == event_type,
                Event.source_id == str(device.id),
                Event.timestamp >= cutoff,
                Event.resolved == False,
            )
            .first()
        )
        if existing:
            return None

        ev = Event(
            timestamp=now,
            source_type="interface" if interface else "device",
            source_id=str(device.id),
            source_name=device.hostname,
            event_type=event_type,
            event_code=event_code,
            severity=severity,
            message=message,
            device_id=device.id,
            interface_id=interface.id if interface else None,
            vlan_id=vlan_id or device.vlan_id,
            correlation_id=correlation_id or f"CORR-{device.hostname}-{event_type}",
            details={
                "source": "SIMULATION",
                "device_name": device.hostname,
                "department": device.department,
                "vlan_id": vlan_id or device.vlan_id,
                "interface": interface.name if interface else None,
            },
            acknowledged=False,
            resolved=False,
        )
        db.add(ev)
        db.flush()

        # Correlate non-info alerts into incidents
        if severity.upper() in {"WARNING", "MINOR", "MAJOR", "CRITICAL", "HIGH", "MEDIUM"}:
            inc = CorrelationEngine.correlate_event(db, ev)
            if inc and not inc.diagnosis:
                try:
                    RootCauseAnalysisEngine.diagnose_incident(db, inc)
                except Exception:
                    pass
        return ev

    @staticmethod
    def _compute_reachable_devices(devices: List[Device], links: List[NetworkLink], offline_ids: set[str], down_link_ids: set[str]) -> set[str]:
        core = next((d for d in devices if d.hostname == "SW-CORE-01"), None)
        if not core or core.id in offline_ids:
            return set()
        G = nx.Graph()
        for d in devices:
            if d.id not in offline_ids:
                G.add_node(d.id)
        for l in links:
            if l.id in down_link_ids:
                continue
            if l.source_device_id not in offline_ids and l.target_device_id not in offline_ids:
                G.add_edge(l.source_device_id, l.target_device_id)
        if core.id not in G:
            return set()
        return set(nx.node_connected_component(G, core.id))

    @staticmethod
    def collect_once(
        db: Session,
        seed: Optional[int] = None,
        simulation_run_id: Optional[str] = None,
        interval_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute one telemetry simulation cycle across all campus devices and interfaces."""
        if not _COLLECT_LOCK.acquire(blocking=False):
            return {"status": "SKIPPED_CONCURRENT_COLLECTION", "devices_polled": 0}

        try:
            rng = random.Random(seed) if seed is not None else random.Random()
            now = datetime.now(timezone.utc)
            run_id = simulation_run_id or f"SIM-{uuid.uuid4().hex[:10]}"
            step_sec = interval_seconds or settings.TELEMETRY_POLLING_INTERVAL_SECONDS

            devices = db.query(Device).all()
            interfaces = db.query(NetworkInterface).all()
            links = db.query(NetworkLink).all()
            active_faults = db.query(FaultScenario).filter(FaultScenario.status == "ACTIVE").all()

            # Auto-recover expired faults if max_duration_seconds exceeded
            for f in list(active_faults):
                started = f.started_at
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                if (now - started).total_seconds() > f.max_duration_seconds:
                    f.status = "RECOVERED"
                    f.ended_at = now
                    active_faults.remove(f)

            faults_by_device: Dict[str, List[FaultScenario]] = {}
            faults_by_iface: Dict[str, List[FaultScenario]] = {}
            down_link_ids: set[str] = set()
            offline_device_ids: set[str] = set()

            for f in active_faults:
                faults_by_device.setdefault(f.target_device_id, []).append(f)
                if f.target_interface_id:
                    faults_by_iface.setdefault(f.target_interface_id, []).append(f)
                if f.scenario_type == "DEVICE_OFFLINE":
                    offline_device_ids.add(f.target_device_id)
                if f.scenario_type == "LINK_FAILURE" and f.target_link_id:
                    down_link_ids.add(f.target_link_id)

            reachable_ids = TelemetryEngine._compute_reachable_devices(
                devices, links, offline_device_ids, down_link_ids
            )

            # Diurnal traffic wave (smooth sine wave over hour/minute)
            diurnal = 1.0 + 0.15 * math.sin((now.hour * 60 + now.minute) / 1440.0 * 2 * math.pi)

            dev_telemetry_rows: List[DeviceTelemetry] = []
            iface_telemetry_rows: List[InterfaceTelemetry] = []
            events_generated = 0

            ifaces_by_dev: Dict[str, List[NetworkInterface]] = {}
            for iface in interfaces:
                ifaces_by_dev.setdefault(iface.device_id, []).append(iface)

            total_cpu = 0.0
            total_latency = 0.0
            total_loss = 0.0
            online_cnt = 0
            offline_cnt = 0
            degraded_cnt = 0

            for dev in devices:
                cpu_lo, cpu_hi, mem_lo, mem_hi, util_lo, util_hi = DEVICE_BASELINES.get(
                    dev.device_type, (5.0, 35.0, 20.0, 70.0, 5.0, 45.0)
                )
                dev_faults = faults_by_device.get(dev.id, [])
                fault_types = {f.scenario_type for f in dev_faults}

                is_offline = "DEVICE_OFFLINE" in fault_types or (
                    dev.id not in reachable_ids and dev.hostname != "SW-CORE-01" and len(links) > 0
                )

                if is_offline:
                    cpu = 0.0
                    mem = 0.0
                    temp = 24.0
                    avail = 0.0
                    latency = 0.0
                    loss = 100.0
                    status = "offline"
                    offline_cnt += 1
                    if "DEVICE_OFFLINE" in fault_types:
                        if TelemetryEngine._emit_deduplicated_event(
                            db, now, "DEVICE_UNREACHABLE", "%DEV-1-UNREACHABLE", "CRITICAL", dev,
                            f"%DEV-1-UNREACHABLE: Device {dev.hostname} ({dev.management_ip}) is unreachable [SIMULATION]."
                        ):
                            events_generated += 1
                else:
                    base_cpu = dev.cpu_percent if dev.cpu_percent is not None else (cpu_lo + cpu_hi) / 2
                    base_mem = dev.memory_percent if dev.memory_percent is not None else (mem_lo + mem_hi) / 2

                    if "HIGH_CPU" in fault_types:
                        cpu = round(rng.uniform(91.5, 98.5), 2)
                        temp = round(rng.uniform(76.0, 84.0), 1)
                    else:
                        cpu = TelemetryEngine._smooth_step(base_cpu, cpu_lo, cpu_hi, 2.2, rng)
                        temp = round(34.0 + (cpu * 0.35) + rng.uniform(-0.8, 0.8), 1)

                    if "MEMORY_PRESSURE" in fault_types:
                        mem = round(rng.uniform(91.0, 97.5), 2)
                    else:
                        mem = TelemetryEngine._smooth_step(base_mem, mem_lo, mem_hi, 1.2, rng)

                    if "PACKET_LOSS" in fault_types:
                        loss = round(rng.uniform(5.5, 11.5), 2)
                        latency = round(rng.uniform(160.0, 290.0), 2)
                    elif "CONGESTION" in fault_types:
                        loss = round(rng.uniform(2.2, 4.8), 2)
                        latency = round(rng.uniform(115.0, 210.0), 2)
                    else:
                        loss = round(rng.uniform(0.0, 0.15), 2)
                        latency = round(rng.uniform(0.8, 4.5) * diurnal, 2)

                    avail = 100.0
                    if (
                        cpu >= settings.THRESHOLD_CPU_WARN
                        or mem >= settings.THRESHOLD_MEM_WARN
                        or loss >= settings.THRESHOLD_LOSS_WARN
                        or latency >= settings.THRESHOLD_LATENCY_WARN
                        or temp >= settings.THRESHOLD_TEMP_WARN
                    ):
                        status = "degraded"
                        degraded_cnt += 1
                    else:
                        status = "online"
                        online_cnt += 1

                    # Threshold Event Detection
                    if cpu >= settings.THRESHOLD_CPU_CRIT:
                        if TelemetryEngine._emit_deduplicated_event(
                            db, now, "HIGH_CPU", "%SYS-1-CPUHOG", "CRITICAL", dev,
                            f"%SYS-1-CPUHOG: High CPU utilization ({cpu}%) detected on {dev.hostname} [SIMULATION]."
                        ):
                            events_generated += 1
                    elif cpu >= settings.THRESHOLD_CPU_WARN:
                        if TelemetryEngine._emit_deduplicated_event(
                            db, now, "HIGH_CPU", "%SYS-2-CPUWARN", "WARNING", dev,
                            f"%SYS-2-CPUWARN: Elevated CPU utilization ({cpu}%) on {dev.hostname} [SIMULATION]."
                        ):
                            events_generated += 1

                    if mem >= settings.THRESHOLD_MEM_CRIT:
                        if TelemetryEngine._emit_deduplicated_event(
                            db, now, "MEMORY_PRESSURE", "%SYS-1-MEMCRIT", "CRITICAL", dev,
                            f"%SYS-1-MEMCRIT: Critical memory pressure ({mem}%) on {dev.hostname} [SIMULATION]."
                        ):
                            events_generated += 1

                    if loss >= settings.THRESHOLD_LOSS_CRIT:
                        if TelemetryEngine._emit_deduplicated_event(
                            db, now, "PACKET_LOSS", "%PKT-3-LOSS", "MAJOR", dev,
                            f"%PKT-3-LOSS: Packet loss {loss}% exceeds threshold on {dev.hostname} [SIMULATION]."
                        ):
                            events_generated += 1

                dev.cpu_percent = cpu
                dev.memory_percent = mem
                dev.status = status
                dev.last_seen = now
                if not is_offline:
                    dev.uptime_seconds = (dev.uptime_seconds or 0) + step_sec

                total_cpu += cpu
                total_latency += latency
                total_loss += loss

                dev_telemetry_rows.append(
                    DeviceTelemetry(
                        device_id=dev.id,
                        timestamp=now,
                        cpu_usage_pct=cpu,
                        memory_usage_pct=mem,
                        temperature_celsius=temp,
                        uptime_seconds=dev.uptime_seconds or 0,
                        availability_pct=avail,
                        latency_ms=latency,
                        packet_loss_pct=loss,
                        status=status,
                        telemetry_source="SIMULATION",
                        simulation_run_id=run_id,
                    )
                )

                # Interface telemetry for device
                for iface in ifaces_by_dev.get(dev.id, []):
                    if_faults = {f.scenario_type for f in faults_by_iface.get(iface.id, [])}
                    if is_offline or "INTERFACE_DOWN" in if_faults or iface.admin_status == "down":
                        op_stat = "down"
                        util = 0.0
                        in_bps = 0.0
                        out_bps = 0.0
                        in_err = iface.in_errors or 0
                        out_err = iface.out_errors or 0
                        in_disc = 0
                        out_disc = 0
                        if "INTERFACE_DOWN" in if_faults:
                            if TelemetryEngine._emit_deduplicated_event(
                                db, now, "INTERFACE_DOWN", "%LINK-3-UPDOWN", "CRITICAL", dev,
                                f"%LINK-3-UPDOWN: Interface {iface.name} on {dev.hostname}, changed state to down [SIMULATION].",
                                interface=iface,
                            ):
                                events_generated += 1
                    else:
                        op_stat = "up"
                        if "CONGESTION" in if_faults or "CONGESTION" in fault_types:
                            util = round(rng.uniform(90.5, 97.5), 2)
                            in_disc = rng.randint(5, 25)
                            out_disc = rng.randint(10, 40)
                            if TelemetryEngine._emit_deduplicated_event(
                                db, now, "HIGH_UTILIZATION", "%PORT-5-IF_UTIL", "MAJOR", dev,
                                f"%PORT-5-IF_UTIL: Interface {iface.name} utilization ({util}%) exceeded threshold [SIMULATION].",
                                interface=iface,
                            ):
                                events_generated += 1
                        else:
                            cur_u = iface.bandwidth_utilization_pct or ((util_lo + util_hi) / 2)
                            util = TelemetryEngine._smooth_step(cur_u, util_lo, util_hi * diurnal, 3.0, rng)
                            in_disc = 0
                            out_disc = 0

                        cap_bps = (iface.speed_mbps or 1000) * 1_000_000.0
                        in_bps = round(cap_bps * (util / 100.0), 2)
                        out_bps = round(in_bps * rng.uniform(0.75, 0.95), 2)
                        in_err = iface.in_errors or 0
                        out_err = iface.out_errors or 0
                        iface.in_octets = (iface.in_octets or 0) + int((in_bps / 8.0) * step_sec)
                        iface.out_octets = (iface.out_octets or 0) + int((out_bps / 8.0) * step_sec)

                    iface.oper_status = op_stat
                    iface.bandwidth_utilization_pct = util
                    iface.updated_at = now

                    iface_telemetry_rows.append(
                        InterfaceTelemetry(
                            interface_id=iface.id,
                            device_id=dev.id,
                            timestamp=now,
                            inbound_bps=in_bps,
                            outbound_bps=out_bps,
                            utilization_pct=util,
                            input_errors=in_err,
                            output_errors=out_err,
                            input_discards=in_disc,
                            output_discards=out_disc,
                            operational_status=op_stat,
                            duplex=iface.duplex or "full",
                            telemetry_source="SIMULATION",
                            simulation_run_id=run_id,
                        )
                    )

            # Update link statuses
            for l in links:
                if l.id in down_link_ids:
                    l.status = "down"
                    l.utilization_pct = 0.0
                elif l.source_device_id in offline_device_ids or l.target_device_id in offline_device_ids:
                    l.status = "down"
                    l.utilization_pct = 0.0
                else:
                    l.status = "up"
                    l.utilization_pct = round(rng.uniform(10.0, 35.0) * diurnal, 2)

            if dev_telemetry_rows:
                db.bulk_save_objects(dev_telemetry_rows)
            if iface_telemetry_rows:
                db.bulk_save_objects(iface_telemetry_rows)

            n_devs = max(1, len(devices))
            avail_pct = round(((online_cnt + degraded_cnt) / n_devs) * 100.0, 2)
            overall = round(max(0.0, min(100.0, avail_pct - (degraded_cnt * 2.5))), 2)
            db.add(HealthMetric(
                timestamp=now,
                overall_health=overall,
                availability=avail_pct,
                performance=round(max(0.0, 100.0 - (total_loss / n_devs) * 5.0), 2),
                configuration=96.0,
                security=95.0,
                redundancy=94.0 if not down_link_ids else 80.0,
                risk_score=round(100.0 - overall, 2),
                active_incidents=db.query(Incident).filter(Incident.status != "RESOLVED").count(),
                total_devices=len(devices),
                online_devices=online_cnt + degraded_cnt,
                avg_latency_ms=round(total_latency / n_devs, 2),
                avg_packet_loss_pct=round(total_loss / n_devs, 2),
            ))
            db.commit()

            return {
                "status": "COLLECTED",
                "telemetry_source": "SIMULATION",
                "simulation_run_id": run_id,
                "timestamp": now.isoformat(),
                "devices_polled": len(devices),
                "interfaces_polled": len(iface_telemetry_rows),
                "online_devices": online_cnt,
                "degraded_devices": degraded_cnt,
                "offline_devices": offline_cnt,
                "events_generated": events_generated,
            }
        finally:
            _COLLECT_LOCK.release()

    @staticmethod
    def prune_old_telemetry(db: Session, retention_hours: Optional[int] = None) -> Dict[str, int]:
        """
        Enforce telemetry retention policy (default 24 hours).
        Never deletes AuditLog or User records.
        """
        hours = retention_hours if retention_hours is not None else settings.TELEMETRY_RETENTION_HOURS
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        del_dev = db.query(DeviceTelemetry).filter(DeviceTelemetry.timestamp < cutoff).delete()
        del_iface = db.query(InterfaceTelemetry).filter(InterfaceTelemetry.timestamp < cutoff).delete()
        db.commit()
        return {"deleted_device_telemetry": del_dev, "deleted_interface_telemetry": del_iface}
