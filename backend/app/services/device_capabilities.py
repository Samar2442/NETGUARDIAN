from typing import Any, Dict, List
from app.models import DeviceConnectionProfile
from app.services.network_connector import READ_ONLY_COMMAND_ALLOWLIST


class DeviceCapabilityDetector:
    """
    Detects and reports supported management & telemetry capabilities
    (SSH, SNMPv3, NETCONF, RESTCONF, Syslog) and explicitly marks unsupported ones.
    """

    @staticmethod
    def detect_capabilities(profile: DeviceConnectionProfile, ssh_reachable: bool = False) -> Dict[str, Any]:
        proto = (profile.protocol or "SSH").upper()
        platform = (profile.device_platform or "cisco_ios").lower()

        capabilities = {
            "SSH": {
                "supported": proto == "SSH" or ssh_reachable,
                "status": "SUPPORTED" if (proto == "SSH" and ssh_reachable) else ("CONFIGURED" if proto == "SSH" else "UNSUPPORTED"),
                "port": profile.port if proto == "SSH" else 22,
            },
            "SNMPv3": {
                "supported": proto == "SNMPV3",
                "status": "CONFIGURED" if proto == "SNMPV3" else "UNSUPPORTED",
                "port": 161,
            },
            "NETCONF": {
                "supported": proto == "NETCONF" and ("xe" in platform or "nxos" in platform),
                "status": "CONFIGURED" if (proto == "NETCONF" and ("xe" in platform or "nxos" in platform)) else "UNSUPPORTED",
                "port": 830,
                "reason": None if ("xe" in platform or "nxos" in platform) else f"Platform '{platform}' does not advertise NETCONF support.",
            },
            "RESTCONF": {
                "supported": proto == "RESTCONF" and ("xe" in platform or "nxos" in platform),
                "status": "CONFIGURED" if (proto == "RESTCONF" and ("xe" in platform or "nxos" in platform)) else "UNSUPPORTED",
                "port": 443,
                "reason": None if ("xe" in platform or "nxos" in platform) else f"Platform '{platform}' does not advertise RESTCONF support.",
            },
            "Syslog": {
                "supported": True,
                "status": "SUPPORTED_RECEIVER",
                "port": 514,
            },
            "read_only_operations": list(READ_ONLY_COMMAND_ALLOWLIST.keys()),
        }
        return capabilities
