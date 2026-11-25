import ipaddress
import networkx as nx
import pytest
from app.models import Device, NetworkInterface, NetworkLink, VLAN, User, AuditLog
from app.database.campus_seed import seed_campus_network
from app.engines.topology.validation_engine import TopologyValidationEngine
from app.engines.digital_twin.digital_twin_engine import DigitalTwinEngine


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_01_three_departmental_vlans_exist(db):
    vlans = db.query(VLAN).all()
    assert len(vlans) == 3


def test_02_vlan_ids_are_exactly_10_20_30(db):
    vlan_ids = sorted(v.vlan_id for v in db.query(VLAN).all())
    assert vlan_ids == [10, 20, 30]


def test_03_vlan_subnets_are_correct(db):
    subnets = {v.vlan_id: v.subnet for v in db.query(VLAN).all()}
    assert subnets == {
        10: "10.10.10.0/24",
        20: "10.10.20.0/24",
        30: "10.10.30.0/24",
    }


def test_04_vlan_gateways_are_correct(db):
    gateways = {v.vlan_id: v.gateway_ip for v in db.query(VLAN).all()}
    assert gateways == {
        10: "10.10.10.1",
        20: "10.10.20.1",
        30: "10.10.30.1",
    }


def test_05_250_endpoint_assets_generated(db):
    eps = db.query(Device).filter(Device.asset_category == "student_endpoint").all()
    assert len(eps) == 250


def test_06_department_endpoint_counts_correct(db):
    eps = db.query(Device).filter(Device.asset_category == "student_endpoint").all()
    counts = {}
    for e in eps:
        counts[e.department] = counts.get(e.department, 0) + 1
    assert counts == {"CSE": 80, "IT": 100, "ECE": 70}


def test_07_every_endpoint_references_valid_vlan(db):
    valid_vlans = {v.vlan_id for v in db.query(VLAN).all()}
    eps = db.query(Device).filter(Device.asset_category == "student_endpoint").all()
    for e in eps:
        assert e.vlan_id in valid_vlans


def test_08_every_endpoint_references_valid_access_switch(db):
    switch_ids = {
        d.id for d in db.query(Device).filter(Device.device_type == "access_switch").all()
    }
    eps = db.query(Device).filter(Device.asset_category == "student_endpoint").all()
    for e in eps:
        assert e.connected_switch_id in switch_ids


def test_09_mac_addresses_are_unique(db):
    macs = [d.mac_address for d in db.query(Device).all() if d.mac_address]
    assert len(macs) == len(set(m.lower() for m in macs))


def test_10_ip_addresses_are_unique(db):
    ips = [d.management_ip for d in db.query(Device).all() if d.management_ip]
    assert len(ips) == len(set(ips))


def test_11_every_access_switch_has_valid_uplinks(db):
    access_switches = db.query(Device).filter(Device.device_type == "access_switch").all()
    assert len(access_switches) >= 6
    for sw in access_switches:
        uplinks = db.query(NetworkInterface).filter(
            NetworkInterface.device_id == sw.id,
            NetworkInterface.is_uplink == True,
        ).all()
        assert len(uplinks) >= 1, f"{sw.hostname} has no uplink"


def test_12_core_and_distribution_relationships_valid(db):
    core = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()
    dist1 = db.query(Device).filter(Device.hostname == "SW-DIST-01").first()
    dist2 = db.query(Device).filter(Device.hostname == "SW-DIST-02").first()
    assert core is not None and dist1 is not None and dist2 is not None

    links = db.query(NetworkLink).all()
    pairs = {(l.source_device_id, l.target_device_id) for l in links} | {
        (l.target_device_id, l.source_device_id) for l in links
    }
    assert (core.id, dist1.id) in pairs
    assert (core.id, dist2.id) in pairs
    assert (dist1.id, dist2.id) in pairs


def test_13_topology_traversal_and_validation_pass(db):
    val = TopologyValidationEngine.validate_topology(db)
    assert val["valid"] is True, f"Topology validation errors: {val['errors']}"
    assert val["summary"]["critical_errors"] == 0

    G = DigitalTwinEngine.build_topology_graph(db)
    edge_rtr = db.query(Device).filter(Device.hostname == "RTR-EDGE-01").first()
    cse_pc = db.query(Device).filter(Device.hostname == "CSE-PC-001").first()
    path = nx.shortest_path(G, source=edge_rtr.id, target=cse_pc.id)
    assert len(path) >= 5  # Edge -> FW -> Core -> Dist -> Access -> Endpoint


def test_14_invalid_vlan_references_rejected(client):
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")
    res = client.post(
        "/api/v1/vlans",
        json={
            "vlan_id": 5000,
            "name": "INVALID",
            "subnet": "10.10.50.0/24",
            "gateway_ip": "10.10.50.1",
        },
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert res.status_code == 400


def test_15_duplicate_ip_assignments_rejected(client):
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    res = client.post(
        "/api/v1/devices",
        json={
            "hostname": "DUP-IP-TEST",
            "management_ip": "10.10.0.10",  # SW-CORE-01 IP
            "device_type": "server",
        },
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert res.status_code == 400
    assert "duplicate ip" in res.json()["detail"].lower()


def test_16_overlapping_subnets_detected(client):
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")
    res = client.post(
        "/api/v1/vlans",
        json={
            "vlan_id": 40,
            "name": "OVERLAP",
            "subnet": "10.10.10.0/25",  # Overlaps VLAN 10 10.10.10.0/24
            "gateway_ip": "10.10.10.1",
        },
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert res.status_code == 400
    assert "overlaps" in res.json()["detail"].lower()


def test_17_invalid_link_references_rejected(client, db):
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    core = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()

    # Self-link rejected
    res_self = client.post(
        "/api/v1/topology/links",
        json={
            "name": "SELF-LINK",
            "source_device_id": core.id,
            "source_interface_name": "Gi1/0/10",
            "target_device_id": core.id,
            "target_interface_name": "Gi1/0/11",
        },
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert res_self.status_code == 400

    # Nonexistent device rejected
    res_bad = client.post(
        "/api/v1/topology/links",
        json={
            "name": "GHOST-LINK",
            "source_device_id": core.id,
            "source_interface_name": "Gi1/0/10",
            "target_device_id": "nonexistent-device-id",
            "target_interface_name": "Gi0/1",
        },
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert res_bad.status_code == 400


def test_18_unauthorized_topology_modifications_rejected(client, db):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    core = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()

    # Viewer cannot create link
    res1 = client.post(
        "/api/v1/topology/links",
        json={
            "name": "UNAUTH-LINK",
            "source_device_id": core.id,
            "source_interface_name": "Gi1/0/10",
            "target_device_id": core.id,
            "target_interface_name": "Gi1/0/11",
        },
        headers={"Authorization": f"Bearer {viewer_tok}"},
    )
    assert res1.status_code == 403

    # Engineer cannot reset campus topology (admin-only)
    res2 = client.post(
        "/api/v1/topology/reset",
        headers={"Authorization": f"Bearer {eng_tok}"},
    )
    assert res2.status_code == 403


def test_19_seed_is_idempotent_no_duplicates(db):
    before_devs = db.query(Device).count()
    before_vlans = db.query(VLAN).count()
    before_links = db.query(NetworkLink).count()

    seed_campus_network(db, force_reset=False)

    assert db.query(Device).count() == before_devs
    assert db.query(VLAN).count() == before_vlans
    assert db.query(NetworkLink).count() == before_links


def test_20_explicit_authorized_reset_preserves_users_and_audits(client, db):
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")
    user_count_before = db.query(User).count()

    res = client.post(
        "/api/v1/topology/reset",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "reset_complete"
    assert data["vlans"] == 3
    assert db.query(User).count() == user_count_before

    reset_audit = db.query(AuditLog).filter(AuditLog.action == "CAMPUS_TOPOLOGY_RESET").first()
    assert reset_audit is not None


def test_21_campus_overview_and_vlan_endpoints(client):
    viewer_tok = _login(client, "auditor", "ViewerAuditor2026!")
    headers = {"Authorization": f"Bearer {viewer_tok}"}

    res_ov = client.get("/api/v1/topology/campus-overview", headers=headers)
    assert res_ov.status_code == 200
    ov = res_ov.json()
    assert ov["core_switches"] == 1
    assert ov["distribution_switches"] == 2
    assert ov["routers"] == 1
    assert ov["firewalls"] == 1
    assert ov["wireless_aps"] == 6
    assert ov["servers"] == 4
    assert ov["student_endpoints"] == 250

    res_v = client.get("/api/v1/vlans/departments/overview", headers=headers)
    assert res_v.status_code == 200
    depts = {d["vlan_id"]: d["endpoint_count"] for d in res_v.json()}
    assert depts == {10: 80, 20: 100, 30: 70}
