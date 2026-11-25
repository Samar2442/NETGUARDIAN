import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.models import (
    AuditLog,
    CampusService,
    Device,
    Diagnosis,
    Incident,
    IncidentActivity,
    RemediationProposal,
    SecurityDetection,
    SecurityEvidence,
    ServiceDependency,
    VLAN,
)
from app.engines.digital_twin.digital_twin_engine import DigitalTwinEngine
from app.engines.remediation.command_validator import (
    RemediationOperation,
    build_structured_commands,
)

_SECRET_PATTERNS = [
    (re.compile(r"(?i)(password|passwd|pwd|secret|api_key|apikey|token)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "[JWT_REDACTED]"),
]


def scrub_secrets(text: str) -> str:
    cleaned = text.strip()
    for pat, repl in _SECRET_PATTERNS:
        cleaned = pat.sub(repl, cleaned)
    return cleaned[:2000]


def compute_evidence_hash(
    incident_id: str,
    source_detection_id: Optional[str],
    source_device_name: Optional[str],
    evidence_type: str,
    timestamp_iso: str,
    description: str,
    collection_method: str,
    data_classification: str,
) -> str:
    canonical = "|".join([
        incident_id,
        source_detection_id or "",
        source_device_name or "",
        evidence_type,
        timestamp_iso,
        description,
        collection_method,
        data_classification,
    ])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SecurityIncidentService:
    """
    Security Incident Response & Evidence Management integrated with
    existing Incident, RCA, Digital Twin, Remediation, and AuditLog systems.
    """

    @staticmethod
    def create_security_incident(
        db: Session,
        title: str,
        description: str,
        severity: str,
        source_device_name: Optional[str],
        vlan_ids: List[int],
        actor: str,
    ) -> Incident:
        now = datetime.now(timezone.utc)
        dev = None
        if source_device_name:
            dev = db.query(Device).filter(
                (Device.hostname == source_device_name) | (Device.id == source_device_name)
            ).first()

        # Resolve affected CampusServices via ServiceDependency (device + VLANs)
        affected_services: List[str] = []
        if db.query(CampusService).count() == 0:
            from app.services.service_intelligence import ServiceIntelligenceEngine
            ServiceIntelligenceEngine.seed_campus_services(db)
        svc_ids = set()
        if dev:
            for d in db.query(ServiceDependency).filter(
                ServiceDependency.resource_type == "device",
                (ServiceDependency.resource_id == dev.id) | (ServiceDependency.resource_name == dev.hostname),
            ).all():
                svc_ids.add(d.service_id)
        if vlan_ids:
            vlan_db_ids = [v.id for v in db.query(VLAN).filter(VLAN.vlan_id.in_(vlan_ids)).all()]
            if vlan_db_ids:
                for d in db.query(ServiceDependency).filter(
                    ServiceDependency.resource_type == "vlan",
                    ServiceDependency.resource_id.in_(vlan_db_ids),
                ).all():
                    svc_ids.add(d.service_id)
        if svc_ids:
            affected_services = [
                s.name for s in db.query(CampusService).filter(CampusService.id.in_(list(svc_ids))).all()
            ]

        sev_upper = severity.upper()
        priority = "P1" if sev_upper == "CRITICAL" else ("P2" if sev_upper == "HIGH" else "P3")
        inc_num = f"SEC-{now.strftime('%Y%m%d')}-{db.query(Incident).count() + 101}"

        inc = Incident(
            incident_number=inc_num,
            title=scrub_secrets(title)[:250],
            description=scrub_secrets(description),
            severity=severity.lower(),
            security_severity=sev_upper,
            priority=priority,
            status="DETECTED",
            lifecycle_state="NEW",
            incident_category="SECURITY",
            source_device_id=dev.id if dev else None,
            source_device_name=dev.hostname if dev else source_device_name,
            affected_device_ids=[dev.id] if dev else [],
            affected_vlan_ids=vlan_ids,
            affected_services=affected_services,
            created_at=now,
            updated_at=now,
            source="SIMULATION",
        )
        db.add(inc)
        db.flush()

        db.add(IncidentActivity(
            incident_id=inc.id,
            actor=actor,
            action="SECURITY_INCIDENT_CREATED",
            details={"security_severity": sev_upper, "affected_services": affected_services},
            timestamp=now,
        ))
        db.add(AuditLog(
            username=actor,
            action="SECURITY_INCIDENT_CREATED",
            resource_type="INCIDENT",
            resource_id=inc.id,
            details={"incident_number": inc_num, "severity": sev_upper},
            status="SUCCESS",
        ))
        db.commit()
        db.refresh(inc)
        return inc

    @staticmethod
    def add_evidence(
        db: Session,
        incident_id: str,
        evidence_type: str,
        description: str,
        source_detection_id: Optional[str],
        source_device_name: Optional[str],
        collection_method: str,
        actor: str,
    ) -> Optional[SecurityEvidence]:
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            return None

        dev = None
        if source_device_name:
            dev = db.query(Device).filter(
                (Device.hostname == source_device_name) | (Device.id == source_device_name)
            ).first()

        now = datetime.now(timezone.utc).replace(microsecond=0)
        ts_iso = now.isoformat()
        clean_desc = scrub_secrets(description)
        data_class = "SIMULATION"
        dev_name = dev.hostname if dev else source_device_name

        digest = compute_evidence_hash(
            incident_id=inc.id,
            source_detection_id=source_detection_id,
            source_device_name=dev_name,
            evidence_type=evidence_type,
            timestamp_iso=ts_iso,
            description=clean_desc,
            collection_method=collection_method,
            data_classification=data_class,
        )

        ev = SecurityEvidence(
            incident_id=inc.id,
            source_detection_id=source_detection_id,
            source_device_id=dev.id if dev else None,
            source_device_name=dev_name,
            evidence_type=evidence_type,
            timestamp=now,
            description=clean_desc,
            integrity_hash=digest,
            collection_method=collection_method,
            data_classification=data_class,
            collected_by=actor,
        )
        db.add(ev)
        db.flush()

        db.add(IncidentActivity(
            incident_id=inc.id,
            actor=actor,
            action="SECURITY_EVIDENCE_ADDED",
            details={"evidence_id": ev.id, "evidence_type": evidence_type, "integrity_hash": digest[:16]},
            timestamp=now,
        ))
        db.add(AuditLog(
            username=actor,
            action="SECURITY_EVIDENCE_COLLECTED",
            resource_type="SECURITY_EVIDENCE",
            resource_id=ev.id,
            details={"incident_id": inc.id, "evidence_type": evidence_type},
            status="SUCCESS",
        ))
        db.commit()
        db.refresh(ev)
        return ev

    @staticmethod
    def list_evidence(db: Session, incident_id: str) -> Optional[List[Dict[str, Any]]]:
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            return None
        rows = (
            db.query(SecurityEvidence)
            .filter(SecurityEvidence.incident_id == incident_id)
            .order_by(SecurityEvidence.timestamp.asc())
            .all()
        )
        results = []
        for r in rows:
            ts = r.timestamp.replace(tzinfo=timezone.utc).isoformat() if r.timestamp and r.timestamp.tzinfo is None else (
                r.timestamp.isoformat() if r.timestamp else ""
            )
            expected_hash = compute_evidence_hash(
                incident_id=r.incident_id,
                source_detection_id=r.source_detection_id,
                source_device_name=r.source_device_name,
                evidence_type=r.evidence_type,
                timestamp_iso=ts,
                description=r.description,
                collection_method=r.collection_method,
                data_classification=r.data_classification,
            )
            results.append({
                "id": r.id,
                "incident_id": r.incident_id,
                "source_detection_id": r.source_detection_id,
                "source_device_id": r.source_device_id,
                "source_device_name": r.source_device_name,
                "evidence_type": r.evidence_type,
                "timestamp": ts,
                "description": r.description,
                "integrity_hash": r.integrity_hash,
                "integrity_valid": r.integrity_hash == expected_hash,
                "collection_method": r.collection_method,
                "data_classification": r.data_classification,
                "collected_by": r.collected_by,
            })
        return results

    @staticmethod
    def get_response_recommendations(db: Session, incident_id: str) -> Optional[Dict[str, Any]]:
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            return None

        dets = db.query(SecurityDetection).filter(SecurityDetection.incident_id == inc.id).all()
        recs: List[str] = [
            "Request network engineer investigation and preserve immutable evidence.",
        ]
        for d in dets:
            if d.detection_type == "ROGUE_DHCP":
                recs.append("Investigate suspicious DHCP activity and verify DHCP snooping trust state.")
            elif d.detection_type in ("PORT_SECURITY_VIOLATION", "UNAUTHORIZED_DEVICE", "MAC_ADDRESS_CHANGE"):
                recs.append("Review affected endpoint and verify switch port-security configuration.")
            elif d.detection_type == "UNEXPECTED_VLAN_CHANGE":
                recs.append("Review VLAN membership and trunk allowed-VLAN policy.")
            elif d.detection_type == "SUSPICIOUS_MGMT_ACCESS":
                recs.append("Restrict management-plane exposure via VTY access-class and SSH-only transport.")
            elif d.detection_type == "ARP_ANOMALY":
                recs.append("Inspect ARP bindings and consider Dynamic ARP Inspection (DAI) on access VLANs.")
        recs.append("Prepare an approved remediation proposal (requires admin approval; no automatic execution).")

        twin_impact = None
        if inc.source_device_name:
            twin_impact = DigitalTwinEngine.simulate_failure(
                db, "switch_failure", inc.source_device_name
            )
        diag = db.query(Diagnosis).filter(Diagnosis.incident_id == inc.id).first()

        return {
            "incident_id": inc.id,
            "incident_number": inc.incident_number,
            "recommendations": list(dict.fromkeys(recs)),
            "digital_twin_impact": twin_impact,
            "rca_summary": {
                "root_cause": diag.root_cause,
                "status": diag.status,
                "confidence": diag.confidence,
            } if diag else None,
        }

    @staticmethod
    def propose_remediation(
        db: Session,
        incident_id: str,
        device_id: str,
        operation: str,
        target_interface: str,
        parameters: Dict[str, Any],
        actor: str,
    ) -> RemediationProposal:
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            raise ValueError("Incident not found")
        dev = db.query(Device).filter((Device.id == device_id) | (Device.hostname == device_id)).first()
        if not dev:
            raise ValueError("Target device not found")

        proposed_cmds, rollback_cmds, _, norm_params = build_structured_commands(
            operation=operation,
            interface=target_interface,
            parameters=parameters or {},
        )

        prop = RemediationProposal(
            incident_id=inc.id,
            device_id=dev.id,
            title=f"Security Remediation ({operation}) on {dev.hostname} {target_interface}",
            target_interface=target_interface,
            operation=operation,
            parameters=norm_params,
            execution_mode="SIMULATION",
            proposed_commands=proposed_cmds,
            rollback_commands=rollback_cmds,
            risk_level="low",
            expected_result=f"Controlled simulation remediation {operation} prepared for admin approval.",
            status="PENDING_APPROVAL",
        )
        db.add(prop)
        db.flush()

        db.add(IncidentActivity(
            incident_id=inc.id,
            actor=actor,
            action="SECURITY_REMEDIATION_PROPOSED",
            details={"proposal_id": prop.id, "operation": operation, "device": dev.hostname},
            timestamp=datetime.now(timezone.utc),
        ))
        db.add(AuditLog(
            username=actor,
            action="SECURITY_REMEDIATION_PROPOSED",
            resource_type="REMEDIATION",
            resource_id=prop.id,
            details={"incident_id": inc.id, "operation": operation},
            status="SUCCESS",
        ))
        db.commit()
        db.refresh(prop)
        return prop
