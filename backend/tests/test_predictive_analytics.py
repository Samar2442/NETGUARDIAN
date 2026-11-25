from datetime import datetime, timedelta, timezone
from app.models import Device, DeviceTelemetry, InterfaceTelemetry, NetworkInterface
from app.services.predictive_analytics import PredictiveAnalyticsService


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_insufficient_data_state_when_telemetry_missing(db):
    dev = db.query(Device).filter(Device.hostname == "SRV-NMS-01").first()
    db.query(DeviceTelemetry).filter(DeviceTelemetry.device_id == dev.id).delete()
    db.commit()

    res = PredictiveAnalyticsService.get_device_analytics(db, dev.id, hours=24)
    assert res is not None
    assert res["status"] == "INSUFFICIENT_DATA"
    assert res["classification"] == "INSUFFICIENT_DATA"
    assert res["sample_count"] == 0
    assert res["data_source"] == "SIMULATION"


def test_anomaly_detection_and_capacity_forecasting(client, db):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    headers = {"Authorization": f"Bearer {viewer_tok}"}

    dev = db.query(Device).filter(Device.hostname == "SW-IT-02").first()
    iface = db.query(NetworkInterface).filter(NetworkInterface.device_id == dev.id).first()
    db.query(DeviceTelemetry).filter(DeviceTelemetry.device_id == dev.id).delete()
    db.query(InterfaceTelemetry).filter(InterfaceTelemetry.interface_id == iface.id).delete()

    now = datetime.now(timezone.utc)
    # 6 rising CPU samples ending in a spike -> triggers CPU_ANOMALY & predictive warning
    cpu_series = [30.0, 38.0, 46.0, 54.0, 62.0, 88.0]
    for idx, val in enumerate(cpu_series):
        ts = now - timedelta(minutes=(5 - idx) * 10)
        db.add(DeviceTelemetry(
            device_id=dev.id,
            cpu_usage_pct=val,
            memory_usage_pct=45.0 + idx * 2.0,
            availability_pct=100.0,
            latency_ms=2.0,
            packet_loss_pct=0.0 if idx < 5 else 4.5,
            timestamp=ts,
        ))
        db.add(InterfaceTelemetry(
            interface_id=iface.id,
            device_id=dev.id,
            inbound_bps=(200.0 + idx * 80.0) * 1_000_000,
            outbound_bps=(180.0 + idx * 70.0) * 1_000_000,
            utilization_pct=25.0 + idx * 12.0,
            input_errors=0 if idx < 5 else 12,
            output_errors=0,
            input_discards=0,
            output_discards=0,
            operational_status="up",
            timestamp=ts,
        ))
    db.commit()

    dev_res = client.get(f"/api/v1/analytics/devices/{dev.id}?hours=24&horizon_minutes=60", headers=headers)
    assert dev_res.status_code == 200
    d_body = dev_res.json()
    assert d_body["data_source"] == "SIMULATION"
    assert d_body["sample_count"] == 6
    assert d_body["last_sample_timestamp"] is not None
    assert any(a["anomaly_type"] == "CPU_ANOMALY" and a["is_confirmed_incident"] is False for a in d_body["anomalies"])
    cpu_fc = next(f for f in d_body["forecasts"] if f["metric_name"] == "cpu_usage_pct")
    assert cpu_fc["classification"] == "PREDICTED"
    assert cpu_fc["predictive_warning"] is True
    assert cpu_fc["slope_per_hour"] > 0

    iface_res = client.get(f"/api/v1/analytics/interfaces/{iface.id}?hours=24", headers=headers)
    assert iface_res.status_code == 200
    i_body = iface_res.json()
    assert any(a["anomaly_type"] in ("BANDWIDTH_ANOMALY", "INTERFACE_ERROR_ANOMALY") for a in i_body["anomalies"])

    # Overview, anomalies, capacity-forecast, trends, vlan, RBAC, and bounded validation
    assert client.get("/api/v1/analytics/overview").status_code == 401
    assert client.get("/api/v1/analytics/overview", headers=headers).status_code == 200
    assert client.get("/api/v1/analytics/anomalies?limit=20", headers=headers).status_code == 200
    assert client.get("/api/v1/analytics/capacity-forecast?horizon_minutes=120", headers=headers).status_code == 200
    assert client.get(f"/api/v1/analytics/trends?entity_type=device&entity_id={dev.id}", headers=headers).status_code == 200
    assert client.get("/api/v1/analytics/vlans/10", headers=headers).status_code == 200
    assert client.get("/api/v1/analytics/overview?hours=999", headers=headers).status_code == 422

    # Clean up test telemetry
    db.query(DeviceTelemetry).filter(DeviceTelemetry.device_id == dev.id).delete()
    db.query(InterfaceTelemetry).filter(InterfaceTelemetry.interface_id == iface.id).delete()
    db.commit()
