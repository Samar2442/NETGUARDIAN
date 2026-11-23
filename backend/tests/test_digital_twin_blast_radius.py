import pytest
from app.engines.digital_twin.digital_twin_engine import DigitalTwinEngine
from app.engines.blast_radius.blast_radius_engine import BlastRadiusEngine

def test_digital_twin_topology_graph(db):
    G = DigitalTwinEngine.build_topology_graph(db)
    assert len(G.nodes) >= 10
    assert len(G.edges) >= 9

    # Verify React Flow payload layout
    payload = DigitalTwinEngine.get_topology_payload(db)
    assert "nodes" in payload
    assert "edges" in payload
    assert len(payload["nodes"]) >= 10

def test_what_if_vlan_trunk_simulation(db):
    res = DigitalTwinEngine.simulate_failure(
        db=db,
        scenario_type="vlan_removed_from_trunk",
        target_name="HQ-Access-SW-02",
        parameters={"vlan_id": 30}
    )

    assert res["severity"] == "HIGH"
    assert "PC-Student-01" in res["affected_endpoints"]
    assert "VLAN 30 (Student-Lab)" in res["affected_vlans"]
    assert res["redundant_path_available"] is False

def test_blast_radius_calculation(db):
    blast = BlastRadiusEngine.calculate_blast_radius(db, "vlan", "HQ-Access-SW-02")
    assert blast["target"] == "HQ-Access-SW-02"
    assert blast["severity"] == "HIGH"
    assert len(blast["affected_services"]) >= 1
