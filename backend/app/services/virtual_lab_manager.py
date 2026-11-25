from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.models import AuditLog, CredentialVault, VirtualLabServer
from app.services.device_connection_manager import decrypt_secret
from app.services.eve_ng_connector import EVENGConnector
from app.services.gns3_connector import GNS3Connector
from app.services.topology_synchronizer import TopologySynchronizer


class VirtualLabManager:
    """Manages configured GNS3 and EVE-NG virtual laboratory servers."""

    @staticmethod
    def register_server(
        db: Session,
        name: str,
        lab_type: str,
        base_url: str,
        credential_ref: Optional[str],
        actor: str,
    ) -> VirtualLabServer:
        lt = lab_type.upper()
        if lt not in {"GNS3", "EVE_NG"}:
            raise ValueError("lab_type must be GNS3 or EVE_NG")
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            raise ValueError("base_url must start with http:// or https://")

        srv = VirtualLabServer(
            name=name.strip()[:100],
            lab_type=lt,
            base_url=base_url.strip()[:255],
            credential_ref=credential_ref,
            connection_status="DISCONNECTED",
            created_by=actor,
        )
        db.add(srv)
        db.add(AuditLog(
            username=actor,
            action="VIRTUAL_LAB_REGISTERED",
            resource_type="VIRTUAL_LAB",
            resource_id=name,
            details={"lab_type": lt, "base_url": srv.base_url},
            status="SUCCESS",
        ))
        db.commit()
        db.refresh(srv)
        return srv

    @staticmethod
    def _auth_tuple(db: Session, credential_ref: Optional[str]) -> Optional[tuple]:
        if not credential_ref:
            return None
        cred = db.query(CredentialVault).filter(CredentialVault.credential_ref == credential_ref).first()
        if not cred:
            return None
        return (cred.username, decrypt_secret(cred.encrypted_password))

    @staticmethod
    def discover(db: Session, server: VirtualLabServer) -> Dict[str, Any]:
        auth = VirtualLabManager._auth_tuple(db, server.credential_ref)
        try:
            if server.lab_type == "GNS3":
                conn = GNS3Connector(server.base_url, auth=auth)
                info = conn.test_connection()
                projects = conn.list_projects()
                summary = {
                    "lab_type": "GNS3",
                    "environment": "LAB",
                    "version": info.get("version"),
                    "projects": projects,
                }
            else:
                u, p = auth if auth else ("admin", "eve")
                conn = EVENGConnector(server.base_url, username=u, password=p)
                info = conn.test_connection()
                labs = conn.list_labs()
                summary = {
                    "lab_type": "EVE_NG",
                    "environment": "LAB",
                    "labs": labs,
                    "unsupported_capabilities": info.get("unsupported_capabilities"),
                }
            server.connection_status = "CONNECTED"
            server.last_error = None
            server.discovered_summary = summary
            db.commit()
            return summary
        except Exception as exc:
            server.connection_status = "ERROR"
            server.last_error = str(exc)[:240]
            db.commit()
            return {"connected": False, "status": "ERROR", "error": server.last_error}

    @staticmethod
    def sync_project_or_lab(
        db: Session,
        server: VirtualLabServer,
        target_id: str,
        actor: str,
    ) -> Dict[str, Any]:
        auth = VirtualLabManager._auth_tuple(db, server.credential_ref)
        nodes_norm: List[Dict[str, Any]] = []
        links_norm: List[Dict[str, Any]] = []

        if server.lab_type == "GNS3":
            conn = GNS3Connector(server.base_url, auth=auth)
            topo = conn.get_project_topology(target_id)
            for n in topo.get("nodes", []):
                nodes_norm.append({
                    "external_id": n.get("node_id"),
                    "name": n.get("name"),
                    "status": n.get("status"),
                    "device_type": n.get("node_type", "router"),
                    "model": n.get("node_type", "GNS3 Node"),
                })
            for l in topo.get("links", []):
                eps = l.get("nodes", [])
                if len(eps) >= 2:
                    links_norm.append({
                        "source_node_id": eps[0].get("node_id"),
                        "target_node_id": eps[1].get("node_id"),
                        "source_port": f"p{eps[0].get('port_number', 0)}",
                        "target_port": f"p{eps[1].get('port_number', 0)}",
                    })
            source_label = f"GNS3:{target_id}"
        else:
            u, p = auth if auth else ("admin", "eve")
            conn = EVENGConnector(server.base_url, username=u, password=p)
            topo = conn.get_lab_topology(target_id)
            raw_nodes = topo.get("nodes", {})
            if isinstance(raw_nodes, dict):
                for nid, n in raw_nodes.items():
                    nodes_norm.append({
                        "external_id": nid,
                        "name": n.get("name", f"eve-node-{nid}"),
                        "status": "started" if str(n.get("status")) == "2" else "stopped",
                        "device_type": "router",
                        "model": n.get("template", "EVE-NG Node"),
                    })
            source_label = f"EVE_NG:{target_id}"

        sync_res = TopologySynchronizer.sync_lab_topology(db, source_label, nodes_norm, links_norm)
        server.last_sync_at = datetime.now(timezone.utc)
        server.connection_status = "CONNECTED"
        db.add(AuditLog(
            username=actor,
            action="VIRTUAL_LAB_SYNCED",
            resource_type="VIRTUAL_LAB",
            resource_id=server.id,
            details=sync_res,
            status="SUCCESS",
        ))
        db.commit()
        return sync_res
