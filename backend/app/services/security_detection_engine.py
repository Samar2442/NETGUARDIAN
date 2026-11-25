from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.models import (
    AuditLog,
    Device,
    Event,
    Incident,
    IncidentActivity,
    SecurityDetection,
    SecurityDetectionRule,
)
from app.engines.correlation.correlation_engine import CorrelationEngine

VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"}

DEFAULT_SECURITY_RULES = [
    {
        "rule_id": "SEC-RULE-001",
        "name": "Repeated Authentication Failures",
        "detection_type": "AUTH_FAILURE_BURST",
        "severity": "HIGH",
        "threshold": 3,
        "window_seconds": 300,
        "cooldown_seconds": 120,
        "description": "Detects repeated failed login attempts within a bounded time window.",
    },
    {
        "rule_id": "SEC-RULE-002",
        "name": "Suspicious Login Pattern",
        "detection_type": "SUSPICIOUS_LOGIN_PATTERN",
        "severity": "HIGH",
        "threshold": 2,
        "window_seconds": 300,
        "cooldown_seconds": 180,
        "description": "Detects anomalous login patterns or role-escalation audit events.",
    },
    {
        "rule_id": "SEC-RULE-003",
        "name": "Unauthorized Device Appearance",
        "detection_type": "UNAUTHORIZED_DEVICE",
        "severity": "HIGH",
        "threshold": 1,
        "window_seconds": 300,
        "cooldown_seconds": 120,
        "description": "Detects an unrecognized MAC or host not present in authorized campus inventory.",
    },
    {
        "rule_id": "SEC-RULE-004",
        "name": "Rogue DHCP Server Indicator",
        "detection_type": "ROGUE_DHCP",
        "severity": "CRITICAL",
        "threshold": 1,
        "window_seconds": 300,
        "cooldown_seconds": 120,
        "description": "Detects unauthorized DHCP Offer/Ack traffic outside SRV-DHCP-01.",
    },
    {
        "rule_id": "SEC-RULE-005",
        "name": "ARP Anomaly / Spoofing Indicator",
        "detection_type": "ARP_ANOMALY",
        "severity": "HIGH",
        "threshold": 2,
        "window_seconds": 300,
        "cooldown_seconds": 120,
        "description": "Detects conflicting ARP bindings or gratuitous ARP bursts on access VLANs.",
    },
    {
        "rule_id": "SEC-RULE-006",
        "name": "Port-Security Violation",
        "detection_type": "PORT_SECURITY_VIOLATION",
        "severity": "MEDIUM",
        "threshold": 1,
        "window_seconds": 300,
        "cooldown_seconds": 120,
        "description": "Detects switchport MAC limit exceeded or err-disable port-security trap.",
    },
    {
        "rule_id": "SEC-RULE-007",
        "name": "MAC Address Change / Flapping",
        "detection_type": "MAC_ADDRESS_CHANGE",
        "severity": "MEDIUM",
        "threshold": 2,
        "window_seconds": 300,
        "cooldown_seconds": 120,
        "description": "Detects rapid MAC address moves across access switch ports.",
    },
    {
        "rule_id": "SEC-RULE-008",
        "name": "Unexpected VLAN Change",
        "detection_type": "UNEXPECTED_VLAN_CHANGE",
        "severity": "HIGH",
        "threshold": 1,
        "window_seconds": 300,
        "cooldown_seconds": 120,
        "description": "Detects unauthorized access or trunk VLAN membership modification.",
    },
    {
        "rule_id": "SEC-RULE-009",
        "name": "Suspicious Management-Plane Access",
        "detection_type": "SUSPICIOUS_MGMT_ACCESS",
        "severity": "CRITICAL",
        "threshold": 1,
        "window_seconds": 300,
        "cooldown_seconds": 120,
        "description": "Detects management access from non-management VLANs or insecure protocols.",
    },
    {
        "rule_id": "SEC-RULE-010",
        "name": "Unusual Network Traffic Pattern",
        "detection_type": "UNUSUAL_TRAFFIC_PATTERN",
        "severity": "MEDIUM",
        "threshold": 2,
        "window_seconds": 300,
        "cooldown_seconds": 120,
        "description": "Detects abnormal east-west or broadcast/multicast traffic bursts.",
    },
]


class SecurityDetectionEngine:
    """
    Defensive rule-based Security Event Monitoring and Threat Detection Engine.
    All simulated detections are explicitly labeled SIMULATION.
    Supports thresholds, deduplication, cooldown, suppression, and false-positive marking.
    """

    @staticmethod
    def seed_rules(db: Session) -> int:
        existing = {r.rule_id for r in db.query(SecurityDetectionRule).all()}
        for spec in DEFAULT_SECURITY_RULES:
            if spec["rule_id"] not in existing:
                db.add(SecurityDetectionRule(**spec))
        db.commit()
        return db.query(SecurityDetectionRule).count()

    @staticmethod
    def evaluate_signal(
        db: Session,
        detection_type: str,
        source_device_name: Optional[str] = None,
        related_endpoint: Optional[str] = None,
        vlan_id: Optional[int] = None,
        evidence: Optional[List[str]] = None,
        observed_count: int = 1,
        confidence: float = 82.0,
        severity_override: Optional[str] = None,
        create_incident_if_high: bool = True,
    ) -> Dict[str, Any]:
        SecurityDetectionEngine.seed_rules(db)
        rule = db.query(SecurityDetectionRule).filter(
            SecurityDetectionRule.detection_type == detection_type
        ).first()
        if not rule:
            return {"status": "UNKNOWN_RULE", "detection": None}
        if not rule.enabled:
            return {"status": "RULE_DISABLED", "detection": None}

        now = datetime.now(timezone.utc)
        severity = (severity_override or rule.severity).upper()
        if severity not in VALID_SEVERITIES:
            severity = rule.severity

        ev_list = [str(x)[:300] for x in (evidence or [])]
        classification = "UNCERTAIN" if (not ev_list or confidence < 50.0) else "SIMULATION"

        # Resolve device & department
        dev = None
        if source_device_name:
            dev = db.query(Device).filter(
                (Device.hostname == source_device_name) | (Device.id == source_device_name)
            ).first()
        dept = dev.department if dev else None
        if not vlan_id and dev and dev.vlan_id:
            vlan_id = dev.vlan_id

        # Check threshold
        if observed_count < rule.threshold:
            return {
                "status": "BELOW_THRESHOLD",
                "rule_id": rule.rule_id,
                "observed_count": observed_count,
                "threshold": rule.threshold,
                "detection": None,
            }

        # Check false-positive suppression or active deduplication window
        dedup_cutoff = now - timedelta(seconds=rule.window_seconds)
        cooldown_cutoff = now - timedelta(seconds=rule.cooldown_seconds)

        recent = (
            db.query(SecurityDetection)
            .filter(
                SecurityDetection.detection_type == detection_type,
                SecurityDetection.source_device_name == (dev.hostname if dev else source_device_name),
                SecurityDetection.timestamp >= dedup_cutoff,
            )
            .order_by(SecurityDetection.timestamp.desc())
            .first()
        )
        if recent:
            if recent.status == "FALSE_POSITIVE":
                return {
                    "status": "SUPPRESSED_FALSE_POSITIVE",
                    "detection": recent,
                }
            # Deduplicate / Cooldown: increment occurrence_count, do NOT create duplicate incident
            recent.occurrence_count = (recent.occurrence_count or 1) + 1
            recent.last_seen_at = now
            if recent.timestamp and recent.timestamp.replace(tzinfo=timezone.utc) >= cooldown_cutoff:
                recent.status = "SUPPRESSED" if recent.status == "OPEN" else recent.status
            db.commit()
            db.refresh(recent)
            return {
                "status": "DEDUPLICATED",
                "detection": recent,
            }

        # Emit normalized Event (SIMULATION)
        event = Event(
            event_type=detection_type,
            event_code=f"%SEC-4-{detection_type}",
            severity=severity,
            source_type="device" if dev else "security_monitor",
            source_id=dev.id if dev else "sec-monitor",
            source_name=dev.hostname if dev else (source_device_name or "Campus-Security-Monitor"),
            device_id=dev.id if dev else None,
            vlan_id=vlan_id,
            message=f"[{classification}] {rule.name}: {'; '.join(ev_list) if ev_list else 'Threshold triggered'}",
            details={"source": "SIMULATION", "rule_id": rule.rule_id, "endpoint": related_endpoint},
            timestamp=now,
        )
        db.add(event)
        db.flush()

        linked_incident: Optional[Incident] = None
        if create_incident_if_high and severity in {"CRITICAL", "HIGH"} and classification != "UNCERTAIN":
            linked_incident = CorrelationEngine.correlate_event(db, event)
            if linked_incident:
                linked_incident.incident_category = "SECURITY"
                linked_incident.security_severity = severity
                db.merge(linked_incident)

        det = SecurityDetection(
            detection_type=detection_type,
            rule_id=rule.rule_id,
            severity=severity,
            confidence=confidence,
            source_device_id=dev.id if dev else None,
            source_device_name=dev.hostname if dev else source_device_name,
            related_endpoint=related_endpoint,
            vlan_id=vlan_id,
            department=dept,
            timestamp=now,
            last_seen_at=now,
            occurrence_count=observed_count,
            supporting_evidence=ev_list,
            status="CORRELATED" if linked_incident else "OPEN",
            data_source="SIMULATION",
            classification=classification,
            event_id=event.id,
            incident_id=linked_incident.id if linked_incident else None,
        )
        db.add(det)
        db.commit()
        db.refresh(det)
        return {
            "status": "DETECTED",
            "detection": det,
            "incident_id": linked_incident.id if linked_incident else None,
        }

    @staticmethod
    def scan_auth_audit_logs(db: Session, hours: int = 1) -> List[SecurityDetection]:
        """Evaluates recent AuditLog failed logins / role-escalation attempts."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        failed_logins = db.query(AuditLog).filter(
            AuditLog.action.in_(["LOGIN_FAILED", "TOKEN_VALIDATION_FAILED"]),
            AuditLog.timestamp >= cutoff,
        ).count()
        detections: List[SecurityDetection] = []
        if failed_logins >= 3:
            res = SecurityDetectionEngine.evaluate_signal(
                db=db,
                detection_type="AUTH_FAILURE_BURST",
                source_device_name="SRV-NMS-01",
                evidence=[f"Observed {failed_logins} failed authentication audit events in the last {hours}h [SIMULATION]."],
                observed_count=failed_logins,
                confidence=86.0,
            )
            if res.get("detection"):
                detections.append(res["detection"])

        esc = db.query(AuditLog).filter(
            AuditLog.action == "ROLE_ESCALATION_ATTEMPT",
            AuditLog.timestamp >= cutoff,
        ).count()
        if esc >= 2:
            res = SecurityDetectionEngine.evaluate_signal(
                db=db,
                detection_type="SUSPICIOUS_LOGIN_PATTERN",
                source_device_name="SRV-NMS-01",
                evidence=[f"Observed {esc} role-escalation audit rejections in the last {hours}h [SIMULATION]."],
                observed_count=esc,
                confidence=88.0,
            )
            if res.get("detection"):
                detections.append(res["detection"])
        return detections

    @staticmethod
    def mark_false_positive(
        db: Session,
        detection_id: str,
        reason: str,
        actor: str,
    ) -> Optional[SecurityDetection]:
        det = db.query(SecurityDetection).filter(SecurityDetection.id == detection_id).first()
        if not det:
            return None
        det.status = "FALSE_POSITIVE"
        det.false_positive_reason = reason.strip()[:250]
        db.add(AuditLog(
            username=actor,
            action="SECURITY_DETECTION_FALSE_POSITIVE",
            resource_type="SECURITY_DETECTION",
            resource_id=det.id,
            details={"detection_type": det.detection_type, "reason": det.false_positive_reason},
            status="SUCCESS",
        ))
        db.commit()
        db.refresh(det)
        return det
