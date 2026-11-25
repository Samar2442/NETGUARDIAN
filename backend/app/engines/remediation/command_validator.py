import hashlib
import hmac
import json
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class RemediationSecurityError(Exception):
    """Base exception for Phase 5A remediation security violations."""
    pass


class CommandValidationError(RemediationSecurityError):
    """Raised when a command, operation, or parameter fails strict allowlist validation."""
    pass


class ApprovalBindingError(RemediationSecurityError):
    """Raised when execution does not match the cryptographically bound approval."""
    pass


class ExecutionLockError(RemediationSecurityError):
    """Raised when a conflicting operation is already executing on the target device."""
    pass


class ExecutionModeError(RemediationSecurityError):
    """Raised when the requested execution mode is disabled or unauthorized."""
    pass


class DuplicateExecutionError(RemediationSecurityError):
    """Raised when attempting to re-execute an already executed or non-approved proposal."""
    pass


class RollbackEligibilityError(RemediationSecurityError):
    """Raised when a proposal is not eligible for rollback."""
    pass


class RemediationOperation(str, Enum):
    CREATE_VLAN = "CREATE_VLAN"
    ADD_VLAN_TO_TRUNK = "ADD_VLAN_TO_TRUNK"
    REMOVE_VLAN_FROM_TRUNK = "REMOVE_VLAN_FROM_TRUNK"
    ENABLE_INTERFACE = "ENABLE_INTERFACE"
    DISABLE_INTERFACE = "DISABLE_INTERFACE"
    CONFIGURE_ACCESS_VLAN = "CONFIGURE_ACCESS_VLAN"
    RESTORE_CONFIG_SNAPSHOT = "RESTORE_CONFIG_SNAPSHOT"
    VERIFY_TRUNK_CONFIG = "VERIFY_TRUNK_CONFIG"
    VERIFY_VLAN_EXISTS = "VERIFY_VLAN_EXISTS"
    VERIFY_INTERFACE_STATUS = "VERIFY_INTERFACE_STATUS"


class ExecutionMode(str, Enum):
    SIMULATION = "SIMULATION"
    LAB = "LAB"
    PRODUCTION = "PRODUCTION"


class ConfigMode(str, Enum):
    EXEC = "EXEC"
    GLOBAL = "GLOBAL"
    INTERFACE = "INTERFACE"


# Strict regexes to prevent command injection and malformed Cisco identifiers
_INJECTION_CHARS_RE = re.compile(r"[;&|`$><\r\x00\\]")
_DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
_INTERFACE_NAME_RE = re.compile(
    r"^(GigabitEthernet|FastEthernet|TenGigabitEthernet|TwentyFiveGigE|"
    r"FortyGigabitEthernet|Port-channel|Loopback|Vlan|Serial|Ethernet)"
    r"\d+(?:/\d+){0,2}(?:\.\d+)?$"
)
_VLAN_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
_SNAPSHOT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Strict line-by-line Cisco IOS command allowlist
_ALLOWLISTED_LINE_PATTERNS = [
    re.compile(r"^interface\s+" + _INTERFACE_NAME_RE.pattern[1:]),
    re.compile(r"^switchport\s+trunk\s+allowed\s+vlan\s+(?:add|remove)\s+(\d{1,4})$"),
    re.compile(r"^switchport\s+mode\s+(?:access|trunk)$"),
    re.compile(r"^switchport\s+access\s+vlan\s+(\d{1,4})$"),
    re.compile(r"^(?:no\s+)?shutdown$"),
    re.compile(r"^(?:no\s+)?vlan\s+(\d{1,4})$"),
    re.compile(r"^name\s+[A-Za-z0-9_-]{1,32}$"),
    re.compile(r"^configure\s+replace\s+flash:snapshots/[A-Za-z0-9_-]{1,64}\.cfg\s+force$"),
    re.compile(r"^show\s+interfaces\s+" + _INTERFACE_NAME_RE.pattern[1:-1] + r"\s+(?:trunk|status)$"),
    re.compile(r"^show\s+vlan\s+id\s+(\d{1,4})$"),
]

# Allowed parameter keys per operation (prevents unexpected argument injection)
_OPERATION_PARAM_SCHEMA: Dict[RemediationOperation, Dict[str, Any]] = {
    RemediationOperation.CREATE_VLAN: {
        "requires_interface": False,
        "required_params": {"vlan_id"},
        "optional_params": {"vlan_name"},
        "config_mode": ConfigMode.GLOBAL,
    },
    RemediationOperation.ADD_VLAN_TO_TRUNK: {
        "requires_interface": True,
        "required_params": {"vlan_id"},
        "optional_params": set(),
        "config_mode": ConfigMode.INTERFACE,
    },
    RemediationOperation.REMOVE_VLAN_FROM_TRUNK: {
        "requires_interface": True,
        "required_params": {"vlan_id"},
        "optional_params": set(),
        "config_mode": ConfigMode.INTERFACE,
    },
    RemediationOperation.ENABLE_INTERFACE: {
        "requires_interface": True,
        "required_params": set(),
        "optional_params": set(),
        "config_mode": ConfigMode.INTERFACE,
    },
    RemediationOperation.DISABLE_INTERFACE: {
        "requires_interface": True,
        "required_params": set(),
        "optional_params": set(),
        "config_mode": ConfigMode.INTERFACE,
    },
    RemediationOperation.CONFIGURE_ACCESS_VLAN: {
        "requires_interface": True,
        "required_params": {"vlan_id"},
        "optional_params": set(),
        "config_mode": ConfigMode.INTERFACE,
    },
    RemediationOperation.RESTORE_CONFIG_SNAPSHOT: {
        "requires_interface": False,
        "required_params": {"snapshot_id"},
        "optional_params": set(),
        "config_mode": ConfigMode.EXEC,
    },
    RemediationOperation.VERIFY_TRUNK_CONFIG: {
        "requires_interface": True,
        "required_params": set(),
        "optional_params": {"vlan_id"},
        "config_mode": ConfigMode.EXEC,
    },
    RemediationOperation.VERIFY_VLAN_EXISTS: {
        "requires_interface": False,
        "required_params": {"vlan_id"},
        "optional_params": set(),
        "config_mode": ConfigMode.EXEC,
    },
    RemediationOperation.VERIFY_INTERFACE_STATUS: {
        "requires_interface": True,
        "required_params": set(),
        "optional_params": set(),
        "config_mode": ConfigMode.EXEC,
    },
}


def check_no_injection(value: str, field_name: str) -> str:
    if not isinstance(value, str):
        raise CommandValidationError(f"Field '{field_name}' must be a string.")
    if "\n" in value or _INJECTION_CHARS_RE.search(value):
        raise CommandValidationError(
            f"Disallowed shell or control characters detected in '{field_name}'."
        )
    return value


def validate_device_id(device_id: str) -> str:
    if not device_id or not isinstance(device_id, str):
        raise CommandValidationError("Device ID must be a non-empty string.")
    check_no_injection(device_id, "device_id")
    if not _DEVICE_ID_RE.match(device_id.strip()):
        raise CommandValidationError(f"Invalid device identifier format: '{device_id}'.")
    return device_id.strip()


def validate_interface_name(interface: Optional[str]) -> str:
    if not interface or not isinstance(interface, str):
        raise CommandValidationError("Target interface must be a non-empty string.")
    check_no_injection(interface, "interface")
    cleaned = interface.strip()
    if not _INTERFACE_NAME_RE.match(cleaned):
        raise CommandValidationError(
            f"Invalid Cisco interface name '{cleaned}'. Expected canonical format such as GigabitEthernet0/1."
        )
    return cleaned


def validate_vlan_id(vlan_id: Any) -> int:
    if isinstance(vlan_id, bool):
        raise CommandValidationError("VLAN ID cannot be a boolean.")
    if isinstance(vlan_id, str):
        check_no_injection(vlan_id, "vlan_id")
        if not vlan_id.strip().isdigit():
            raise CommandValidationError(f"Invalid VLAN ID '{vlan_id}'. Must be an integer 1..4094.")
        vlan_num = int(vlan_id.strip())
    elif isinstance(vlan_id, int):
        vlan_num = vlan_id
    else:
        raise CommandValidationError("VLAN ID must be an integer between 1 and 4094.")

    if vlan_num < 1 or vlan_num > 4094:
        raise CommandValidationError(f"VLAN ID {vlan_num} out of valid IEEE 802.1Q range (1-4094).")
    return vlan_num


def validate_vlan_name(vlan_name: Any) -> str:
    if not isinstance(vlan_name, str):
        raise CommandValidationError("VLAN name must be a string.")
    check_no_injection(vlan_name, "vlan_name")
    cleaned = vlan_name.strip()
    if not _VLAN_NAME_RE.match(cleaned):
        raise CommandValidationError(
            "VLAN name must be 1-32 alphanumeric, underscore, or hyphen characters."
        )
    return cleaned


def validate_snapshot_id(snapshot_id: Any) -> str:
    if not isinstance(snapshot_id, str):
        raise CommandValidationError("Snapshot ID must be a string.")
    check_no_injection(snapshot_id, "snapshot_id")
    cleaned = snapshot_id.strip()
    if not _SNAPSHOT_ID_RE.match(cleaned):
        raise CommandValidationError("Invalid snapshot ID format.")
    return cleaned


def build_structured_commands(
    operation: str,
    interface: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, ConfigMode, Dict[str, Any]]:
    """
    Validate a structured remediation operation and generate canonical Cisco IOS
    proposed commands and rollback commands. Never trusts arbitrary strings.
    """
    if not operation or not isinstance(operation, str):
        raise CommandValidationError("Remediation operation is required.")
    try:
        op = RemediationOperation(operation.strip().upper())
    except ValueError:
        raise CommandValidationError(f"Unsupported remediation operation: '{operation}'.")

    schema = _OPERATION_PARAM_SCHEMA[op]
    params = dict(parameters or {})

    # Reject unexpected parameter keys
    allowed_keys = schema["required_params"] | schema["optional_params"]
    unexpected = set(params.keys()) - allowed_keys
    if unexpected:
        raise CommandValidationError(
            f"Unexpected parameters for {op.value}: {sorted(unexpected)}"
        )

    missing = schema["required_params"] - set(params.keys())
    if missing:
        raise CommandValidationError(
            f"Missing required parameters for {op.value}: {sorted(missing)}"
        )

    validated_iface: Optional[str] = None
    if schema["requires_interface"]:
        validated_iface = validate_interface_name(interface)
    elif interface is not None and str(interface).strip():
        # If an interface is provided on a non-interface op, still validate it strictly
        validated_iface = validate_interface_name(interface)

    normalized_params: Dict[str, Any] = {}

    if op == RemediationOperation.CREATE_VLAN:
        vid = validate_vlan_id(params["vlan_id"])
        normalized_params["vlan_id"] = vid
        if "vlan_name" in params and params["vlan_name"] is not None:
            vname = validate_vlan_name(params["vlan_name"])
            normalized_params["vlan_name"] = vname
            proposed = f"vlan {vid}\n name {vname}"
        else:
            proposed = f"vlan {vid}"
        rollback = f"no vlan {vid}"

    elif op == RemediationOperation.ADD_VLAN_TO_TRUNK:
        vid = validate_vlan_id(params["vlan_id"])
        normalized_params["vlan_id"] = vid
        proposed = f"interface {validated_iface}\n switchport trunk allowed vlan add {vid}"
        rollback = f"interface {validated_iface}\n switchport trunk allowed vlan remove {vid}"

    elif op == RemediationOperation.REMOVE_VLAN_FROM_TRUNK:
        vid = validate_vlan_id(params["vlan_id"])
        normalized_params["vlan_id"] = vid
        proposed = f"interface {validated_iface}\n switchport trunk allowed vlan remove {vid}"
        rollback = f"interface {validated_iface}\n switchport trunk allowed vlan add {vid}"

    elif op == RemediationOperation.ENABLE_INTERFACE:
        proposed = f"interface {validated_iface}\n no shutdown"
        rollback = f"interface {validated_iface}\n shutdown"

    elif op == RemediationOperation.DISABLE_INTERFACE:
        proposed = f"interface {validated_iface}\n shutdown"
        rollback = f"interface {validated_iface}\n no shutdown"

    elif op == RemediationOperation.CONFIGURE_ACCESS_VLAN:
        vid = validate_vlan_id(params["vlan_id"])
        normalized_params["vlan_id"] = vid
        proposed = (
            f"interface {validated_iface}\n"
            f" switchport mode access\n"
            f" switchport access vlan {vid}"
        )
        rollback = f"interface {validated_iface}\n switchport access vlan 1"

    elif op == RemediationOperation.RESTORE_CONFIG_SNAPSHOT:
        sid = validate_snapshot_id(params["snapshot_id"])
        normalized_params["snapshot_id"] = sid
        proposed = f"configure replace flash:snapshots/{sid}.cfg force"
        rollback = f"configure replace flash:snapshots/{sid}.cfg force"

    elif op == RemediationOperation.VERIFY_TRUNK_CONFIG:
        if "vlan_id" in params and params["vlan_id"] is not None:
            normalized_params["vlan_id"] = validate_vlan_id(params["vlan_id"])
        proposed = f"show interfaces {validated_iface} trunk"
        rollback = ""

    elif op == RemediationOperation.VERIFY_VLAN_EXISTS:
        vid = validate_vlan_id(params["vlan_id"])
        normalized_params["vlan_id"] = vid
        proposed = f"show vlan id {vid}"
        rollback = ""

    elif op == RemediationOperation.VERIFY_INTERFACE_STATUS:
        proposed = f"show interfaces {validated_iface} status"
        rollback = ""

    return proposed, rollback, schema["config_mode"], normalized_params


def validate_cisco_commands(
    commands: str,
    target_interface: Optional[str] = None,
    allow_empty: bool = False,
) -> List[str]:
    """
    Validate a multi-line Cisco IOS command block against the explicit allowlist.
    Rejects shell metacharacters, unexpected arguments, and unsupported combinations.
    """
    if commands is None or not isinstance(commands, str):
        raise CommandValidationError("Commands must be a string.")

    stripped = commands.strip()
    if not stripped:
        if allow_empty:
            return []
        raise CommandValidationError("Command block cannot be empty.")

    if _INJECTION_CHARS_RE.search(stripped):
        raise CommandValidationError(
            "Command block contains forbidden shell or injection characters."
        )

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        if allow_empty:
            return []
        raise CommandValidationError("Command block contains no valid commands.")

    current_mode = ConfigMode.EXEC
    seen_interface: Optional[str] = None
    has_config_cmd = False
    has_exec_show = False

    for line in lines:
        matched = False
        for pattern in _ALLOWLISTED_LINE_PATTERNS:
            m = pattern.match(line)
            if m:
                matched = True
                # Validate VLAN ID bounds if present in capture group
                if "vlan" in line and m.groups():
                    for grp in m.groups():
                        if grp and grp.isdigit():
                            validate_vlan_id(int(grp))
                break

        if not matched:
            raise CommandValidationError(
                f"Command '{line}' is not in the explicit Cisco IOS remediation allowlist."
            )

        # Enforce configuration mode consistency & reject unsupported combinations
        if line.startswith("show ") or line.startswith("configure replace "):
            if has_config_cmd:
                raise CommandValidationError(
                    "Unsupported combination: cannot mix EXEC commands with configuration mode commands."
                )
            has_exec_show = True
            current_mode = ConfigMode.EXEC
        elif line.startswith("interface "):
            if has_exec_show:
                raise CommandValidationError(
                    "Unsupported combination: cannot enter interface mode after EXEC command."
                )
            iface_in_cmd = line.split(None, 1)[1].strip()
            if target_interface and iface_in_cmd != target_interface:
                raise CommandValidationError(
                    f"Interface mismatch: command targets '{iface_in_cmd}' but proposal targets '{target_interface}'."
                )
            seen_interface = iface_in_cmd
            current_mode = ConfigMode.INTERFACE
            has_config_cmd = True
        elif line.startswith("switchport ") or line in {"shutdown", "no shutdown"}:
            if current_mode != ConfigMode.INTERFACE:
                raise CommandValidationError(
                    f"Configuration mode error: '{line}' requires INTERFACE configuration mode."
                )
            has_config_cmd = True
        elif line.startswith("vlan ") or line.startswith("no vlan "):
            if current_mode == ConfigMode.INTERFACE:
                raise CommandValidationError(
                    f"Configuration mode error: '{line}' is a GLOBAL command, invalid inside INTERFACE mode."
                )
            current_mode = ConfigMode.GLOBAL
            has_config_cmd = True
        elif line.startswith("name "):
            if current_mode != ConfigMode.GLOBAL:
                raise CommandValidationError(
                    "Configuration mode error: 'name' must follow 'vlan <id>' in GLOBAL mode."
                )
            has_config_cmd = True

    if target_interface and seen_interface is None and has_config_cmd:
        # Interface-scoped configuration commands must explicitly enter the interface
        raise CommandValidationError(
            f"Missing 'interface {target_interface}' context for interface configuration."
        )

    return lines


def infer_structured_operation(
    proposed_commands: str,
    target_interface: Optional[str] = None,
) -> Tuple[RemediationOperation, Dict[str, Any]]:
    """
    Strictly infer the structured operation and validated parameters from a legacy
    allowlisted Cisco IOS command block. Rejects anything outside the allowlist.
    """
    lines = validate_cisco_commands(proposed_commands, target_interface=target_interface)
    joined = "\n".join(lines)

    for line in lines:
        m = re.match(r"^switchport\s+trunk\s+allowed\s+vlan\s+add\s+(\d{1,4})$", line)
        if m:
            return RemediationOperation.ADD_VLAN_TO_TRUNK, {"vlan_id": validate_vlan_id(m.group(1))}

        m = re.match(r"^switchport\s+trunk\s+allowed\s+vlan\s+remove\s+(\d{1,4})$", line)
        if m:
            return RemediationOperation.REMOVE_VLAN_FROM_TRUNK, {"vlan_id": validate_vlan_id(m.group(1))}

        m = re.match(r"^switchport\s+access\s+vlan\s+(\d{1,4})$", line)
        if m:
            return RemediationOperation.CONFIGURE_ACCESS_VLAN, {"vlan_id": validate_vlan_id(m.group(1))}

        if line == "no shutdown":
            return RemediationOperation.ENABLE_INTERFACE, {}

        if line == "shutdown":
            return RemediationOperation.DISABLE_INTERFACE, {}

        m = re.match(r"^vlan\s+(\d{1,4})$", line)
        if m:
            params: Dict[str, Any] = {"vlan_id": validate_vlan_id(m.group(1))}
            for sub in lines:
                nm = re.match(r"^name\s+([A-Za-z0-9_-]{1,32})$", sub)
                if nm:
                    params["vlan_name"] = nm.group(1)
            return RemediationOperation.CREATE_VLAN, params

        m = re.match(r"^configure\s+replace\s+flash:snapshots/([A-Za-z0-9_-]{1,64})\.cfg\s+force$", line)
        if m:
            return RemediationOperation.RESTORE_CONFIG_SNAPSHOT, {"snapshot_id": m.group(1)}

        m = re.match(r"^show\s+interfaces\s+\S+\s+trunk$", line)
        if m:
            return RemediationOperation.VERIFY_TRUNK_CONFIG, {}

        m = re.match(r"^show\s+vlan\s+id\s+(\d{1,4})$", line)
        if m:
            return RemediationOperation.VERIFY_VLAN_EXISTS, {"vlan_id": validate_vlan_id(m.group(1))}

        m = re.match(r"^show\s+interfaces\s+\S+\s+status$", line)
        if m:
            return RemediationOperation.VERIFY_INTERFACE_STATUS, {}

    raise CommandValidationError(f"Unsupported command sequence: '{joined}'.")


def _normalize_timestamp(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def compute_approval_digest(
    proposal_id: str,
    device_id: str,
    target_interface: Optional[str],
    operation: Optional[str],
    parameters: Optional[Dict[str, Any]],
    proposed_commands: str,
    rollback_commands: str,
    config_revision: Optional[str],
    approved_by: Optional[str],
    approved_at: Optional[datetime],
) -> str:
    """
    Compute a deterministic SHA-256 cryptographic digest binding an approval to the
    exact proposal, device, interface, structured operation, parameters, commands,
    configuration revision, approver identity, and approval timestamp.
    """
    canonical_payload = {
        "proposal_id": str(proposal_id),
        "device_id": str(device_id),
        "target_interface": target_interface or "",
        "operation": operation or "",
        "parameters": parameters or {},
        "proposed_commands": (proposed_commands or "").strip(),
        "rollback_commands": (rollback_commands or "").strip(),
        "config_revision": config_revision or "BASELINE",
        "approved_by": approved_by or "",
        "approved_at": _normalize_timestamp(approved_at),
    }
    serialized = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def verify_approval_digest(expected_digest: Optional[str], actual_digest: str) -> bool:
    """Constant-time verification of approval binding digest."""
    if not expected_digest or not actual_digest:
        return False
    return hmac.compare_digest(expected_digest, actual_digest)


class DeviceExecutionLockManager:
    """
    Thread-safe per-device execution lock registry.
    Prevents two conflicting configuration operations from executing on the same
    device simultaneously.
    """

    def __init__(self) -> None:
        self._registry_lock = threading.Lock()
        self._device_locks: Dict[str, threading.Lock] = {}

    def _get_lock(self, device_id: str) -> threading.Lock:
        with self._registry_lock:
            if device_id not in self._device_locks:
                self._device_locks[device_id] = threading.Lock()
            return self._device_locks[device_id]

    @contextmanager
    def acquire(self, device_id: str, timeout: float = 0.0):
        lock = self._get_lock(device_id)
        acquired = lock.acquire(timeout=timeout) if timeout > 0 else lock.acquire(blocking=False)
        if not acquired:
            raise ExecutionLockError(
                f"Device '{device_id}' is currently locked by another active remediation or rollback operation."
            )
        try:
            yield
        finally:
            lock.release()


device_execution_locks = DeviceExecutionLockManager()
