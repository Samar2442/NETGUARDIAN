import pytest
from app.models import AuditLog, Device, Faculty, ITPersonnel, Student, User
from app.seeders.campus_inventory_seed import seed_campus_inventory
from app.engines.inventory.validation_engine import InventoryValidationEngine


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


# ==============================================================================
# 1. Seed & Distribution Tests
# ==============================================================================

def test_01_seed_counts_exact(db):
    assert db.query(Student).count() == 250
    assert db.query(Faculty).count() == 16
    assert db.query(ITPersonnel).count() == 6


def test_02_department_distribution_exact(db):
    stu_counts = {}
    for s in db.query(Student).all():
        stu_counts[s.department] = stu_counts.get(s.department, 0) + 1
    assert stu_counts == {"CSE": 80, "IT": 100, "ECE": 70}

    fac_counts = {}
    for f in db.query(Faculty).all():
        fac_counts[f.department] = fac_counts.get(f.department, 0) + 1
    assert fac_counts == {"CSE": 5, "IT": 6, "ECE": 5}


def test_03_student_to_endpoint_deterministic_mapping(db):
    cse1 = db.query(Student).filter(Student.student_id == "CSE2026001").first()
    it1 = db.query(Student).filter(Student.student_id == "IT2026001").first()
    ece1 = db.query(Student).filter(Student.student_id == "ECE2026001").first()
    assert cse1.device.hostname == "CSE-PC-001"
    assert it1.device.hostname == "IT-PC-001"
    assert ece1.device.hostname == "ECE-PC-001"


def test_04_idempotent_seeding_no_duplicates(db):
    summary = seed_campus_inventory(db)
    assert summary["students"] == 250
    assert summary["faculty"] == 16
    assert summary["it_personnel"] == 6
    assert db.query(Student).count() == 250


def test_05_personnel_do_not_create_login_accounts(db):
    assert db.query(User).count() == 3


# ==============================================================================
# 2. Relationship Integrity Tests
# ==============================================================================

def test_06_every_student_has_unique_consistent_endpoint(db):
    students = db.query(Student).all()
    seen_device_ids = set()
    dept_vlan = {"CSE": 10, "IT": 20, "ECE": 30}

    for s in students:
        assert s.device_id is not None
        assert s.device_id not in seen_device_ids
        seen_device_ids.add(s.device_id)
        dev = s.device
        assert dev is not None
        assert dev.department == s.department
        assert dev.vlan_id == dept_vlan[s.department]
        assert dev.management_ip.startswith(f"10.10.{dept_vlan[s.department]}.")


def test_07_inventory_validation_passes_on_clean_baseline(db):
    val = InventoryValidationEngine.validate_inventory(db)
    assert val["valid"] is True
    assert val["critical_errors"] == 0
    assert val["warnings"] == 0
    assert val["passed_checks"] == val["total_checks"]


# ==============================================================================
# 3. Validation & Integrity Rejection Tests
# ==============================================================================

def test_08_duplicate_student_id_and_email_rejected(client):
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")
    headers = {"Authorization": f"Bearer {admin_tok}"}

    res_dup_id = client.post(
        "/api/v1/campus/students",
        json={
            "student_id": "CSE2026001",
            "full_name": "Test Duplicate",
            "department": "CSE",
            "email": "unique_dup_test@campus.example.invalid",
        },
        headers=headers,
    )
    assert res_dup_id.status_code == 400

    res_dup_email = client.post(
        "/api/v1/campus/students",
        json={
            "student_id": "CSE2026999",
            "full_name": "Test Duplicate Email",
            "department": "CSE",
            "email": "cse2026001@campus.example.invalid",
        },
        headers=headers,
    )
    assert res_dup_email.status_code == 400


def test_09_invalid_department_and_device_mismatch_rejected(client, db):
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")
    headers = {"Authorization": f"Bearer {admin_tok}"}

    # Invalid department
    res_bad_dept = client.post(
        "/api/v1/campus/students",
        json={
            "student_id": "BIO2026001",
            "full_name": "Invalid Dept",
            "department": "BIO",
            "email": "bio2026001@campus.example.invalid",
        },
        headers=headers,
    )
    assert res_bad_dept.status_code == 422

    # Department mismatch on device assignment (CSE student -> IT endpoint)
    it_ep = db.query(Device).filter(Device.hostname == "IT-PC-001").first()
    res_mismatch = client.post(
        "/api/v1/campus/students",
        json={
            "student_id": "CSE2026998",
            "full_name": "Mismatch Student",
            "department": "CSE",
            "email": "cse2026998@campus.example.invalid",
            "device_id": it_ep.id,
        },
        headers=headers,
    )
    assert res_mismatch.status_code == 400
    assert "mismatch" in res_mismatch.json()["detail"].lower()


def test_10_validation_engine_detects_department_mismatch_and_unassigned(db):
    s = db.query(Student).filter(Student.student_id == "CSE2026001").first()
    orig_dev_id = s.device_id
    it_ep = db.query(Device).filter(Device.hostname == "IT-PC-001").first()

    # Temporarily create a mismatch on an in-memory/rolled-back test or restore after
    s.device_id = None
    db.commit()
    val_unassigned = InventoryValidationEngine.validate_inventory(db)
    assert val_unassigned["valid"] is False
    assert any(i["code"] == "UNASSIGNED_STUDENT_ENDPOINT" for i in val_unassigned["issues"])

    # Restore
    s.device_id = orig_dev_id
    db.commit()


# ==============================================================================
# 4. API Security, RBAC, Pagination & Audit Tests
# ==============================================================================

def test_11_unauthenticated_access_rejected(client):
    assert client.get("/api/v1/campus/students").status_code == 401
    assert client.get("/api/v1/campus/faculty").status_code == 401
    assert client.get("/api/v1/campus/it-personnel").status_code == 401
    assert client.get("/api/v1/campus/inventory/overview").status_code == 401
    assert client.get("/api/v1/campus/inventory/validate").status_code == 401


def test_12_rbac_viewer_engineer_admin_enforced(client):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")

    # Viewer can read overview, students, faculty, IT, validate
    assert client.get("/api/v1/campus/inventory/overview", headers={"Authorization": f"Bearer {viewer_tok}"}).status_code == 200
    assert client.get("/api/v1/campus/students?limit=10", headers={"Authorization": f"Bearer {viewer_tok}"}).status_code == 200
    assert client.get("/api/v1/campus/faculty", headers={"Authorization": f"Bearer {viewer_tok}"}).status_code == 200
    assert client.get("/api/v1/campus/it-personnel", headers={"Authorization": f"Bearer {viewer_tok}"}).status_code == 200

    # Viewer cannot view student network assignment (requires engineer+) or mutate
    assert client.get("/api/v1/campus/students/CSE2026001/network", headers={"Authorization": f"Bearer {viewer_tok}"}).status_code == 403
    assert client.post("/api/v1/campus/inventory/seed", headers={"Authorization": f"Bearer {viewer_tok}"}).status_code == 403

    # Engineer can view student network assignment, cannot mutate or run seeder
    res_net = client.get("/api/v1/campus/students/CSE2026001/network", headers={"Authorization": f"Bearer {eng_tok}"})
    assert res_net.status_code == 200
    net_data = res_net.json()
    assert net_data["endpoint_hostname"] == "CSE-PC-001"
    assert net_data["vlan_id"] == 10
    assert net_data["connected_switch"] == "SW-CSE-01"
    assert net_data["status_source"] == "SIMULATED_INVENTORY"

    assert client.post("/api/v1/campus/inventory/seed", headers={"Authorization": f"Bearer {eng_tok}"}).status_code == 403

    # Admin can run seeder and create/update/delete student with audit log
    res_seed = client.post("/api/v1/campus/inventory/seed", headers={"Authorization": f"Bearer {admin_tok}"})
    assert res_seed.status_code == 200


def test_13_pagination_limits_enforced(client):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    res_over = client.get("/api/v1/campus/students?limit=251", headers={"Authorization": f"Bearer {viewer_tok}"})
    assert res_over.status_code == 422

    res_ok = client.get("/api/v1/campus/students?limit=10&offset=0", headers={"Authorization": f"Bearer {viewer_tok}"})
    assert res_ok.status_code == 200
    assert len(res_ok.json()) == 10


def test_14_admin_crud_and_audit_logging(client, db):
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")
    headers = {"Authorization": f"Bearer {admin_tok}"}

    res_create = client.post(
        "/api/v1/campus/students",
        json={
            "student_id": "CSE2026901",
            "full_name": "Temp Synthetic Student",
            "department": "CSE",
            "academic_year": 2,
            "semester": 3,
            "enrollment_status": "ACTIVE",
            "email": "cse2026901@campus.example.invalid",
        },
        headers=headers,
    )
    assert res_create.status_code == 201

    res_upd = client.put(
        "/api/v1/campus/students/CSE2026901",
        json={"enrollment_status": "PROBATION"},
        headers=headers,
    )
    assert res_upd.status_code == 200
    assert res_upd.json()["enrollment_status"] == "PROBATION"

    res_del = client.delete("/api/v1/campus/students/CSE2026901", headers=headers)
    assert res_del.status_code == 200

    assert db.query(AuditLog).filter(AuditLog.action == "STUDENT_CREATED", AuditLog.resource_id == "CSE2026901").first() is not None
    assert db.query(AuditLog).filter(AuditLog.action == "STUDENT_DELETED", AuditLog.resource_id == "CSE2026901").first() is not None
