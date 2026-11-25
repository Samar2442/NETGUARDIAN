from datetime import datetime, timedelta, timezone
from app.models import CampusService, Device, DeviceTelemetry, Incident, NetworkLink
from app.services.service_intelligence import ServiceIntelligenceEngine
from app.services.fault_injection_engine import FaultInjectionEngine


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_seven_campus_services_and_real_dependencies(client, db):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    res = client.get("/api/v1/services", headers={"Authorization": f"Bearer {viewer_tok}"})
    assert res.status_code == 200
    svcs = res.json()
    assert len(svcs) == 7
    keys = {s["service_key"] for s in svcs}
    assert keys == {
        "CAMPUS_INTERNET",
        "CSE_NETWORK",
        "IT_NETWORK",
        "ECE_NETWORK",
        "CAMPUS_DNS",
        "CAMPUS_DHCP",
        "CAMPUS_APP_SERVER",
    }

    # Verify DNS depends on SRV-DNS-01
    res_deps = client.get("/api/v1/services/CAMPUS_DNS/dependencies", headers={"Authorization": f"Bearer {viewer_tok}"})
    assert res_deps.status_code == 200
    dep_names = {d["resource_name"] for d in res_deps.json()}
    assert "SRV-DNS-01" in dep_names


def test_redundant_link_failure_preserves_service_connectivity(db):
    ServiceIntelligenceEngine.seed_campus_services(db)
    cse_svc = db.query(CampusService).filter(CampusService.service_key == "CSE_NETWORK").first()

    # Fail primary link SW-CORE-01 -> SW-DIST-01 (SW-DIST-02 redundant path remains UP)
    core = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()
    dist1 = db.query(Device).filter(Device.hostname == "SW-DIST-01").first()
    link = db.query(NetworkLink).filter(
        NetworkLink.source_device_id == core.id,
        NetworkLink.target_device_id == dist1.id,
    ).first()

    res_inj = FaultInjectionEngine.inject_fault(
        db=db,
        scenario_type="LINK_FAILURE",
        target_device_id="SW-DIST-01",
        target_link_id=link.id,
        created_by="admin",
    )
    health = ServiceIntelligenceEngine.calculate_service_health(db, cse_svc)
    assert health["status"] != "OUTAGE"

    FaultInjectionEngine.recover_fault(db, res_inj["fault"].id, recovered_by="admin")


def test_unknown_service_status_when_telemetry_unavailable(db):
    ServiceIntelligenceEngine.seed_campus_services(db)
    dns_svc = db.query(CampusService).filter(CampusService.service_key == "CAMPUS_DNS").first()
    dns_srv = db.query(Device).filter(Device.hostname == "SRV-DNS-01").first()

    # Clear telemetry & set unknown
    db.query(DeviceTelemetry).delete()
    orig_status = dns_srv.status
    dns_srv.status = "unknown"
    db.commit()

    health = ServiceIntelligenceEngine.calculate_service_health(db, dns_svc)
    assert health["status"] == "UNKNOWN"

    dns_srv.status = orig_status
    db.commit()


def test_sla_mttd_mtta_mttr_and_reports_csv_pdf(client, db):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    headers = {"Authorization": f"Bearer {viewer_tok}"}

    # Create a resolved incident with known ack/resolve timestamps
    now = datetime.now(timezone.utc)
    inc = Incident(
        incident_number="INC-5-SLA-001",
        title="SLA Metric Test",
        description="Test MTTA/MTTR",
        severity="high",
        priority="P2",
        status="RESOLVED",
        lifecycle_state="RESOLVED",
        created_at=now - timedelta(minutes=10),
        acknowledged_at=now - timedelta(minutes=8),
        resolved_at=now - timedelta(minutes=2),
    )
    db.add(inc)
    db.commit()

    res_sla = client.get("/api/v1/sla/overview", headers=headers)
    assert res_sla.status_code == 200
    assert res_sla.json()["data_source"] == "SIMULATION_DEMONSTRATION"

    res_metrics = client.get("/api/v1/sla/metrics", headers=headers)
    assert res_metrics.status_code == 200
    m = res_metrics.json()
    assert m["mtta_seconds"] is not None and m["mtta_seconds"] > 0
    assert m["mttr_seconds"] is not None and m["mttr_seconds"] > 0

    # Test CSV & PDF exports
    for rtype in ["daily_incidents", "monthly_sla", "department_health", "engineer_workload"]:
        r_csv = client.get(f"/api/v1/reports/{rtype}?format=csv", headers=headers)
        assert r_csv.status_code == 200
        assert "text/csv" in r_csv.headers["content-type"]

        r_pdf = client.get(f"/api/v1/reports/{rtype}?format=pdf", headers=headers)
        assert r_pdf.status_code == 200
        assert r_pdf.content.startswith(b"%PDF-1.4")
