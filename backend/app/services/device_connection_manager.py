import base64
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models import AuditLog, CredentialVault, Device, DeviceConnectionProfile
from app.services.device_capabilities import DeviceCapabilityDetector
from app.services.network_connector import validate_approved_destination
from app.services.ssh_connector import SSHConnector


def _get_fernet() -> Fernet:
    raw = (settings.INTEGRATION_ENCRYPTION_KEY or settings.SECRET_KEY or "netguardian-ephemeral-test-key").encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def _redact_error(msg: str, secrets: List[str]) -> str:
    cleaned = str(msg)
    for s in secrets:
        if s:
            cleaned = cleaned.replace(s, "[REDACTED]")
    return cleaned[:250]


class DeviceConnectionManager:
    """
    Manages encrypted CredentialVault entries, approved DeviceConnectionProfiles,
    SSH host-key verification, and strict read-only Cisco operations.
    """

    @staticmethod
    def create_credential(
        db: Session,
        name: str,
        username: str,
        password: str,
        secret: Optional[str],
        auth_protocol: Optional[str],
        priv_protocol: Optional[str],
        actor: str,
    ) -> CredentialVault:
        ref = f"cred-{uuid.uuid4().hex[:12]}"
        cred = CredentialVault(
            credential_ref=ref,
            name=name.strip()[:100],
            username=username.strip()[:100],
            encrypted_password=encrypt_secret(password),
            encrypted_secret=encrypt_secret(secret) if secret else None,
            auth_protocol=auth_protocol,
            priv_protocol=priv_protocol,
            created_by=actor,
        )
        db.add(cred)
        db.add(AuditLog(
            username=actor,
            action="CREDENTIAL_CREATED",
            resource_type="CREDENTIAL_VAULT",
            resource_id=ref,
            details={"name": cred.name, "auth_protocol": auth_protocol},
            status="SUCCESS",
        ))
        db.commit()
        db.refresh(cred)
        return cred

    @staticmethod
    def create_profile(
        db: Session,
        device_name: str,
        management_ip: str,
        device_vendor: str,
        device_platform: str,
        device_model: Optional[str],
        os_version: Optional[str],
        protocol: str,
        port: int,
        credential_ref: str,
        environment: str,
        timeout_seconds: int,
        max_retries: int,
        ssh_host_key_fingerprint: Optional[str],
        actor: str,
    ) -> DeviceConnectionProfile:
        env_upper = environment.upper()
        ip_valid = validate_approved_destination(management_ip, env_upper)

        cred = db.query(CredentialVault).filter(CredentialVault.credential_ref == credential_ref).first()
        if not cred:
            raise ValueError(f"Credential reference '{credential_ref}' not found.")

        dev = db.query(Device).filter(Device.hostname == device_name).first()
        proto_upper = protocol.upper()
        if proto_upper not in {"SSH", "SNMPV3", "NETCONF", "RESTCONF"}:
            raise ValueError(f"Unsupported protocol '{protocol}'.")

        profile = DeviceConnectionProfile(
            device_id=dev.id if dev else None,
            device_name=device_name.strip()[:100],
            management_ip=ip_valid,
            device_vendor=device_vendor.strip()[:50],
            device_platform=device_platform.strip()[:50],
            device_model=device_model,
            os_version=os_version,
            protocol=proto_upper,
            port=port,
            credential_ref=credential_ref,
            environment=env_upper,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            ssh_host_key_fingerprint=ssh_host_key_fingerprint,
            host_key_verified=bool(ssh_host_key_fingerprint),
            connection_status="DISCONNECTED",
            is_approved=True,
        )
        profile.capabilities = DeviceCapabilityDetector.detect_capabilities(profile, ssh_reachable=False)
        db.add(profile)
        db.add(AuditLog(
            username=actor,
            action="CONNECTION_PROFILE_CREATED",
            resource_type="DEVICE_CONNECTION",
            resource_id=device_name,
            details={"ip": ip_valid, "protocol": proto_upper, "environment": env_upper},
            status="SUCCESS",
        ))
        db.commit()
        db.refresh(profile)
        return profile

    @staticmethod
    def _build_ssh_connector(db: Session, profile: DeviceConnectionProfile) -> tuple:
        validate_approved_destination(profile.management_ip, profile.environment)
        if not profile.is_approved:
            raise PermissionError("Device connection profile is not approved.")
        cred = db.query(CredentialVault).filter(CredentialVault.credential_ref == profile.credential_ref).first()
        if not cred:
            raise ValueError("Credential reference missing from vault.")
        password = decrypt_secret(cred.encrypted_password)
        connector = SSHConnector(
            host=profile.management_ip,
            port=profile.port,
            username=cred.username,
            password=password,
            expected_fingerprint=profile.ssh_host_key_fingerprint,
            timeout_seconds=profile.timeout_seconds,
            max_retries=profile.max_retries,
        )
        return connector, [password]

    @staticmethod
    def test_connection(db: Session, profile: DeviceConnectionProfile, actor: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        secrets_to_redact: List[str] = []
        try:
            if profile.protocol != "SSH":
                caps = DeviceCapabilityDetector.detect_capabilities(profile, ssh_reachable=False)
                if not caps.get(profile.protocol, {}).get("supported", False):
                    profile.connection_status = "UNSUPPORTED"
                    profile.last_connection_error = f"Protocol {profile.protocol} is not supported on {profile.device_platform}."
                    db.commit()
                    return {"connected": False, "status": "UNSUPPORTED", "detail": profile.last_connection_error}

            connector, secrets_to_redact = DeviceConnectionManager._build_ssh_connector(db, profile)
            res = connector.test_connection()
            profile.connection_status = "CONNECTED"
            profile.host_key_verified = True
            profile.last_successful_connection = now
            profile.last_connection_error = None
            profile.capabilities = DeviceCapabilityDetector.detect_capabilities(profile, ssh_reachable=True)
            db.add(AuditLog(
                username=actor,
                action="DEVICE_CONNECTION_TEST",
                resource_type="DEVICE_CONNECTION",
                resource_id=profile.id,
                details={"device": profile.device_name, "environment": profile.environment, "result": "CONNECTED"},
                status="SUCCESS",
            ))
            db.commit()
            return {"connected": True, "status": "CONNECTED", "host_key_verified": True, "capabilities": profile.capabilities}
        except Exception as exc:
            err = _redact_error(str(exc), secrets_to_redact)
            profile.connection_status = "ERROR"
            profile.last_connection_error = err
            db.add(AuditLog(
                username=actor,
                action="DEVICE_CONNECTION_TEST",
                resource_type="DEVICE_CONNECTION",
                resource_id=profile.id,
                details={"device": profile.device_name, "error": err},
                status="FAILED",
            ))
            db.commit()
            return {"connected": False, "status": "ERROR", "detail": err}

    @staticmethod
    def run_read_only_operation(db: Session, profile: DeviceConnectionProfile, operation: str, actor: str) -> Dict[str, Any]:
        from app.services.network_connector import resolve_allowlisted_command
        resolve_allowlisted_command(operation)
        secrets_to_redact: List[str] = []
        connector, secrets_to_redact = DeviceConnectionManager._build_ssh_connector(db, profile)
        try:
            res = connector.run_read_only_operation(operation)
            db.add(AuditLog(
                username=actor,
                action="DEVICE_READ_ONLY_OP",
                resource_type="DEVICE_CONNECTION",
                resource_id=profile.id,
                details={"device": profile.device_name, "operation": operation},
                status="SUCCESS",
            ))
            db.commit()
            return res
        except Exception as exc:
            err = _redact_error(str(exc), secrets_to_redact)
            raise RuntimeError(err)
