import pytest
from app.models import Device, NetworkInterface, Event, Incident, VLAN, RemediationProposal
from app.engines.correlation.correlation_engine import CorrelationEngine
from app.engines.diagnosis.rca_engine import RootCauseAnalysisEngine
from app.engines.scoring.health_engine import HealthScoringEngine

def test_missing_vlan_from_trunk_rca(db):
    # Setup test condition: HQ-Access-SW-02 has VLAN 30 removed from Gi0/1 allowed list
    sw = db.query(Device).filter(Device.hostname == "HQ-Access-SW-02").first()
    assert sw is not None

    trunk = db.query(NetworkInterface).filter(
        NetworkInterface.device_id == sw.id,
        NetworkInterface.name == "GigabitEthernet0/1"
    ).first()
    assert trunk is not None

    # Simulate missing VLAN 30 from trunk
    trunk.allowed_vlans = "1,10,20,99"
    db.commit()

    # Create correlated incident with VLAN 30 symptoms
    inc = Incident(
        incident_number="TEST-INC-VLAN30",
        title="VLAN 30 Gateway Unreachable",
        description="Multiple endpoints in Student Lab lost connectivity",
        severity="high",
        status="DETECTED",
        source_device_name=sw.hostname,
        affected_vlan_ids=[30],
        affected_endpoints_count=2
    )
    db.add(inc)
    db.commit()

    # Run RCA Engine
    diagnosis = RootCauseAnalysisEngine.diagnose_incident(db, inc)

    # Verify RCA output matches acceptance criteria
    assert diagnosis is not None
    assert diagnosis.confidence == 96.0
    assert "VLAN 30 missing from HQ-Access-SW-02" in diagnosis.root_cause
    assert len(diagnosis.supporting_evidence) >= 4
    assert len(diagnosis.contradicting_evidence) >= 1
    props = db.query(RemediationProposal).filter(RemediationProposal.incident_id == inc.id).all()
    assert len(props) > 0
    assert "switchport trunk allowed vlan add 30" in props[0].proposed_commands

    # Restore healthy baseline
    trunk.allowed_vlans = "1,10,20,30,99"
    db.commit()

def test_event_correlation_groups_symptoms(db):
    # Create two events from different endpoints in same VLAN
    ev1 = Event(
        source_type="endpoint",
        source_name="PC-Student-01",
        event_type="GATEWAY_UNREACHABLE",
        severity="high",
        message="Client cannot ping 10.0.30.1",
        details={"vlan_id": 30}
    )
    db.add(ev1)
    db.commit()

    inc1 = CorrelationEngine.correlate_event(db, ev1)
    assert inc1 is not None

    ev2 = Event(
        source_type="endpoint",
        source_name="PC-Student-02",
        event_type="GATEWAY_UNREACHABLE",
        severity="high",
        message="Client cannot ping 10.0.30.1",
        details={"vlan_id": 30}
    )
    db.add(ev2)
    db.commit()

    inc2 = CorrelationEngine.correlate_event(db, ev2)
    # Both events correlated into the same incident!
    assert inc2.id == inc1.id
    assert inc2.affected_endpoints_count >= 1

def test_transparent_health_scoring(db):
    health = HealthScoringEngine.calculate_health(db)
    assert "overall_health" in health
    assert "availability" in health
    assert "configuration" in health
    assert 0 <= health["overall_health"] <= 100
    assert health["overall_health"] + health["risk_score"] == 100.0
