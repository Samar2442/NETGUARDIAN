from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.dependencies import require_admin, require_engineer, require_viewer
from app.database.session import get_db
from app.models import AuditLog, Device, Incident, SecurityDetection, SecurityDetectionRule, User
from app.services.security_detection_engine import SecurityDetectionEngine, VALID_SEVERITIES
from app.services.network_security_intelligence import NetworkSecurityIntelligenceService
from app.services.security_incident_service import SecurityIncidentService

router = APIRouter(prefix="/security", tags=["Security Operations"])


class DetectionEvaluateRequest(BaseModel):
    detection_type: str = Field(..., min_length=2, max_length=50)
    source_device_name: Optional[str] = Field(default=None, max_length=100)
    related_endpoint: Optional[str] = Field(default=None, max_length=100)
    vlan_id: Optional[int] = Field(default=None, ge=1, le=4094)
    evidence: List[str] = Field(default_factory=list, max_length=20)
    observed_count: int = Field(default=1, ge=1, le=1000)
    confidence: float = Field(default=82.0, ge=0.0, le=100.0)
    severity_override: Optional[str] = None


class FalsePositiveRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=250)


class RuleUpdateRequest(BaseModel):
    threshold: Optional[int] = Field(default=None, ge=1, le=100)
    window_seconds: Optional[int] = Field(default=None, ge=30, le=86400)
    cooldown_seconds: Optional[int] = Field(default=None, ge=10, le=86400)
    enabled: Optional[bool] = None
    severity: Optional[str] = None


def _serialize_detection(d: SecurityDetection) -> Dict[str, Any]:
    return {
        "id": d.id,
        "detection_type": d.detection_type,
        "rule_id": d.rule_id,
        "severity": d.severity,
        "confidence": d.confidence,
        "source_device_id": d.source_device_id,
        "source_device_name": d.source_device_name,
        "related_endpoint": d.related_endpoint,
        "vlan_id": d.vlan_id,
        "department": d.department,
        "timestamp": d.timestamp.isoformat() if d.timestamp else None,
        "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None,
        "occurrence_count": d.occurrence_count,
        "supporting_evidence": d.supporting_evidence or [],
        "status": d.status,
        "false_positive_reason": d.false_positive_reason,
        "data_source": d.data_source,
        "classification": d.classification,
        "event_id": d.event_id,
        "incident_id": d.incident_id,
    }


@router.get("/detections")
def list_security_detections(
    severity: Optional[str] = Query(default=None),
    detection_type: Optional[str] = Query(default=None),
    device: Optional[str] = Query(default=None),
    vlan_id: Optional[int] = Query(default=None, ge=1, le=4094),
    department: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    SecurityDetectionEngine.seed_rules(db)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = db.query(SecurityDetection).filter(SecurityDetection.timestamp >= cutoff)
    if severity:
        q = q.filter(SecurityDetection.severity == severity.upper())
    if detection_type:
        q = q.filter(SecurityDetection.detection_type == detection_type)
    if device:
        q = q.filter(SecurityDetection.source_device_name.ilike(f"%{device.strip()}%"))
    if vlan_id:
        q = q.filter(SecurityDetection.vlan_id == vlan_id)
    if department:
        q = q.filter(SecurityDetection.department == department)
    if status:
        q = q.filter(SecurityDetection.status == status.upper())

    total = q.count()
    items = q.order_by(SecurityDetection.timestamp.desc()).offset(offset).limit(limit).all()
    return {
        "data_source": "SIMULATION",
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_serialize_detection(d) for d in items],
    }


@router.post("/detections/evaluate")
def evaluate_security_signal(
    payload: DetectionEvaluateRequest,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    res = SecurityDetectionEngine.evaluate_signal(
        db=db,
        detection_type=payload.detection_type,
        source_device_name=payload.source_device_name,
        related_endpoint=payload.related_endpoint,
        vlan_id=payload.vlan_id,
        evidence=payload.evidence,
        observed_count=payload.observed_count,
        confidence=payload.confidence,
        severity_override=payload.severity_override,
    )
    if res.get("status") == "UNKNOWN_RULE":
        raise HTTPException(status_code=400, detail="Unknown detection rule")
    det = res.get("detection")
    db.add(AuditLog(
        username=current_user.username,
        action="SECURITY_DETECTION_EVALUATED",
        resource_type="SECURITY_DETECTION",
        resource_id=det.id if det else payload.detection_type,
        details={"status": res.get("status"), "detection_type": payload.detection_type},
        status="SUCCESS",
    ))
    db.commit()
    return {
        "status": res["status"],
        "incident_id": res.get("incident_id"),
        "detection": _serialize_detection(det) if det else None,
    }


@router.post("/detections/{detection_id}/false-positive")
def mark_detection_false_positive(
    detection_id: str,
    payload: FalsePositiveRequest,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    det = SecurityDetectionEngine.mark_false_positive(db, detection_id, payload.reason, current_user.username)
    if not det:
        raise HTTPException(status_code=404, detail="Security detection not found")
    return _serialize_detection(det)


@router.get("/rules")
def list_security_rules(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    SecurityDetectionEngine.seed_rules(db)
    rules = db.query(SecurityDetectionRule).order_by(SecurityDetectionRule.rule_id.asc()).all()
    return [
        {
            "id": r.id,
            "rule_id": r.rule_id,
            "name": r.name,
            "detection_type": r.detection_type,
            "severity": r.severity,
            "threshold": r.threshold,
            "window_seconds": r.window_seconds,
            "cooldown_seconds": r.cooldown_seconds,
            "enabled": r.enabled,
            "description": r.description,
        }
        for r in rules
    ]


@router.patch("/rules/{rule_id}")
def update_security_rule(
    rule_id: str,
    payload: RuleUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    SecurityDetectionEngine.seed_rules(db)
    rule = db.query(SecurityDetectionRule).filter(SecurityDetectionRule.rule_id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Security rule not found")
    if payload.threshold is not None:
        rule.threshold = payload.threshold
    if payload.window_seconds is not None:
        rule.window_seconds = payload.window_seconds
    if payload.cooldown_seconds is not None:
        rule.cooldown_seconds = payload.cooldown_seconds
    if payload.enabled is not None:
        rule.enabled = payload.enabled
    if payload.severity is not None:
        sev = payload.severity.upper()
        if sev not in VALID_SEVERITIES:
            raise HTTPException(status_code=400, detail="Invalid severity")
        rule.severity = sev
    db.add(AuditLog(
        username=current_user.username,
        action="SECURITY_RULE_UPDATED",
        resource_type="SECURITY_RULE",
        resource_id=rule.rule_id,
        details={"threshold": rule.threshold, "enabled": rule.enabled, "severity": rule.severity},
        status="SUCCESS",
    ))
    db.commit()
    db.refresh(rule)
    return {
        "rule_id": rule.rule_id,
        "name": rule.name,
        "severity": rule.severity,
        "threshold": rule.threshold,
        "window_seconds": rule.window_seconds,
        "cooldown_seconds": rule.cooldown_seconds,
        "enabled": rule.enabled,
    }


@router.get("/overview")
def get_security_overview(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return NetworkSecurityIntelligenceService.get_security_overview(db)


@router.get("/assessments/devices")
def get_device_security_assessments(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return NetworkSecurityIntelligenceService.assess_devices(db, limit=limit, offset=offset)


@router.get("/assessments/devices/{device_id}")
def get_single_device_security_assessment(
    device_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    dev = db.query(Device).filter((Device.id == device_id) | (Device.hostname == device_id)).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    return NetworkSecurityIntelligenceService.assess_device_baseline(db, dev)


@router.get("/assessments/vlans")
def get_vlan_segmentation_assessment(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return NetworkSecurityIntelligenceService.assess_vlan_segmentation(db)


@router.get("/assessments/acls")
def get_acl_assessment(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return NetworkSecurityIntelligenceService.assess_acls(db)


@router.get("/assessments/firewall")
def get_firewall_assessment(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return NetworkSecurityIntelligenceService.assess_firewall(db)


@router.get("/assessments/departments")
def get_department_security_posture(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return NetworkSecurityIntelligenceService.assess_departments(db)


@router.get("/recommendations")
def get_security_recommendations(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ov = NetworkSecurityIntelligenceService.get_security_overview(db)
    return {
        "data_source": "SIMULATION",
        "recommendations": ov["recommendations"],
        "assessment_timestamp": ov["assessment_timestamp"],
    }


class SecurityIncidentCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=250)
    description: str = Field(..., min_length=5, max_length=2000)
    severity: str = Field(default="HIGH")
    source_device_name: Optional[str] = Field(default=None, max_length=100)
    vlan_ids: List[int] = Field(default_factory=list, max_length=20)


class EvidenceCreateRequest(BaseModel):
    evidence_type: str = Field(..., min_length=2, max_length=50)
    description: str = Field(..., min_length=3, max_length=2000)
    source_detection_id: Optional[str] = None
    source_device_name: Optional[str] = Field(default=None, max_length=100)
    collection_method: str = Field(default="AUTOMATED_SIMULATION", max_length=50)


class SecurityRemediationProposeRequest(BaseModel):
    device_id: str
    operation: str
    target_interface: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


@router.get("/incidents")
def list_security_incidents(
    severity: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    q = db.query(Incident).filter(Incident.incident_category == "SECURITY")
    if severity:
        q = q.filter(Incident.security_severity == severity.upper())
    if status:
        q = q.filter(Incident.lifecycle_state == status.upper())
    total = q.count()
    items = q.order_by(Incident.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": i.id,
                "incident_number": i.incident_number,
                "title": i.title,
                "description": i.description,
                "severity": i.severity,
                "security_severity": i.security_severity or i.severity.upper(),
                "priority": i.priority,
                "status": i.status,
                "lifecycle_state": i.lifecycle_state,
                "source_device_name": i.source_device_name,
                "affected_vlan_ids": i.affected_vlan_ids or [],
                "affected_services": i.affected_services or [],
                "assigned_to": i.assigned_to,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ],
    }


@router.post("/incidents", status_code=201)
def create_security_incident(
    payload: SecurityIncidentCreateRequest,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    sev = payload.severity.upper()
    if sev not in VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail="Invalid severity")
    inc = SecurityIncidentService.create_security_incident(
        db=db,
        title=payload.title,
        description=payload.description,
        severity=sev,
        source_device_name=payload.source_device_name,
        vlan_ids=payload.vlan_ids,
        actor=current_user.username,
    )
    return {
        "id": inc.id,
        "incident_number": inc.incident_number,
        "title": inc.title,
        "security_severity": inc.security_severity,
        "lifecycle_state": inc.lifecycle_state,
        "affected_services": inc.affected_services or [],
    }


@router.get("/incidents/{incident_id}/evidence")
def get_incident_evidence(
    incident_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    res = SecurityIncidentService.list_evidence(db, incident_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return res


@router.post("/incidents/{incident_id}/evidence", status_code=201)
def add_incident_evidence(
    incident_id: str,
    payload: EvidenceCreateRequest,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    ev = SecurityIncidentService.add_evidence(
        db=db,
        incident_id=incident_id,
        evidence_type=payload.evidence_type,
        description=payload.description,
        source_detection_id=payload.source_detection_id,
        source_device_name=payload.source_device_name,
        collection_method=payload.collection_method,
        actor=current_user.username,
    )
    if not ev:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {
        "id": ev.id,
        "incident_id": ev.incident_id,
        "evidence_type": ev.evidence_type,
        "description": ev.description,
        "integrity_hash": ev.integrity_hash,
        "data_classification": ev.data_classification,
        "collected_by": ev.collected_by,
    }


@router.get("/incidents/{incident_id}/recommendations")
def get_incident_recommendations(
    incident_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    res = SecurityIncidentService.get_response_recommendations(db, incident_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return res


@router.post("/incidents/{incident_id}/propose-remediation", status_code=201)
def propose_security_remediation(
    incident_id: str,
    payload: SecurityRemediationProposeRequest,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        prop = SecurityIncidentService.propose_remediation(
            db=db,
            incident_id=incident_id,
            device_id=payload.device_id,
            operation=payload.operation,
            target_interface=payload.target_interface,
            parameters=payload.parameters,
            actor=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "proposal_id": prop.id,
        "incident_id": prop.incident_id,
        "status": prop.status,
        "execution_mode": prop.execution_mode,
        "proposed_commands": prop.proposed_commands,
    }
