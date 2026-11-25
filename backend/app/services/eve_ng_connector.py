from typing import Any, Dict, List, Optional
import httpx


class EVENGConnector:
    """
    Documented EVE-NG REST API connector (/api/auth/login, /api/status, /api/folders/, /api/labs/...).
    Exposes explicit UNSUPPORTED status for capabilities not provided by the EVE-NG REST API.
    """

    UNSUPPORTED_CAPABILITIES = {
        "interface_counters_polling": "UNSUPPORTED: EVE-NG REST API does not expose live SNMP-style interface counters directly.",
        "ssh_config_push": "UNSUPPORTED: Milestone 8 restricts EVE-NG integration to read-only discovery.",
    }

    def __init__(
        self,
        base_url: str,
        username: str = "admin",
        password: str = "eve",
        timeout_seconds: int = 8,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout_seconds

    def _client(self) -> httpx.Client:
        client = httpx.Client(timeout=self.timeout)
        login_resp = client.post(
            f"{self.base_url}/api/auth/login",
            json={"username": self.username, "password": self.password, "html5": "-1"},
        )
        login_resp.raise_for_status()
        return client

    def test_connection(self) -> Dict[str, Any]:
        with self._client() as client:
            resp = client.get(f"{self.base_url}/api/status")
            resp.raise_for_status()
            data = resp.json()
            return {
                "connected": True,
                "status": data.get("data", {}),
                "unsupported_capabilities": self.UNSUPPORTED_CAPABILITIES,
            }

    def list_labs(self) -> List[Dict[str, Any]]:
        with self._client() as client:
            resp = client.get(f"{self.base_url}/api/folders/")
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return data.get("labs", [])

    def get_lab_topology(self, lab_path: str) -> Dict[str, Any]:
        clean_path = lab_path.lstrip("/")
        with self._client() as client:
            nodes_resp = client.get(f"{self.base_url}/api/labs/{clean_path}/nodes")
            nodes_resp.raise_for_status()
            nets_resp = client.get(f"{self.base_url}/api/labs/{clean_path}/networks")
            nets_resp.raise_for_status()
            return {
                "lab_path": clean_path,
                "nodes": nodes_resp.json().get("data", {}),
                "networks": nets_resp.json().get("data", {}),
                "unsupported_capabilities": self.UNSUPPORTED_CAPABILITIES,
            }
