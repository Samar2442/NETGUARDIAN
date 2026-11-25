import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.models import Device, DeviceConnectionProfile, Event
from app.engines.correlation.correlation_engine import CorrelationEngine

MAX_SYSLOG_BYTES = 2048

_CISCO_SYSLOG_RE = re.compile(
    r"^(?:<\d+>)?(?:(?P<ts>[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+)?(?:(?P<host>[A-Za-z0-9._-]+):\s+)?%(?P<fac>[A-Z0-9_]+)-(?P<sev>[0-7])-(?P<mnem>[A-Z0-9_]+):\s*(?P<msg>.+)$"
)

_SYSLOG_SEV_MAP = {
    0: "CRITICAL",
    1: "CRITICAL",
    2: "CRITICAL",
    3: "HIGH",
    4: "MEDIUM",
    5: "LOW",
    6: "INFO",
    7: "INFO",
}


def sanitize_syslog_message(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Empty syslog message.")
    if len(raw.encode("utf-8", errors="ignore")) > MAX_SYSLOG_BYTES:
        raise ValueError(f"Syslog message exceeds maximum length ({MAX_SYSLOG_BYTES} bytes).")
    # Strip control characters / newlines to prevent log injection
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", raw).strip()
    return cleaned


class SyslogCollector:
    """
    Controlled Cisco-style Syslog receiver & normalizer.
    Validates message size, sanitizes content, verifies source against
    configured devices/profiles, deduplicates, and feeds CorrelationEngine.
    """

    @staticmethod
    def parse_message(raw: str) -> Dict[str, Any]:
        cleaned = sanitize_syslog_message(raw)
        m = _CISCO_SYSLOG_RE.match(cleaned)
        if not m:
            raise ValueError("Malformed Cisco syslog message format.")
        sev_num = int(m.group("sev"))
        return {
            "host": m.group("host"),
            "facility": m.group("fac"),
            "severity_level": sev_num,
            "severity": _SYSLOG_SEV_MAP.get(sev_num, "INFO"),
            "mnemonic": m.group("mnem"),
            "event_code": f"%{m.group('fac')}-{sev_num}-{m.group('mnem')}",
            "message": m.group("msg"),
        }

    @staticmethod
    def ingest_syslog(
        db: Session,
        raw_message: str,
        source_ip: Optional[str] = None,
        dedup_window_seconds: int = 60,
    ) -> Dict[str, Any]:
        parsed = SyslogCollector.parse_message(raw_message)

        # Trust only configured profiles or registered campus devices (never raw IP alone)
        profile = None
        if source_ip:
            profile = db.query(DeviceConnectionProfile).filter(
                DeviceConnectionProfile.management_ip == source_ip.strip(),
                DeviceConnectionProfile.is_approved == True,
            ).first()

        dev = None
        if profile and profile.device_id:
            dev = db.query(Device).filter(Device.id == profile.device_id).first()
        elif parsed["host"]:
            dev = db.query(Device).filter(Device.hostname == parsed["host"]).first()

        if not profile and not dev:
            raise PermissionError("Untrusted syslog source: IP/hostname does not match any authorized device.")

        source_env = profile.environment if profile else (dev.environment or "SIMULATION")
        source_name = profile.device_name if profile else dev.hostname
        source_id = dev.id if dev else profile.id

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=dedup_window_seconds)
        dup = (
            db.query(Event)
            .filter(
                Event.event_code == parsed["event_code"],
                Event.source_id == source_id,
                Event.timestamp >= cutoff,
                Event.resolved == False,
            )
            .first()
        )
        if dup:
            return {"status": "DEDUPLICATED", "event_id": dup.id, "source": source_env}

        ev = Event(
            event_type=parsed["mnemonic"],
            event_code=parsed["event_code"],
            severity=parsed["severity"],
            source_type="device",
            source_id=source_id,
            source_name=source_name,
            device_id=dev.id if dev else None,
            message=f"[{source_env}] {parsed['event_code']}: {parsed['message']}",
            details={
                "source": source_env,
                "facility": parsed["facility"],
                "trusted_profile": profile.id if profile else None,
            },
            timestamp=now,
        )
        db.add(ev)
        db.flush()

        inc = None
        if parsed["severity"] in {"CRITICAL", "HIGH"}:
            inc = CorrelationEngine.correlate_event(db, ev)

        db.commit()
        return {
            "status": "INGESTED",
            "event_id": ev.id,
            "incident_id": inc.id if inc else None,
            "source": source_env,
            "event_code": parsed["event_code"],
            "severity": parsed["severity"],
        }
