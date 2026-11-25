import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import (
    AuditLog,
    Incident,
    IncidentActivity,
    IncidentEscalation,
    IncidentNote,
    User,
)

VALID_LIFECYCLE_STATES = {
    "NEW",
    "ACKNOWLEDGED",
    "IN_PROGRESS",
    "MITIGATED",
    "RESOLVED",
    "CLOSED",
}

VALID_TRANSITIONS: Dict[str, set[str]] = {
    "NEW": {"ACKNOWLEDGED", "IN_PROGRESS", "RESOLVED"},
    "ACKNOWLEDGED": {"IN_PROGRESS", "MITIGATED", "RESOLVED"},
    "IN_PROGRESS": {"MITIGATED", "RESOLVED"},
    "MITIGATED": {"RESOLVED", "IN_PROGRESS"},
    "RESOLVED": {"CLOSED", "IN_PROGRESS"},
    "CLOSED": set(),
}

VALID_PRIORITIES = {"P1", "P2", "P3", "P4"}

_STATE_TO_LEGACY_STATUS = {
    "NEW": "DETECTED",
    "ACKNOWLEDGED": "ACKNOWLEDGED",
    "IN_PROGRESS": "INVESTIGATING",
    "MITIGATED": "MITIGATED",
    "RESOLVED": "RESOLVED",
    "CLOSED": "CLOSED",
}


class IncidentLifecycleError(ValueError):
    pass


class IncidentLifecycleService:
    """
    Enterprise NOC Incident Lifecycle, Assignment, Notes, Timeline, and Escalation Service.
    """

    @staticmethod
    def record_activity(
        db: Session,
        incident_id: str,
        actor: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> IncidentActivity:
        act = IncidentActivity(
            incident_id=incident_id,
            actor=actor,
            action=action,
            details=details or {},
            timestamp=datetime.now(timezone.utc),
        )
        db.add(act)
        return act

    @staticmethod
    def assign_incident(
        db: Session,
        incident_id: str,
        assignee_username: str,
        actor: str,
        priority: Optional[str] = None,
    ) -> Incident:
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            raise IncidentLifecycleError("Incident not found.")

        target_user = (
            db.query(User)
            .filter(User.username == assignee_username, User.is_active == True)
            .first()
        )
        if not target_user or target_user.role not in {"admin", "network_engineer"}:
            raise IncidentLifecycleError(
                f"Assignee '{assignee_username}' must be an active application user with admin or network_engineer role."
            )

        now = datetime.now(timezone.utc)
        old_assignee = inc.assigned_to
        inc.assigned_to = target_user.username
        inc.assigned_at = now
        inc.updated_at = now

        IncidentLifecycleService.record_activity(
            db,
            inc.id,
            actor,
            "INCIDENT_ASSIGNED",
            {"previous_assignee": old_assignee, "assigned_to": target_user.username},
        )

        if priority:
            prio = priority.strip().upper()
            if prio not in VALID_PRIORITIES:
                raise IncidentLifecycleError(f"Priority must be one of {sorted(VALID_PRIORITIES)}.")
            old_prio = inc.priority
            inc.priority = prio
            IncidentLifecycleService.record_activity(
                db, inc.id, actor, "PRIORITY_CHANGED", {"from": old_prio, "to": prio}
            )

        db.add(AuditLog(
            username=actor,
            action="INCIDENT_ASSIGNED",
            resource_type="INCIDENT",
            resource_id=inc.id,
            details={"assigned_to": target_user.username, "priority": inc.priority},
            status="SUCCESS",
        ))
        db.commit()
        db.refresh(inc)
        return inc

    @staticmethod
    def transition_incident(
        db: Session,
        incident_id: str,
        target_state: str,
        actor: str,
        reason: Optional[str] = None,
    ) -> Incident:
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            raise IncidentLifecycleError("Incident not found.")

        nxt = (target_state or "").strip().upper()
        if nxt not in VALID_LIFECYCLE_STATES:
            raise IncidentLifecycleError(f"Invalid lifecycle state '{target_state}'.")

        cur = (inc.lifecycle_state or "NEW").upper()
        allowed = VALID_TRANSITIONS.get(cur, set())
        if nxt not in allowed:
            raise IncidentLifecycleError(
                f"Invalid state transition from '{cur}' to '{nxt}'. Allowed: {sorted(allowed)}."
            )

        now = datetime.now(timezone.utc)
        inc.lifecycle_state = nxt
        inc.status = _STATE_TO_LEGACY_STATUS.get(nxt, nxt)
        inc.updated_at = now

        if nxt == "ACKNOWLEDGED":
            inc.acknowledged_at = now
            inc.acknowledged_by = actor
        elif nxt == "RESOLVED":
            inc.resolved_at = now
        elif nxt == "CLOSED":
            inc.closed_at = now

        IncidentLifecycleService.record_activity(
            db,
            inc.id,
            actor,
            f"STATE_TRANSITION_{nxt}",
            {"from": cur, "to": nxt, "reason": (reason or "")[:200]},
        )
        db.add(AuditLog(
            username=actor,
            action="INCIDENT_STATE_TRANSITION",
            resource_type="INCIDENT",
            resource_id=inc.id,
            details={"from": cur, "to": nxt},
            status="SUCCESS",
        ))
        db.commit()
        db.refresh(inc)
        return inc

    @staticmethod
    def add_note(
        db: Session,
        incident_id: str,
        author: str,
        content: str,
    ) -> IncidentNote:
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            raise IncidentLifecycleError("Incident not found.")

        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", (content or "")).strip()
        if not cleaned:
            raise IncidentLifecycleError("Investigation note cannot be empty.")
        if len(cleaned) > 2000:
            raise IncidentLifecycleError("Investigation note exceeds 2000 character limit.")

        note = IncidentNote(
            incident_id=inc.id,
            author=author,
            content=cleaned,
            created_at=datetime.now(timezone.utc),
        )
        db.add(note)
        IncidentLifecycleService.record_activity(
            db,
            inc.id,
            author,
            "INVESTIGATION_NOTE_ADDED",
            {"note_preview": cleaned[:80]},
        )
        db.add(AuditLog(
            username=author,
            action="INCIDENT_NOTE_ADDED",
            resource_type="INCIDENT",
            resource_id=inc.id,
            details={"length": len(cleaned)},
            status="SUCCESS",
        ))
        db.commit()
        db.refresh(note)
        return note

    @staticmethod
    def evaluate_escalations(db: Session, now: Optional[datetime] = None) -> List[IncidentEscalation]:
        """
        Evaluate open incidents against configurable escalation SLA timers.
        Prevents duplicate escalation records for the same (incident_id, escalation_level).
        """
        current_time = now or datetime.now(timezone.utc)
        open_incs = db.query(Incident).filter(
            Incident.lifecycle_state.in_(["NEW", "ACKNOWLEDGED", "IN_PROGRESS"])
        ).all()

        created_escalations: List[IncidentEscalation] = []
        for inc in open_incs:
            sev = (inc.severity or "medium").upper()
            if sev == "CRITICAL":
                threshold_min = settings.ESCALATION_CRITICAL_MINUTES
            elif sev in {"HIGH", "MAJOR"}:
                threshold_min = settings.ESCALATION_MAJOR_MINUTES
            else:
                threshold_min = settings.ESCALATION_MINOR_MINUTES

            created_at = inc.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            age_minutes = (current_time - created_at).total_seconds() / 60.0
            if age_minutes < threshold_min:
                continue

            target_level = 1
            existing = db.query(IncidentEscalation).filter(
                IncidentEscalation.incident_id == inc.id,
                IncidentEscalation.escalation_level == target_level,
            ).first()
            if existing:
                continue

            esc = IncidentEscalation(
                incident_id=inc.id,
                escalation_level=target_level,
                severity=sev,
                reason=f"Incident unmitigated for {int(age_minutes)}m (policy threshold {threshold_min}m)",
                escalated_to="admin",
                escalated_at=current_time,
            )
            inc.escalation_level = target_level
            inc.escalated_at = current_time
            db.add(esc)
            IncidentLifecycleService.record_activity(
                db,
                inc.id,
                "system-escalation",
                "INCIDENT_ESCALATED",
                {"level": target_level, "threshold_minutes": threshold_min},
            )
            created_escalations.append(esc)

        if created_escalations:
            db.commit()
        return created_escalations
