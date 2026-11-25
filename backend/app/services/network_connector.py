import ipaddress
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from app.core.config import settings

# Strict read-only Cisco IOS command allowlist (never accepts arbitrary CLI strings)
READ_ONLY_COMMAND_ALLOWLIST: Dict[str, str] = {
    "device_identity": "show running-config | include hostname",
    "device_version": "show version",
    "interface_status": "show ip interface brief",
    "interface_statistics": "show interfaces",
    "vlan_info": "show vlan brief",
    "trunk_info": "show interfaces trunk",
    "cpu_utilization": "show processes cpu sorted | head 5",
    "memory_utilization": "show memory statistics",
    "uptime": "show version | include uptime",
}


def validate_approved_destination(ip_str: str, environment: str) -> str:
    env = (environment or "").upper()
    if env not in {"SIMULATION", "LAB", "PRODUCTION"}:
        raise ValueError(f"Unsupported environment '{environment}'. Must be SIMULATION, LAB, or PRODUCTION.")
    if env == "PRODUCTION" and not settings.PRODUCTION_INTEGRATION_ENABLED:
        raise PermissionError("PRODUCTION device integration is disabled by default.")
    if env == "LAB" and not settings.LAB_INTEGRATION_ENABLED:
        raise PermissionError("LAB device integration is disabled.")

    try:
        addr = ipaddress.ip_address(ip_str.strip())
    except ValueError:
        raise ValueError(f"Invalid management IP address: '{ip_str}'.")

    if addr.is_multicast or addr.is_unspecified:
        raise ValueError("Multicast or unspecified IP addresses are not permitted.")

    allowed = False
    for cidr in settings.APPROVED_INTEGRATION_CIDRS:
        try:
            net = ipaddress.ip_network(cidr, strict=False)
            if addr in net:
                allowed = True
                break
        except ValueError:
            continue

    if not allowed:
        raise PermissionError(f"Destination {addr} is outside APPROVED_INTEGRATION_CIDRS.")
    return str(addr)


def resolve_allowlisted_command(operation: str) -> str:
    if operation not in READ_ONLY_COMMAND_ALLOWLIST:
        raise ValueError(
            f"Operation '{operation}' is not in the read-only command allowlist. Arbitrary CLI execution is forbidden."
        )
    return READ_ONLY_COMMAND_ALLOWLIST[operation]


class NetworkConnector(ABC):
    """Abstract base class for read-only network device connectors."""

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def run_read_only_operation(self, operation: str) -> Dict[str, Any]:
        pass
