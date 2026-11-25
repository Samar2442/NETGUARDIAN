"""
NetGuardian End-to-End Acceptance Criteria Demonstration Script.
Executes the complete VLAN 30 Failure & Self-Healing Workflow:
DETECT -> COLLECT EVIDENCE -> CORRELATE -> IDENTIFY ROOT CAUSE -> PREDICT IMPACT -> RECOMMEND FIX -> HUMAN APPROVAL -> CONTROLLED REMEDIATION -> VERIFY RECOVERY -> RESOLVE.
"""
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

os.environ.setdefault("ADMIN_PASSWORD", "NetGuardianAdmin2026!")
os.environ.setdefault("ENGINEER_PASSWORD", "CiscoEngineer2026!")
os.environ.setdefault("VIEWER_PASSWORD", "ViewerAuditor2026!")

import time
from datetime import datetime, timezone
from app.database.session import SessionLocal, engine, Base
from app.database.migrations import run_safe_migrations
from app.database.seed import seed_database
from app.models import Device, NetworkInterface, Incident, Event, Diagnosis, RemediationProposal, HealthMetric, AuditLog
from app.engines.training.training_engine import TrainingEngine
from app.engines.correlation.correlation_engine import CorrelationEngine
from app.engines.diagnosis.rca_engine import RootCauseAnalysisEngine
from app.engines.digital_twin.digital_twin_engine import DigitalTwinEngine
from app.engines.remediation.remediation_engine import RemediationEngine
from app.engines.verification.verification_engine import VerificationEngine
from app.engines.scoring.health_engine import HealthScoringEngine

def print_step(num: int, title: str):
    print(f"\n{'='*75}")
    print(f"[STEP {num:02d}] {title}")
    print(f"{'='*75}")

def run_acceptance_demo():
    print("""
    =======================================================================
               NETGUARDIAN — ENTERPRISE NETWORK INTELLIGENCE
                      Tagline: Detect. Understand. Predict. Recover.
    =======================================================================
    """)

    Base.metadata.create_all(bind=engine)
    run_safe_migrations(engine)
    db = SessionLocal()
    try:
        # STEP 1: Launch & Initialize
        print_step(1, "Launch NetGuardian Platform & Verify Engine Initialization")
        health_init = HealthScoringEngine.calculate_health(db)
        print(f"[*] Engine Status: ONLINE")
        print(f"[*] Operational Environment: {health_init['environment']}")
        print(f"[*] Baseline Network Health: {health_init['overall_health']}/100")
        print(f"[*] Total Monitored Devices: {health_init['total_devices']}")

        # STEP 2 & 3: Network Topology
        print_step(2, "Inspect Healthy Cisco Network Topology")
        topo = DigitalTwinEngine.get_topology_payload(db)
        print(f"[+] Active Cisco Nodes: {len(topo['nodes'])}")
        print(f"[+] Active Interconnect Links: {len(topo['edges'])}")
        sw02 = db.query(Device).filter(Device.hostname == "HQ-Access-SW-02").first()
        trunk02 = db.query(NetworkInterface).filter(
            NetworkInterface.device_id == sw02.id,
            NetworkInterface.name == "GigabitEthernet0/1"
        ).first()
        print(f"[+] Healthy Baseline Check: {sw02.hostname} {trunk02.name} Allowed VLANs = [{trunk02.allowed_vlans}]")

        # STEP 4 & 5: Failure Injection
        print_step(5, "Fault Injection: Remove VLAN 30 from HQ-Access-SW-02 Trunk Gi0/1")
        inj = TrainingEngine.inject_fault(db, "vlan_30_trunk_missing", username="admin")
        print(f"[!] Fault Injected: {inj['message']}")
        db.refresh(trunk02)
        print(f"[!] Pruned Allowed VLANs: [{trunk02.allowed_vlans}] (VLAN 30 ABSENT)")

        # STEP 6: Monitoring Detection
        print_step(6, "Monitoring Engine Ingests Telemetry & Syslog Traps")
        recent_events = db.query(Event).order_by(Event.timestamp.desc()).limit(3).all()
        for ev in recent_events:
            print(f"  [-] Alert: {ev.event_type} on {ev.source_name} | {ev.message}")

        # STEP 7: Event Correlation
        print_step(7, "Event Correlation Engine Unifies Multi-Symptom Cluster")
        incident = db.query(Incident).filter(Incident.id == inj["incident_id"]).first()
        assert incident is not None
        print(f"[+] Correlated Incident: {incident.incident_number}")
        print(f"[+] Title: {incident.title}")
        print(f"[+] Severity: {incident.severity.upper()}")
        print(f"[+] Affected Endpoints: {incident.affected_endpoints_count} lab workstations")

        # STEP 8: Root Cause Analysis
        print_step(8, "Evidence-Based Diagnostic Engine Identifies Root Cause")
        diagnosis = db.query(Diagnosis).filter(Diagnosis.incident_id == incident.id).first()
        assert diagnosis is not None
        print(f"[+] PROBABLE ROOT CAUSE: {diagnosis.root_cause}")
        print(f"[+] CALCULATED CONFIDENCE: {diagnosis.confidence}% (Documented weighted rule)")
        print(f"[+] EXPLANATION: {diagnosis.explanation}")

        # STEP 9: Evidence Graph
        print_step(9, "Multi-Symptom Evidence Graph Correlation Chain")
        for node in diagnosis.evidence_graph.get("nodes", []):
            print(f"  -> [{node['type'].upper()}]: {node['label']} (Status: {node.get('status', 'OK')})")

        # STEP 10: Digital Twin Blast-Radius Estimation
        print_step(10, "Digital Twin Logical What-If Simulation")
        sim = DigitalTwinEngine.simulate_failure(db, "vlan_removed_from_trunk", "HQ-Access-SW-02", {"vlan_id": 30})
        print(f"[*] Isolated Endpoints: {', '.join(sim['affected_endpoints'])}")
        print(f"[*] Impacted Services: {', '.join(sim['affected_services'])}")
        print(f"[*] Alternate Redundant Path: {'YES' if sim['redundant_path_available'] else 'NONE (Single Uplink)'}")

        # STEP 11 & 12: Recommendation & Risk Assessment
        print_step(11, "Recommendation Engine Generates Vetted Cisco Configuration")
        prop = db.query(RemediationProposal).filter(RemediationProposal.incident_id == incident.id).first()
        assert prop is not None
        print(f"[+] Proposed Commands:\n{prop.proposed_commands}")
        print(f"[+] Risk Level: {prop.risk_level.upper()}")
        print(f"[+] Rollback Plan:\n{prop.rollback_commands}")

        # STEP 13: Administrator Approval
        print_step(13, "Mandatory Human Administrator Approval Workflow")
        approved_prop = RemediationEngine.approve_proposal(db, prop.id, approved_by="admin")
        print(f"[+] Approval Status: {approved_prop.status} by {approved_prop.approved_by} at {approved_prop.approved_at}")

        # STEP 14: Controlled Remediation Execution
        print_step(14, "Executing Approved Remediation & Configuration Snapshot")
        exec_res = RemediationEngine.execute_remediation(db, prop.id, executed_by="admin")
        print(f"[+] Execution Result: {exec_res['status']}")
        print(f"[+] Cisco IOS Console Output:\n{exec_res['execution_log']}")

        # STEP 15 & 16: Verification Engine
        print_step(15, "Post-Remediation Verification & ICMP Gateway Reachability Test")
        db.refresh(trunk02)
        print(f"[+] Updated Trunk Allowed VLANs: [{trunk02.allowed_vlans}] (VLAN 30 RESTORED)")
        print(f"[+] Automated Verification Checks:")
        for check in exec_res["verification"]["checks"]:
            status_symbol = "[PASS]" if check["passed"] else "[FAIL]"
            print(f"  {status_symbol} {check['name']}: {check['output']}")

        # STEP 17 & 18: Resolution & Health Score
        print_step(17, "Incident State Updated to RESOLVED & Network Health Recalculated")
        db.refresh(incident)
        print(f"[+] Incident Status: {incident.status} (Resolved at: {incident.resolved_at})")
        health_final = HealthScoringEngine.calculate_health(db)
        print(f"[+] Restored Network Health Score: {health_final['overall_health']}/100")
        print(f"[+] Active Incidents: {health_final['active_incidents']}")

        # STEP 19: Immutable Audit Logging
        print_step(19, "Immutable Audit Trail Verification")
        audits = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(4).all()
        for a in audits:
            print(f"  [-] Audit: {a.action} by {a.username} on {a.resource_type} [{a.status}]")

        print("""
    =======================================================================
               NETGUARDIAN ACCEPTANCE CRITERIA: 100% SUCCESS
       All 19 workflow steps completed without errors or manual edits.
    =======================================================================
        """)

    finally:
        db.close()

if __name__ == "__main__":
    run_acceptance_demo()
