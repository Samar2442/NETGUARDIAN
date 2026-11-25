from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from app.models import Device, DeviceTelemetry
from app.services.snmpv3_collector import SNMPAuthError, SNMPv3Collector
from app.services.telemetry_normalizer import TelemetryNormalizer


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_snmpv3_polling_normalization_and_failures(client, db):
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")

    a_h = {"Authorization": f"Bearer {admin_tok}"}
    e_h = {"Authorization": f"Bearer {eng_tok}"}
    v_h = {"Authorization": f"Bearer {viewer_tok}"}

    cred_ref = client.post(
        "/api/v1/integrations/credentials",
        json={
            "name": "lab-snmpv3",
            "username": "snmpuser",
            "password": "AuthSecretKey99!",
            "secret": "PrivSecretKey88!",
            "auth_protocol": "SHA",
            "priv_protocol": "AES128",
        },
        headers=a_h,
    ).json()["credential_ref"]

    sw = db.query(Device).filter(Device.hostname == "SW-IT-01").first()
    prof = client.post(
        "/api/v1/integrations/profiles",
        json={
            "device_name": "SW-IT-01",
            "management_ip": "10.200.2.10",
            "protocol": "SNMPV3",
            "port": 161,
            "credential_ref": cred_ref,
            "environment": "LAB",
        },
        headers=a_h,
    ).json()
    prof_id = prof["id"]

    # Mock SNMPv3 collection with unsupported memory OID -> PARTIAL quality, LAB source
    with patch.object(SNMPv3Collector, "_snmp_get", return_value={
        "sysUpTime": 123456,
        "cpu_utilization": 42.5,
        "memory_used": "NO_SUCH_OBJECT",
        "interfaces": [{"name": "GigabitEthernet0/1", "oper_status": "up", "utilization_pct": 18.0, "input_errors": 0, "output_errors": 0}],
    }):
        res = client.post(f"/api/v1/integrations/telemetry/poll/{prof_id}", headers=e_h)
        assert res.status_code == 200
        body = res.json()
        assert body["telemetry_source"] == "LAB"
        assert body["collection_method"] == "SNMPV3"
        assert body["data_quality"] == "PARTIAL"
        assert "memory_used" in body["unsupported_oids"]
        assert "AuthSecretKey99!" not in str(body)

    # SNMPv3 Auth error -> handled gracefully & secret redacted
    with patch.object(SNMPv3Collector, "_snmp_get", side_effect=SNMPAuthError("Bad USM auth AuthSecretKey99!")):
        err_res = client.post(f"/api/v1/integrations/telemetry/poll/{prof_id}", headers=e_h)
        assert err_res.status_code == 200
        assert err_res.json()["success"] is False

    # Health & stale detection
    assert client.get("/api/v1/integrations/telemetry/health", headers=v_h).status_code == 200
    old_ts = datetime.now(timezone.utc) - timedelta(minutes=15)
    lab_dev = Device(
        hostname="LAB-STALE-SW",
        device_type="l2_switch",
        management_ip="10.200.2.99",
        environment="LAB",
        status="online",
    )
    db.add(lab_dev)
    db.flush()
    db.add(DeviceTelemetry(device_id=lab_dev.id, timestamp=old_ts, cpu_usage_pct=10.0, memory_usage_pct=20.0, telemetry_source="LAB"))
    db.commit()
    stale = TelemetryNormalizer.detect_stale_telemetry(db, max_age_seconds=120)
    assert any(s["hostname"] == "LAB-STALE-SW" for s in stale)


def test_syslog_parsing_validation_untrusted_and_deduplication(client, db):
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    e_h = {"Authorization": f"Bearer {eng_tok}"}

    # Malformed message -> 400
    assert client.post(
        "/api/v1/integrations/syslog/ingest",
        json={"raw_message": "random non-cisco garbage"},
        headers=e_h,
    ).status_code == 400

    # Untrusted source -> 403
    assert client.post(
        "/api/v1/integrations/syslog/ingest",
        json={"raw_message": "<187>Nov 25 09:00:00 UNKNOWN-HOST: %LINK-3-UPDOWN: Interface Gi0/1 down", "source_ip": "192.168.99.99"},
        headers=e_h,
    ).status_code == 403

    # Valid message from registered device -> INGESTED then DEDUPLICATED
    msg = "<187>Nov 25 09:00:00 SW-CSE-01: %LINK-3-UPDOWN: Interface GigabitEthernet0/1 changed state to down"
    r1 = client.post("/api/v1/integrations/syslog/ingest", json={"raw_message": msg}, headers=e_h)
    assert r1.status_code == 200
    assert r1.json()["status"] == "INGESTED"

    r2 = client.post("/api/v1/integrations/syslog/ingest", json={"raw_message": msg}, headers=e_h)
    assert r2.status_code == 200
    assert r2.json()["status"] == "DEDUPLICATED"
