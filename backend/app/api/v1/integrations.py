from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.dependencies import require_admin, require_engineer, require_viewer
from app.database.session import get_db
from app.models import CredentialVault, DeviceConnectionProfile, Event, User, VirtualLabServer
from app.services.device_capabilities import DeviceCapabilityDetector
from app.services.device_connection_manager import DeviceConnectionManager
from app.services.real_device_telemetry import RealDeviceTelemetryService
from app.services.syslog_collector import SyslogCollector
from app.services.virtual_lab_manager import VirtualLabManager
from app.services.integration_validator import IntegrationValidator

router = APIRouter(prefix="/integrations", tags=["Network Integrations"])


class CredentialCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)
    secret: Optional[str] = Field(default=None, max_length=200)
    auth_protocol: Optional[str] = Field(default=None, max_length=20)
    priv_protocol: Optional[str] = Field(default=None, max_length=20)


class ProfileCreateRequest(BaseModel):
    device_name: str = Field(..., min_length=2, max_length=100)
    management_ip: str = Field(..., min_length=7, max_length=45)
    device_vendor: str = Field(default="Cisco", max_length=50)
    device_platform: str = Field(default="cisco_ios", max_length=50)
    device_model: Optional[str] = Field(default=None, max_length=80)
    os_version: Optional[str] = Field(default=None, max_length=80)
    protocol: str = Field(default="SSH", max_length=20)
    port: int = Field(default=22, ge=1, le=65535)
    credential_ref: str = Field(..., min_length=3, max_length=64)
    environment: str = Field(default="LAB", max_length=20)
    timeout_seconds: int = Field(default=10, ge=2, le=30)
    max_retries: int = Field(default=2, ge=1, le=3)
    ssh_host_key_fingerprint: Optional[str] = Field(default=None, max_length=128)


def _serialize_profile(p: DeviceConnectionProfile) -> Dict[str, Any]:
    # Never expose credentials or encrypted secrets
    return {
        "id": p.id,
        "device_id": p.device_id,
        "device_name": p.device_name,
        "management_ip": p.management_ip,
        "device_vendor": p.device_vendor,
        "device_platform": p.device_platform,
        "device_model": p.device_model,
        "os_version": p.os_version,
        "protocol": p.protocol,
        "port": p.port,
        "credential_ref": p.credential_ref,
        "environment": p.environment,
        "timeout_seconds": p.timeout_seconds,
        "max_retries": p.max_retries,
        "host_key_verified": p.host_key_verified,
        "connection_status": p.connection_status,
        "last_successful_connection": p.last_successful_connection.isoformat() if p.last_successful_connection else None,
        "last_connection_error": p.last_connection_error,
        "capabilities": p.capabilities or {},
        "is_approved": p.is_approved,
    }


@router.post("/credentials", status_code=201)
def create_credential(
    payload: CredentialCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    cred = DeviceConnectionManager.create_credential(
        db=db,
        name=payload.name,
        username=payload.username,
        password=payload.password,
        secret=payload.secret,
        auth_protocol=payload.auth_protocol,
        priv_protocol=payload.priv_protocol,
        actor=current_user.username,
    )
    return {
        "credential_ref": cred.credential_ref,
        "name": cred.name,
        "username": cred.username,
        "auth_protocol": cred.auth_protocol,
        "priv_protocol": cred.priv_protocol,
    }


@router.get("/credentials")
def list_credentials(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    creds = db.query(CredentialVault).order_by(CredentialVault.created_at.desc()).all()
    return [
        {
            "credential_ref": c.credential_ref,
            "name": c.name,
            "username": c.username,
            "auth_protocol": c.auth_protocol,
            "priv_protocol": c.priv_protocol,
            "created_by": c.created_by,
        }
        for c in creds
    ]


@router.get("/profiles")
def list_profiles(
    environment: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    q = db.query(DeviceConnectionProfile)
    if environment:
        q = q.filter(DeviceConnectionProfile.environment == environment.upper())
    total = q.count()
    items = q.order_by(DeviceConnectionProfile.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [_serialize_profile(p) for p in items]}


@router.post("/profiles", status_code=201)
def create_profile(
    payload: ProfileCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        prof = DeviceConnectionManager.create_profile(
            db=db,
            device_name=payload.device_name,
            management_ip=payload.management_ip,
            device_vendor=payload.device_vendor,
            device_platform=payload.device_platform,
            device_model=payload.device_model,
            os_version=payload.os_version,
            protocol=payload.protocol,
            port=payload.port,
            credential_ref=payload.credential_ref,
            environment=payload.environment,
            timeout_seconds=payload.timeout_seconds,
            max_retries=payload.max_retries,
            ssh_host_key_fingerprint=payload.ssh_host_key_fingerprint,
            actor=current_user.username,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _serialize_profile(prof)


@router.get("/profiles/{profile_id}/status")
def get_profile_status(
    profile_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    p = db.query(DeviceConnectionProfile).filter(DeviceConnectionProfile.id == profile_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Connection profile not found")
    return _serialize_profile(p)


@router.post("/profiles/{profile_id}/test")
def test_profile_connection(
    profile_id: str,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    p = db.query(DeviceConnectionProfile).filter(DeviceConnectionProfile.id == profile_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Connection profile not found")
    return DeviceConnectionManager.test_connection(db, p, current_user.username)


@router.post("/profiles/{profile_id}/capabilities")
def discover_capabilities(
    profile_id: str,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    p = db.query(DeviceConnectionProfile).filter(DeviceConnectionProfile.id == profile_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Connection profile not found")
    caps = DeviceCapabilityDetector.detect_capabilities(p, ssh_reachable=(p.connection_status == "CONNECTED"))
    p.capabilities = caps
    db.commit()
    return {"profile_id": p.id, "device_name": p.device_name, "capabilities": caps}


@router.get("/profiles/{profile_id}/device-info")
def get_read_only_device_info(
    profile_id: str,
    operation: str = Query(default="device_version"),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    p = db.query(DeviceConnectionProfile).filter(DeviceConnectionProfile.id == profile_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Connection profile not found")
    try:
        return DeviceConnectionManager.run_read_only_operation(db, p, operation, current_user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/profiles/{profile_id}/interfaces")
def get_read_only_interfaces(
    profile_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return get_read_only_device_info(profile_id, operation="interface_status", current_user=current_user, db=db)


@router.get("/profiles/{profile_id}/vlans")
def get_read_only_vlans(
    profile_id: str,
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return get_read_only_device_info(profile_id, operation="vlan_info", current_user=current_user, db=db)


class SyslogIngestRequest(BaseModel):
    raw_message: str = Field(..., min_length=5, max_length=2048)
    source_ip: Optional[str] = Field(default=None, max_length=45)


@router.post("/telemetry/poll/{profile_id}")
def poll_device_telemetry(
    profile_id: str,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    p = db.query(DeviceConnectionProfile).filter(DeviceConnectionProfile.id == profile_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Connection profile not found")
    return RealDeviceTelemetryService.poll_profile(db, p)


@router.get("/telemetry/health")
def get_real_telemetry_health(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return RealDeviceTelemetryService.get_polling_health(db)


@router.post("/syslog/ingest")
def ingest_syslog_message(
    payload: SyslogIngestRequest,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        return SyslogCollector.ingest_syslog(db, payload.raw_message, payload.source_ip)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/syslog/events")
def list_syslog_events(
    limit: int = Query(default=30, ge=1, le=200),
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    evs = db.query(Event).order_by(Event.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "event_code": e.event_code,
            "severity": e.severity,
            "source_name": e.source_name,
            "message": e.message,
            "source": (e.details or {}).get("source", "SIMULATION"),
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        }
        for e in evs
    ]


class LabServerCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    lab_type: str = Field(..., pattern="^(GNS3|EVE_NG)$")
    base_url: str = Field(..., min_length=8, max_length=255)
    credential_ref: Optional[str] = Field(default=None, max_length=64)


class LabSyncRequest(BaseModel):
    target_id: str = Field(..., min_length=1, max_length=200)


@router.get("/labs/servers")
def list_lab_servers(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    srvs = db.query(VirtualLabServer).order_by(VirtualLabServer.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "lab_type": s.lab_type,
            "base_url": s.base_url,
            "connection_status": s.connection_status,
            "last_sync_at": s.last_sync_at.isoformat() if s.last_sync_at else None,
            "last_error": s.last_error,
            "discovered_summary": s.discovered_summary or {},
            "environment": "LAB",
        }
        for s in srvs
    ]


@router.post("/labs/servers", status_code=201)
def register_lab_server(
    payload: LabServerCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        s = VirtualLabManager.register_server(
            db=db,
            name=payload.name,
            lab_type=payload.lab_type,
            base_url=payload.base_url,
            credential_ref=payload.credential_ref,
            actor=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": s.id, "name": s.name, "lab_type": s.lab_type, "base_url": s.base_url, "environment": "LAB"}


@router.post("/labs/servers/{server_id}/discover")
def discover_lab_server(
    server_id: str,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    srv = db.query(VirtualLabServer).filter(VirtualLabServer.id == server_id).first()
    if not srv:
        raise HTTPException(status_code=404, detail="Lab server not found")
    return VirtualLabManager.discover(db, srv)


@router.post("/labs/servers/{server_id}/sync")
def sync_lab_server(
    server_id: str,
    payload: LabSyncRequest,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    srv = db.query(VirtualLabServer).filter(VirtualLabServer.id == server_id).first()
    if not srv:
        raise HTTPException(status_code=404, detail="Lab server not found")
    try:
        return VirtualLabManager.sync_project_or_lab(db, srv, payload.target_id, current_user.username)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:200])


@router.get("/validation-report")
def get_integration_validation_report(
    current_user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return IntegrationValidator.build_validation_report(db)
