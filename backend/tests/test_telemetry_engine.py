import asyncio
from datetime import datetime, timedelta, timezone
from app.models import AuditLog, Device, DeviceTelemetry, InterfaceTelemetry
from app.services.telemetry_engine import DEVICE_BASELINES, TelemetryEngine
from app.services.telemetry_scheduler import TelemetryScheduler


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_metrics_generated_within_baseline_bounds(db):
    res = TelemetryEngine.collect_once(db, seed=42)
    assert res["status"] == "COLLECTED"
    assert res["telemetry_source"] == "SIMULATION"
    assert res["devices_polled"] >= 274

    rows = db.query(DeviceTelemetry).filter(DeviceTelemetry.simulation_run_id == res["simulation_run_id"]).all()
    assert len(rows) == res["devices_polled"]
    for r in rows:
        assert 0.0 <= r.cpu_usage_pct <= 100.0
        assert 0.0 <= r.memory_usage_pct <= 100.0
        assert 0.0 <= r.availability_pct <= 100.0
        assert r.telemetry_source == "SIMULATION"


def test_time_series_continuity_and_reproducible_seed(db):
    r1 = TelemetryEngine.collect_once(db, seed=1234, simulation_run_id="SEED-RUN-1")
    r2 = TelemetryEngine.collect_once(db, seed=1234, simulation_run_id="SEED-RUN-2")
    assert r1["devices_polled"] == r2["devices_polled"]

    core = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()
    pts = db.query(DeviceTelemetry).filter(DeviceTelemetry.device_id == core.id).order_by(DeviceTelemetry.timestamp.asc()).all()
    assert len(pts) >= 2
    # Continuity: normal CPU step shouldn't jump by > 15% in a single cycle
    assert abs(pts[-1].cpu_usage_pct - pts[-2].cpu_usage_pct) < 15.0


def test_interface_traffic_calculations_and_retention(db):
    TelemetryEngine.collect_once(db, seed=7)
    ifaces = db.query(InterfaceTelemetry).limit(10).all()
    assert len(ifaces) > 0
    for it in ifaces:
        assert it.inbound_bps >= 0.0
        assert it.outbound_bps >= 0.0
        assert it.telemetry_source == "SIMULATION"

    # Retention policy never deletes AuditLog
    audit_before = db.query(AuditLog).count()
    old_row = DeviceTelemetry(
        device_id=ifaces[0].device_id,
        timestamp=datetime.now(timezone.utc) - timedelta(hours=30),
        cpu_usage_pct=15.0,
        memory_usage_pct=30.0,
    )
    db.add(old_row)
    db.commit()
    pruned = TelemetryEngine.prune_old_telemetry(db, retention_hours=24)
    assert pruned["deleted_device_telemetry"] >= 1
    assert db.query(AuditLog).count() == audit_before


def test_scheduler_lifecycle_prevents_duplicate_instances():
    async def _run():
        sched = TelemetryScheduler()
        assert sched.start() is True
        assert sched.is_running is True
        # Second start must return False (duplicate prevention)
        assert sched.start() is False
        await sched.stop()
        assert sched.is_running is False

    asyncio.run(_run())


def test_telemetry_api_rbac_and_vlan_health(client):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")

    assert client.get("/api/v1/telemetry/overview").status_code == 401
    assert client.post("/api/v1/telemetry/collect", headers={"Authorization": f"Bearer {viewer_tok}"}).status_code == 403
    assert client.post("/api/v1/telemetry/collect", headers={"Authorization": f"Bearer {eng_tok}"}).status_code == 200

    res_vlans = client.get("/api/v1/telemetry/vlans", headers={"Authorization": f"Bearer {viewer_tok}"})
    assert res_vlans.status_code == 200
    vlan_map = {v["vlan_id"]: v for v in res_vlans.json()}
    assert vlan_map[10]["total_endpoints"] == 80
    assert vlan_map[20]["total_endpoints"] == 100
    assert vlan_map[30]["total_endpoints"] == 70
