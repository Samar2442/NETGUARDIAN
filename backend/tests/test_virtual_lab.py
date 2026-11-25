from unittest.mock import patch
from app.models import Device
from app.services.eve_ng_connector import EVENGConnector
from app.services.gns3_connector import GNS3Connector


def _login(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_gns3_and_eveng_discovery_sync_and_campus_preservation(client, db):
    admin_tok = _login(client, "admin", "NetGuardianAdmin2026!")
    eng_tok = _login(client, "neteng", "CiscoEngineer2026!")
    a_h = {"Authorization": f"Bearer {admin_tok}"}
    e_h = {"Authorization": f"Bearer {eng_tok}"}

    sim_count_before = db.query(Device).filter(Device.environment == "SIMULATION").count()

    # 1. Register GNS3 server (admin only)
    gns3_srv = client.post(
        "/api/v1/integrations/labs/servers",
        json={"name": "Campus GNS3 Lab", "lab_type": "GNS3", "base_url": "http://127.0.0.1:3080"},
        headers=a_h,
    )
    assert gns3_srv.status_code == 201
    gns3_id = gns3_srv.json()["id"]

    with patch.object(GNS3Connector, "test_connection", return_value={"connected": True, "version": "2.2.46"}), \
         patch.object(GNS3Connector, "list_projects", return_value=[{"project_id": "proj-1", "name": "CCNA-Lab", "status": "opened"}]):
        disc = client.post(f"/api/v1/integrations/labs/servers/{gns3_id}/discover", headers=e_h)
        assert disc.status_code == 200
        assert disc.json()["projects"][0]["project_id"] == "proj-1"

    # Sync GNS3 topology (including a node named SW-CORE-01 to verify campus seed preservation!)
    topo_1 = {
        "project": {"project_id": "proj-1", "name": "CCNA-Lab"},
        "nodes": [
            {"node_id": "n1", "name": "SW-CORE-01", "status": "started", "node_type": "iou"},
            {"node_id": "n2", "name": "GNS3-RTR-02", "status": "started", "node_type": "dynamips"},
        ],
        "links": [
            {"link_id": "l1", "nodes": [{"node_id": "n1", "port_number": 0}, {"node_id": "n2", "port_number": 0}]}
        ],
    }
    with patch.object(GNS3Connector, "get_project_topology", return_value=topo_1):
        s1 = client.post(
            f"/api/v1/integrations/labs/servers/{gns3_id}/sync",
            json={"target_id": "proj-1"},
            headers=e_h,
        )
        assert s1.status_code == 200
        assert s1.json()["created_devices"] == 2
        assert s1.json()["created_links"] == 1

    # Duplicate prevention on re-sync + deleted node marked offline
    topo_2 = {
        "project": {"project_id": "proj-1", "name": "CCNA-Lab"},
        "nodes": [
            {"node_id": "n1", "name": "SW-CORE-01", "status": "started", "node_type": "iou"},
        ],
        "links": [],
    }
    with patch.object(GNS3Connector, "get_project_topology", return_value=topo_2):
        s2 = client.post(
            f"/api/v1/integrations/labs/servers/{gns3_id}/sync",
            json={"target_id": "proj-1"},
            headers=e_h,
        )
        assert s2.status_code == 200
        assert s2.json()["created_devices"] == 0
        assert s2.json()["updated_devices"] == 1
        assert s2.json()["removed_or_offline_devices"] == 1

    # Verify SIMULATION campus devices untouched
    assert db.query(Device).filter(Device.environment == "SIMULATION").count() == sim_count_before
    assert db.query(Device).filter(Device.hostname == "LAB-SW-CORE-01", Device.environment == "LAB").count() == 1

    # 2. Register EVE-NG server & verify explicit UNSUPPORTED capability reporting
    eve_srv = client.post(
        "/api/v1/integrations/labs/servers",
        json={"name": "Campus EVE-NG", "lab_type": "EVE_NG", "base_url": "http://127.0.0.1:8080"},
        headers=a_h,
    )
    assert eve_srv.status_code == 201
    eve_id = eve_srv.json()["id"]

    with patch.object(EVENGConnector, "test_connection", return_value={
        "connected": True,
        "status": {"version": "5.0.1"},
        "unsupported_capabilities": EVENGConnector.UNSUPPORTED_CAPABILITIES,
    }), patch.object(EVENGConnector, "list_labs", return_value=[{"file": "Campus.unl", "path": "/Campus.unl"}]):
        e_disc = client.post(f"/api/v1/integrations/labs/servers/{eve_id}/discover", headers=e_h)
        assert e_disc.status_code == 200
        assert "interface_counters_polling" in e_disc.json()["unsupported_capabilities"]
