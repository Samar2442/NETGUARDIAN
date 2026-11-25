from datetime import datetime, timedelta, timezone
from app.database.migrations import run_safe_migrations
from app.models import Device, DeviceTelemetry
from app.engines.digital_twin.digital_twin_engine import DigitalTwinEngine
from app.services.predictive_analytics import PredictiveAnalyticsService
from app.services.telemetry_normalizer import TelemetryNormalizer


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_freshness_classification_and_source_isolation(client, db):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    headers = {"Authorization": f"Bearer {viewer_tok}"}

    now = datetime.now(timezone.utc)
    assert TelemetryNormalizer.classify_freshness(None, "online") == "MISSING"
    assert TelemetryNormalizer.classify_freshness(now, "unknown") == "UNKNOWN"
    assert TelemetryNormalizer.classify_freshness(now, "offline") == "STALE"
    assert TelemetryNormalizer.classify_freshness(now - timedelta(seconds=5), "online", threshold_seconds=30) == "FRESH"
    assert TelemetryNormalizer.classify_freshness(now - timedelta(seconds=90), "online", threshold_seconds=30) == "STALE"

    # Create a LAB device and an offline LAB device with old telemetry
    lab_dev = Device(
        hostname="LAB-SRC-ISO-01",
        management_ip="10.210.1.10",
        device_type="router",
        environment="LAB",
        status="offline",
    )
    db.add(lab_dev)
    db.flush()
    # Add SIMULATION telemetry row -> must NOT leak into LAB analytics!
    for i in range(4):
        db.add(DeviceTelemetry(
            device_id=lab_dev.id,
            timestamp=now - timedelta(minutes=10 - i),
            cpu_usage_pct=20.0 + i,
            memory_usage_pct=30.0,
            telemetry_source="SIMULATION",
            collection_method="SIMULATION",
        ))
    db.commit()

    # Predictive analytics for LAB device must return INSUFFICIENT_DATA (no SIMULATION leakage)
    ana = PredictiveAnalyticsService.get_device_analytics(db, lab_dev.id, hours=24)
    assert ana["data_source"] == "LAB"
    assert ana["status"] == "INSUFFICIENT_DATA"
    assert ana["sample_count"] == 0

    # Telemetry API source=LAB must not fabricate 100% availability for offline device
    t_res = client.get("/api/v1/telemetry/devices?source=LAB", headers=headers)
    assert t_res.status_code == 200
    match = next(d for d in t_res.json() if d["hostname"] == "LAB-SRC-ISO-01")
    assert match["environment"] == "LAB"
    assert match["freshness_status"] in ("MISSING", "STALE")
    assert match["availability_pct"] == 0.0

    # Synthetic SIMULATION recovery must NOT verify physical/LAB recovery
    twin_state = DigitalTwinEngine.get_intelligence_state(db, target_name="LAB-SRC-ISO-01")
    assert twin_state["state_classification"] == "UNKNOWN"

    # Validation report never marks unconfigured/mocked integrations as VALIDATED
    vr = client.get("/api/v1/integrations/validation-report", headers=headers)
    assert vr.status_code == 200
    for integ in vr.json()["integrations"].values():
        assert integ["status"] != "VALIDATED"

    # Idempotent migration check
    run_safe_migrations(db.get_bind())
