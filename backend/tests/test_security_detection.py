from app.models import SecurityDetection, Incident
from app.services.security_detection_engine import SecurityDetectionEngine


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_all_security_detection_rules_and_simulation_classification(client, db):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")

    rules_res = client.get("/api/v1/security/rules", headers={"Authorization": f"Bearer {viewer_tok}"})
    assert rules_res.status_code == 200
    assert len(rules_res.json()) == 10

    # RBAC: viewer cannot evaluate or update rule; engineer cannot update rule
    assert client.post(
        "/api/v1/security/detections/evaluate",
        json={"detection_type": "ROGUE_DHCP", "source_device_name": "SW-IT-01"},
        headers={"Authorization": f"Bearer {viewer_tok}"},
    ).status_code == 403
    assert client.patch(
        "/api/v1/security/rules/SEC-RULE-004",
        json={"threshold": 2},
        headers={"Authorization": f"Bearer {eng_tok}"},
    ).status_code == 403

    # Test key detection types & SIMULATION classification
    scenarios = [
        ("AUTH_FAILURE_BURST", "SRV-NMS-01", None, 10, 4, ["4 failed logins"]),
        ("UNAUTHORIZED_DEVICE", "SW-CSE-01", "AA:BB:CC:11:22:33", 10, 1, ["Unknown MAC on Gi0/5"]),
        ("ROGUE_DHCP", "SW-IT-01", "00:11:22:33:44:55", 20, 1, ["DHCP Offer from Gi0/8"]),
        ("ARP_ANOMALY", "SW-ECE-01", "10.0.30.99", 30, 2, ["Duplicate ARP for 10.0.30.1"]),
        ("PORT_SECURITY_VIOLATION", "SW-CSE-02", "DE:AD:BE:EF:00:01", 10, 1, ["Port-security max MAC exceeded"]),
        ("MAC_ADDRESS_CHANGE", "SW-IT-02", "00:50:56:AA:BB:CC", 20, 2, ["MAC flapping Gi0/2 <-> Gi0/4"]),
        ("UNEXPECTED_VLAN_CHANGE", "SW-ECE-02", None, 30, 1, ["Access port moved from VLAN 30 to VLAN 20"]),
    ]

    for dtype, dev, ep, vlan, count, ev in scenarios:
        res = client.post(
            "/api/v1/security/detections/evaluate",
            json={
                "detection_type": dtype,
                "source_device_name": dev,
                "related_endpoint": ep,
                "vlan_id": vlan,
                "observed_count": count,
                "evidence": ev,
                "confidence": 85.0,
            },
            headers={"Authorization": f"Bearer {eng_tok}"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "DETECTED"
        det = body["detection"]
        assert det["data_source"] == "SIMULATION"
        assert det["classification"] == "SIMULATION"

    # Deduplication & cooldown: repeating ROGUE_DHCP on SW-IT-01 must NOT create duplicate detection/incident
    inc_count_before = db.query(Incident).count()
    dup_res = client.post(
        "/api/v1/security/detections/evaluate",
        json={
            "detection_type": "ROGUE_DHCP",
            "source_device_name": "SW-IT-01",
            "vlan_id": 20,
            "observed_count": 1,
            "evidence": ["Repeated DHCP Offer"],
        },
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert dup_res.status_code == 200
    assert dup_res.json()["status"] == "DEDUPLICATED"
    assert dup_res.json()["detection"]["occurrence_count"] >= 2
    assert db.query(Incident).count() == inc_count_before

    # False-positive marking suppresses subsequent identical detections
    det_id = dup_res.json()["detection"]["id"]
    fp_res = client.post(
        f"/api/v1/security/detections/{det_id}/false-positive",
        json={"reason": "Authorized lab DHCP test"},
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert fp_res.status_code == 200
    assert fp_res.json()["status"] == "FALSE_POSITIVE"

    sup_res = client.post(
        "/api/v1/security/detections/evaluate",
        json={
            "detection_type": "ROGUE_DHCP",
            "source_device_name": "SW-IT-01",
            "vlan_id": 20,
            "observed_count": 1,
            "evidence": ["Repeated after FP"],
        },
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert sup_res.status_code == 200
    assert sup_res.json()["status"] == "SUPPRESSED_FALSE_POSITIVE"

    # Admin rule threshold update
    upd = client.patch(
        "/api/v1/security/rules/SEC-RULE-001",
        json={"threshold": 5},
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert upd.status_code == 200
    assert upd.json()["threshold"] == 5

    # Clean up
    db.query(SecurityDetection).delete()
    db.commit()
