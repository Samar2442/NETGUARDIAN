from typing import Any, Dict, List, Optional, Tuple
import httpx


class GNS3Connector:
    """
    Documented GNS3 REST API v2 connector (/v2/version, /v2/projects, nodes, links).
    """

    def __init__(
        self,
        base_url: str,
        auth: Optional[Tuple[str, str]] = None,
        timeout_seconds: int = 8,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.timeout = timeout_seconds

    def _get(self, path: str) -> Any:
        with httpx.Client(timeout=self.timeout, auth=self.auth) as client:
            resp = client.get(f"{self.base_url}{path}")
            resp.raise_for_status()
            return resp.json()

    def test_connection(self) -> Dict[str, Any]:
        ver = self._get("/v2/version")
        return {"connected": True, "version": ver.get("version"), "local": ver.get("local")}

    def list_projects(self) -> List[Dict[str, Any]]:
        return self._get("/v2/projects")

    def get_project_topology(self, project_id: str) -> Dict[str, Any]:
        project = self._get(f"/v2/projects/{project_id}")
        nodes = self._get(f"/v2/projects/{project_id}/nodes")
        links = self._get(f"/v2/projects/{project_id}/links")
        return {
            "project": project,
            "nodes": nodes,
            "links": links,
        }
