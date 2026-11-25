import base64
import hashlib
import re
import time
from typing import Any, Dict, List, Optional
import paramiko
from app.services.network_connector import NetworkConnector, resolve_allowlisted_command


class HostKeyMismatchError(Exception):
    """Raised when SSH server host key does not match the configured fingerprint."""


class _StrictFingerprintPolicy(paramiko.MissingHostKeyPolicy):
    """
    Strict SSH host-key verification policy.
    Never silently accepts unknown or mismatched host keys.
    """

    def __init__(self, expected_fingerprint: Optional[str]) -> None:
        self.expected_fingerprint = (expected_fingerprint or "").strip()

    def missing_host_key(self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey) -> None:
        if not self.expected_fingerprint:
            raise paramiko.SSHException(
                f"SSH host-key verification failed for {hostname}: no trusted fingerprint configured."
            )
        digest = hashlib.sha256(key.asbytes()).digest()
        actual_fp = "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")
        if actual_fp != self.expected_fingerprint:
            raise HostKeyMismatchError(
                f"SSH host-key mismatch for {hostname}: expected {self.expected_fingerprint}, got {actual_fp}."
            )


def parse_show_ip_int_brief(raw: str) -> List[Dict[str, str]]:
    interfaces = []
    for line in raw.splitlines():
        m = re.match(
            r"^(\S+)\s+(\d+\.\d+\.\d+\.\d+|unassigned)\s+\S+\s+\S+\s+(up|down|administratively down)\s+(up|down)",
            line.strip(),
            re.IGNORECASE,
        )
        if m:
            interfaces.append({
                "interface": m.group(1),
                "ip_address": m.group(2),
                "admin_status": "down" if "administratively" in m.group(3).lower() else m.group(3).lower(),
                "oper_status": m.group(4).lower(),
            })
    return interfaces


def parse_show_vlan_brief(raw: str) -> List[Dict[str, Any]]:
    vlans = []
    for line in raw.splitlines():
        m = re.match(r"^(\d+)\s+(\S+)\s+(active|suspend|act/unsup)\s*(.*)$", line.strip(), re.IGNORECASE)
        if m:
            vlans.append({
                "vlan_id": int(m.group(1)),
                "name": m.group(2),
                "status": m.group(3).lower(),
                "ports": [p.strip() for p in m.group(4).split(",") if p.strip()],
            })
    return vlans


class SSHConnector(NetworkConnector):
    """
    Read-only Cisco SSH connector using Paramiko with strict host-key verification,
    connection timeouts, retry limits, and command allowlisting.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        expected_fingerprint: Optional[str],
        timeout_seconds: int = 10,
        max_retries: int = 2,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.expected_fingerprint = expected_fingerprint
        self.timeout_seconds = max(2, min(timeout_seconds, 30))
        self.max_retries = max(1, min(max_retries, 3))

    def _connect(self) -> paramiko.SSHClient:
        last_err: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(_StrictFingerprintPolicy(self.expected_fingerprint))
            try:
                client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.timeout_seconds,
                    banner_timeout=self.timeout_seconds,
                    auth_timeout=self.timeout_seconds,
                    allow_agent=False,
                    look_for_keys=False,
                )
                return client
            except (HostKeyMismatchError, paramiko.AuthenticationException) as exc:
                client.close()
                raise exc
            except Exception as exc:
                client.close()
                last_err = exc
                if attempt < self.max_retries:
                    time.sleep(min(1.0 * attempt, 2.0))
        raise TimeoutError(f"SSH connection to {self.host}:{self.port} failed after {self.max_retries} attempts: {last_err}")

    def test_connection(self) -> Dict[str, Any]:
        client = self._connect()
        try:
            transport = client.get_transport()
            remote_key = transport.get_remote_server_key() if transport else None
            fp = None
            if remote_key:
                fp = "SHA256:" + base64.b64encode(hashlib.sha256(remote_key.asbytes()).digest()).decode("ascii").rstrip("=")
            return {
                "connected": True,
                "host": self.host,
                "port": self.port,
                "host_key_verified": True,
                "fingerprint": fp,
            }
        finally:
            client.close()

    def run_read_only_operation(self, operation: str) -> Dict[str, Any]:
        cmd = resolve_allowlisted_command(operation)
        client = self._connect()
        try:
            _, stdout, stderr = client.exec_command(cmd, timeout=self.timeout_seconds)
            raw_out = stdout.read().decode("utf-8", errors="replace")
            raw_err = stderr.read().decode("utf-8", errors="replace")
            parsed: Any = raw_out.strip()
            if operation == "interface_status":
                parsed = parse_show_ip_int_brief(raw_out)
            elif operation == "vlan_info":
                parsed = parse_show_vlan_brief(raw_out)
            return {
                "operation": operation,
                "command": cmd,
                "structured_data": parsed,
                "stderr": raw_err.strip(),
            }
        finally:
            client.close()
