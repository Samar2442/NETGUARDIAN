from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from app.models import DeviceConnectionProfile, VirtualLabServer

MANUAL_LAB_VALIDATION_PROCEDURE = [
    "1. Configure an encrypted CredentialVault entry via POST /api/v1/integrations/credentials (admin only).",
    "2. Register an approved LAB DeviceConnectionProfile (10.0.0.0/8, 172.16.0.0/12, or 192.168.0.0/16) with SHA-256 SSH host-key fingerprint or SNMPv3 authPriv.",
    "3. Execute POST /api/v1/integrations/profiles/{id}/test (engineer) to verify real SSH host-key and reachability.",
    "4. Execute POST /api/v1/integrations/telemetry/poll/{id} (engineer) to verify live SNMPv3 MIB-II & Cisco OIDs.",
    "5. Register GNS3 or EVE-NG server via POST /api/v1/integrations/labs/servers and run discover/sync.",
]


class IntegrationValidator:
    """
    Reports actual validation status for CISCO_SSH, SNMPV3, GNS3, and EVE_NG.
    Never marks an integration as VALIDATED based on mocked responses.
    """

    @staticmethod
    def _profile_status(profiles: List[DeviceConnectionProfile], protocol: str) -> str:
        matching = [p for p in profiles if p.protocol == protocol]
        if not matching:
            return "NOT_CONFIGURED"
        if any(p.connection_status == "CONNECTED" and p.last_successful_connection is not None for p in matching):
            return "CONNECTED"
        if any("auth" in (p.last_connection_error or "").lower() for p in matching):
            return "AUTHENTICATION_FAILED"
        if any(p.connection_status == "ERROR" for p in matching):
            return "CONNECTION_FAILED"
        return "NOT_CONNECTED"

    @staticmethod
    def _lab_status(servers: List[VirtualLabServer], lab_type: str) -> str:
        matching = [s for s in servers if s.lab_type == lab_type]
        if not matching:
            return "NOT_CONFIGURED"
        if any(s.connection_status == "CONNECTED" for s in matching):
            return "PARTIALLY_SUPPORTED" if lab_type == "EVE_NG" else "CONNECTED"
        if any("auth" in (s.last_error or "").lower() or "401" in (s.last_error or "") for s in matching):
            return "AUTHENTICATION_FAILED"
        if any(s.connection_status == "ERROR" for s in matching):
            return "CONNECTION_FAILED"
        return "NOT_CONNECTED"

    @staticmethod
    def build_validation_report(db: Session) -> Dict[str, Any]:
        profiles = db.query(DeviceConnectionProfile).all()
        servers = db.query(VirtualLabServer).all()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "integrations": {
                "CISCO_SSH": {
                    "status": IntegrationValidator._profile_status(profiles, "SSH"),
                    "configured_count": sum(1 for p in profiles if p.protocol == "SSH"),
                    "read_only_allowlist_enforced": True,
                },
                "SNMPV3": {
                    "status": IntegrationValidator._profile_status(profiles, "SNMPV3"),
                    "configured_count": sum(1 for p in profiles if p.protocol == "SNMPV3"),
                    "pysnmp_v3_ready": True,
                },
                "GNS3": {
                    "status": IntegrationValidator._lab_status(servers, "GNS3"),
                    "configured_count": sum(1 for s in servers if s.lab_type == "GNS3"),
                },
                "EVE_NG": {
                    "status": IntegrationValidator._lab_status(servers, "EVE_NG"),
                    "configured_count": sum(1 for s in servers if s.lab_type == "EVE_NG"),
                    "note": "Interface counter polling and config push are explicitly UNSUPPORTED via EVE-NG REST API.",
                },
            },
            "manual_validation_procedure": MANUAL_LAB_VALIDATION_PROCEDURE,
        }
