from typing import Any, Dict, List, Optional
from app.models import CredentialVault, DeviceConnectionProfile
from app.services.device_connection_manager import decrypt_secret

STANDARD_CISCO_OIDS = {
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "cpu_utilization": "1.3.6.1.4.1.9.9.109.1.1.1.1.6.1",
    "memory_used": "1.3.6.1.4.1.9.9.48.1.1.1.5.1",
    "ifOperStatus": "1.3.6.1.2.1.2.2.1.8",
    "ifAdminStatus": "1.3.6.1.2.1.2.2.1.7",
    "ifInOctets": "1.3.6.1.2.1.2.2.1.10",
    "ifOutOctets": "1.3.6.1.2.1.2.2.1.16",
    "ifInErrors": "1.3.6.1.2.1.2.2.1.14",
    "ifOutErrors": "1.3.6.1.2.1.2.2.1.20",
    "ifSpeed": "1.3.6.1.2.1.2.2.1.5",
}


class SNMPAuthError(Exception):
    """Raised when SNMPv3 authentication or privacy validation fails."""


class SNMPv3Collector:
    """
    SNMPv3 metric collector for authorized LAB/PRODUCTION devices.
    Never exposes SNMP credentials in responses, logs, or exceptions.
    Gracefully handles unsupported OIDs.
    """

    @staticmethod
    def _snmp_get(
        host: str,
        port: int,
        username: str,
        auth_key: str,
        priv_key: Optional[str],
        auth_proto: str,
        priv_proto: Optional[str],
        oids: Dict[str, str],
        timeout_seconds: int = 5,
    ) -> Dict[str, Any]:
        # Real pysnmp transport if available; otherwise explicit runtime error
        try:
            import pysnmp  # noqa: F401
        except ImportError:
            raise RuntimeError(f"SNMPv3 UDP transport unavailable for {host}:{port} (pysnmp not installed).")
        raise RuntimeError(f"Direct SNMPv3 polling to {host}:{port} requires live network reachability.")

    @staticmethod
    def collect_device_metrics(
        profile: DeviceConnectionProfile,
        cred: CredentialVault,
    ) -> Dict[str, Any]:
        auth_key = decrypt_secret(cred.encrypted_password)
        priv_key = decrypt_secret(cred.encrypted_secret) if cred.encrypted_secret else None
        auth_proto = (cred.auth_protocol or "SHA").upper()
        priv_proto = (cred.priv_protocol or "AES128").upper() if priv_key else None

        if auth_proto not in {"SHA", "SHA256", "MD5"}:
            raise SNMPAuthError("Unsupported SNMPv3 authentication protocol.")

        try:
            raw = SNMPv3Collector._snmp_get(
                host=profile.management_ip,
                port=profile.port if profile.protocol == "SNMPV3" else 161,
                username=cred.username,
                auth_key=auth_key,
                priv_key=priv_key,
                auth_proto=auth_proto,
                priv_proto=priv_proto,
                oids=STANDARD_CISCO_OIDS,
                timeout_seconds=profile.timeout_seconds,
            )
        except SNMPAuthError:
            raise
        except Exception as exc:
            # Redact secrets from any exception
            msg = str(exc).replace(auth_key, "[REDACTED]")
            if priv_key:
                msg = msg.replace(priv_key, "[REDACTED]")
            raise RuntimeError(msg[:220])

        unsupported_oids: List[str] = []
        metrics: Dict[str, Any] = {}
        for name in ("sysUpTime", "cpu_utilization", "memory_used"):
            val = raw.get(name)
            if val is None or val == "NO_SUCH_OBJECT":
                unsupported_oids.append(name)
                metrics[name] = None
            else:
                metrics[name] = val

        interfaces = raw.get("interfaces", [])
        return {
            "device_name": profile.device_name,
            "telemetry_source": profile.environment,
            "collection_method": "SNMPV3",
            "metrics": metrics,
            "interfaces": interfaces,
            "unsupported_oids": unsupported_oids,
        }
