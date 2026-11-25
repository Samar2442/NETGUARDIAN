from app.models import AuditLog, Device, SecurityEvidence
from app.services.service_intelligence import ServiceIntelligenceEngine


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_security_incident_evidence_integrity_rca_twin_and_remediation(client, db):
    ServiceIntelligenceEngine.seed_campus_services(db)
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")

    v_headers = {"Authorization": f"Bearer {viewer_tok}"}
    e_headers = {"Authorization": f"Bearer {eng_tok}"}
    a_headers = {"Authorization": f"Bearer {admin_tok}"}

    # 1. Create security incident (viewer rejected, engineer allowed)
    assert client.post(
        "/api/v1/security/incidents",
        json={"title": "Test Sec", "description": "Testing RBAC", "severity": "HIGH"},
        headers=v_headers,
    ).status_code == 403

    inc_res = client.post(
        "/api/v1/security/incidents",
        json={
            "title": "Unauthorized Trunk VLAN Change on SW-IT-01",
            "description": "Detected unexpected VLAN change on SW-IT-01",
            "severity": "HIGH",
            "source_device_name": "SW-IT-01",
            "vlan_ids": [20],
        },
        headers=e_headers,
    )
    assert inc_res.status_code == 201
    inc_id = inc_res.json()["id"]
    assert "IT Department Network" in inc_res.json()["affected_services"]

    # 2. Evidence creation + secret scrubbing + SHA-256 integrity verification
    assert client.get(f"/api/v1/security/incidents/{inc_id}/evidence").status_code == 401
    assert client.post(
        f"/api/v1/security/incidents/{inc_id}/evidence",
        json={"evidence_type": "SYSLOG", "description": "Viewer cannot add evidence"},
        headers=v_headers,
    ).status_code == 403

    ev_res = client.post(
        f"/api/v1/security/incidents/{inc_id}/evidence",
        json={
            "evidence_type": "SYSLOG",
            "description": "User login attempt with password=SuperSecret123 and Bearer eyJhbGciOiJIUzI1NiJ9.abc.def",
            "source_device_name": "SW-IT-01",
        },
        headers=e_headers,
    )
    assert ev_res.status_code == 201
    ev_body = ev_res.json()
    assert "SuperSecret123" not in ev_body["description"]
    assert "[REDACTED]" in ev_body["description"]
    assert len(ev_body["integrity_hash"]) == 64

    ev_list = client.get(f"/api/v1/security/incidents/{inc_id}/evidence", headers=v_headers)
    assert ev_list.status_code == 200
    assert ev_list.json()[0]["integrity_valid"] is True

    # Simulate tampering -> integrity_valid becomes False
    ev_row = db.query(SecurityEvidence).filter(SecurityEvidence.id == ev_body["id"]).first()
    ev_row.description = "Tampered description"
    db.commit()
    ev_list_tampered = client.get(f"/api/v1/security/incidents/{inc_id}/evidence", headers=v_headers)
    assert ev_list_tampered.json()[0]["integrity_valid"] is False

    # 3. Timeline & Assignment integration
    assert client.post(
        f"/api/v1/incidents/{inc_id}/assign",
        json={"assigned_to": "neteng", "priority": "P1"},
        headers=a_headers,
    ).status_code == 200
    tl = client.get(f"/api/v1/incidents/{inc_id}/timeline", headers=v_headers)
    assert tl.status_code == 200
    assert len(tl.json()) >= 2

    # 4. RCA + Digital Twin + Recommendations
    assert client.post(f"/api/v1/diagnostics/run?incident_id={inc_id}", headers=e_headers).status_code == 200
    recs = client.get(f"/api/v1/security/incidents/{inc_id}/recommendations", headers=v_headers)
    assert recs.status_code == 200
    assert recs.json()["digital_twin_impact"]["state_classification"] == "PREDICTED"
    assert recs.json()["rca_summary"] is not None

    # 5. Propose remediation (PENDING_APPROVAL) -> Engineer cannot approve, Admin can approve
    sw = db.query(Device).filter(Device.hostname == "SW-IT-01").first()
    prop_res = client.post(
        f"/api/v1/security/incidents/{inc_id}/propose-remediation",
        json={
            "device_id": sw.id,
            "operation": "ADD_VLAN_TO_TRUNK",
            "target_interface": "GigabitEthernet0/1",
            "parameters": {"vlan_id": 20},
        },
        headers=e_headers,
    )
    assert prop_res.status_code == 201
    prop_id = prop_res.json()["proposal_id"]
    assert prop_res.json()["status"] == "PENDING_APPROVAL"
    assert prop_res.json()["execution_mode"] == "SIMULATION"

    assert client.post(f"/api/v1/remediation/{prop_id}/approve", headers=e_headers).status_code == 403
    assert client.post(f"/api/v1/remediation/{prop_id}/approve", headers=a_headers).status_code == 200

    # Audit trail check
    assert db.query(AuditLog).filter(AuditLog.action == "SECURITY_EVIDENCE_COLLECTED").count() >= 1
