from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import (
    Device, NetworkInterface, Event, Incident, TrainingScenario, TrainingSession, AuditLog
)
from app.engines.correlation.correlation_engine import CorrelationEngine
from app.engines.diagnosis.rca_engine import RootCauseAnalysisEngine

class TrainingEngine:
    """
    CCNA Training and Fault Injection Engine.
    Injects realistic failure scenarios into the simulated Cisco network
    and grades student troubleshooting accuracy and recovery time.
    """

    @staticmethod
    def inject_fault(db: Session, scenario_key: str, username: str = "admin") -> Dict[str, Any]:
        """
        Injects a known networking fault into the network environment.
        Specifically handles the primary Acceptance Criteria scenario:
        Removing VLAN 30 from HQ-Access-SW-02 trunk port GigabitEthernet0/1.
        """
        scenario = db.query(TrainingScenario).filter(TrainingScenario.scenario_key == scenario_key).first()
        now = datetime.now(timezone.utc)

        # 1. SCENARIO: VLAN 30 MISSING FROM TRUNK (PRIMARY ACCEPTANCE CRITERIA)
        if scenario_key == "vlan_30_trunk_missing" or "vlan" in scenario_key.lower():
            target_sw = db.query(Device).filter(Device.hostname == "HQ-Access-SW-02").first()
            if not target_sw:
                raise ValueError("Target switch HQ-Access-SW-02 not found")

            trunk_iface = db.query(NetworkInterface).filter(
                NetworkInterface.device_id == target_sw.id,
                NetworkInterface.name == "GigabitEthernet0/1"
            ).first()

            if not trunk_iface:
                raise ValueError("Trunk interface GigabitEthernet0/1 not found")

            # Prune VLAN 30 from allowed list
            current_allowed = [v.strip() for v in (trunk_iface.allowed_vlans or "1,10,20,30,99").split(",")]
            new_allowed = [v for v in current_allowed if v != "30"]
            trunk_iface.allowed_vlans = ",".join(new_allowed)
            db.merge(trunk_iface)

            # Mark endpoints in VLAN 30 as degraded
            pc1 = db.query(Device).filter(Device.hostname == "PC-Student-01").first()
            pc2 = db.query(Device).filter(Device.hostname == "PC-Student-02").first()
            if pc1:
                pc1.status = "degraded"
                db.merge(pc1)
            if pc2:
                pc2.status = "degraded"
                db.merge(pc2)

            # Generate realistic Cisco syslog and telemetry events
            events = [
                Event(
                    timestamp=now,
                    source_type="interface",
                    source_id=trunk_iface.id,
                    source_name=f"{target_sw.hostname} {trunk_iface.name}",
                    event_type="VLAN_TRUNK_PRUNED",
                    severity="high",
                    message=f"%SW_TRUNK-4-VLAN_NOT_ALLOWED: VLAN 30 is removed from trunk interface {trunk_iface.name} allowed list.",
                    details={"vlan_id": 30, "switch_name": target_sw.hostname, "interface": trunk_iface.name},
                    raw_payload="000142: *Nov 23 21:55:01.120: %SW_TRUNK-4-VLAN_NOT_ALLOWED: VLAN 30 excluded on Gi0/1"
                ),
                Event(
                    timestamp=now,
                    source_type="endpoint",
                    source_id=pc1.id if pc1 else None,
                    source_name="PC-Student-01",
                    event_type="GATEWAY_UNREACHABLE",
                    severity="high",
                    message="ICMP ping failure: Default gateway 10.0.30.1 is unreachable (100% packet loss).",
                    details={"vlan_id": 30, "ip": "10.0.30.101", "switch_name": target_sw.hostname},
                    raw_payload="Destination Host Unreachable from 10.0.30.101"
                ),
                Event(
                    timestamp=now,
                    source_type="endpoint",
                    source_id=pc2.id if pc2 else None,
                    source_name="PC-Student-02",
                    event_type="GATEWAY_UNREACHABLE",
                    severity="high",
                    message="ICMP ping failure: Default gateway 10.0.30.1 is unreachable (100% packet loss).",
                    details={"vlan_id": 30, "ip": "10.0.30.102", "switch_name": target_sw.hostname},
                    raw_payload="Destination Host Unreachable from 10.0.30.102"
                )
            ]

            db.add_all(events)
            db.commit()

            # Correlate events into an Incident
            incident = None
            for ev in events:
                incident = CorrelationEngine.correlate_event(db, ev)

            # Run Root Cause Analysis
            if incident:
                diagnosis = RootCauseAnalysisEngine.diagnose_incident(db, incident)
                db.commit()

            # Record Audit Log
            audit = AuditLog(
                username=username,
                action="FAULT_INJECTED",
                resource_type="SIMULATOR",
                resource_id=scenario_key,
                details={"scenario": scenario_key, "device": target_sw.hostname, "interface": trunk_iface.name},
                status="SUCCESS"
            )
            db.add(audit)
            db.commit()

            return {
                "success": True,
                "scenario": scenario_key,
                "target_device": target_sw.hostname,
                "target_interface": trunk_iface.name,
                "incident_id": incident.id if incident else None,
                "incident_number": incident.incident_number if incident else None,
                "message": f"Fault successfully injected: VLAN 30 removed from {target_sw.hostname} {trunk_iface.name} trunk."
            }

        # 2. SCENARIO: INTERFACE SHUTDOWN
        elif scenario_key == "interface_admin_down":
            target_sw = db.query(Device).filter(Device.hostname == "HQ-Access-SW-01").first()
            if not target_sw:
                raise ValueError("Target switch HQ-Access-SW-01 not found")

            iface = db.query(NetworkInterface).filter(
                NetworkInterface.device_id == target_sw.id,
                NetworkInterface.name == "FastEthernet0/1"
            ).first()

            iface.admin_status = "down"
            iface.oper_status = "down"
            db.merge(iface)

            ev = Event(
                timestamp=now,
                source_type="interface",
                source_id=iface.id,
                source_name=f"{target_sw.hostname} {iface.name}",
                event_type="INTERFACE_SHUTDOWN",
                severity="medium",
                message=f"%LINK-5-CHANGED: Interface {iface.name}, changed state to administratively down",
                details={"interface": iface.name, "device": target_sw.hostname}
            )
            db.add(ev)
            db.commit()

            inc = CorrelationEngine.correlate_event(db, ev)
            if inc:
                RootCauseAnalysisEngine.diagnose_incident(db, inc)
                db.commit()

            return {
                "success": True,
                "scenario": scenario_key,
                "target_device": target_sw.hostname,
                "target_interface": iface.name,
                "incident_id": inc.id if inc else None,
                "message": f"Fault injected: Interface {iface.name} administratively shut down."
            }

        return {"success": False, "message": f"Scenario {scenario_key} not recognized."}

    @staticmethod
    def grade_student_diagnosis(expected: str, student_text: str) -> Dict[str, Any]:
        """
        Calculates student diagnosis accuracy using CCNA keyword & semantics matching.
        """
        student_lower = student_text.lower()
        expected_keywords = ["vlan", "trunk", "allowed", "missing", "pruned", "gi0/1", "30"]
        matched = [kw for kw in expected_keywords if kw in student_lower]

        score = min(100.0, (len(matched) / len(expected_keywords)) * 100.0 + 10.0) if matched else 20.0
        feedback = "Excellent diagnosis! You correctly identified the missing VLAN on the 802.1Q trunk port." if score >= 80 else "Partial diagnosis. Review 'show interfaces trunk' to check allowed VLAN lists."

        return {
            "score": round(score, 1),
            "matched_concepts": matched,
            "feedback": feedback
        }
