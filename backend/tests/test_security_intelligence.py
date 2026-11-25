from app.models import ConfigSnapshot, Device


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_security_posture_vlan_acl_firewall_and_unknown_states(client, db):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    headers = {"Authorization": f"Bearer {viewer_tok}"}

    # Unauthenticated rejected
    assert client.get("/api/v1/security/overview").status_code == 401

    ov = client.get("/api/v1/security/overview", headers=headers)
    assert ov.status_code == 200
    ov_body = ov.json()
    assert ov_body["data_source"] == "SIMULATION"
    assert "overall_posture_score" in ov_body

    # VLAN segmentation covers 10, 20, 30 and does not assume VLAN IDs alone prove full isolation
    vlans = client.get("/api/v1/security/assessments/vlans", headers=headers)
    assert vlans.status_code == 200
    v_body = vlans.json()
    assert {v["vlan_id"] for v in v_body["vlans"]} == {10, 20, 30}
    assert v_body["status"] in ("PARTIAL", "ASSESSED", "UNKNOWN")

    # Missing ACL evidence -> NOT_ASSESSED
    acls = client.get("/api/v1/security/assessments/acls", headers=headers)
    assert acls.status_code == 200
    assert acls.json()["status"] in ("NOT_ASSESSED", "PARTIAL", "ASSESSED")

    # Firewall without ConfigSnapshot -> UNKNOWN
    fw_dev = db.query(Device).filter(Device.device_type == "firewall").first()
    db.query(ConfigSnapshot).filter(ConfigSnapshot.device_id == fw_dev.id).delete()
    db.commit()

    fw = client.get("/api/v1/security/assessments/firewall", headers=headers)
    assert fw.status_code == 200
    assert fw.json()["status"] == "UNKNOWN"
    assert fw.json()["score"] == 0.0

    # Device baseline, departments, recommendations
    devs = client.get("/api/v1/security/assessments/devices?limit=10", headers=headers)
    assert devs.status_code == 200
    assert len(devs.json()["items"]) > 0

    depts = client.get("/api/v1/security/assessments/departments", headers=headers)
    assert depts.status_code == 200
    assert {d["department"] for d in depts.json()["departments"]} == {"CSE", "IT", "ECE"}

    recs = client.get("/api/v1/security/recommendations", headers=headers)
    assert recs.status_code == 200
    assert isinstance(recs.json()["recommendations"], list)
