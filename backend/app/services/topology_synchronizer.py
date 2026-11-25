from datetime import datetime, timezone
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from app.models import Device, NetworkLink


class TopologySynchronizer:
    """
    Safely maps discovered GNS3 / EVE-NG lab nodes and links into NETGUARDIAN's
    existing Device and NetworkLink tables without overwriting SIMULATION campus records.
    """

    @staticmethod
    def sync_lab_topology(
        db: Session,
        lab_source: str,
        nodes: List[Dict[str, Any]],
        links: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        seen_ext_ids = set()
        created_devices = 0
        updated_devices = 0
        created_links = 0

        ext_to_device: Dict[str, Device] = {}

        for n in nodes:
            ext_id = f"{lab_source}:{n['external_id']}"
            seen_ext_ids.add(ext_id)
            raw_name = str(n.get("name") or ext_id)[:90]
            status_val = "online" if str(n.get("status", "")).lower() in ("started", "running", "2", "online") else "offline"

            # Never overwrite SIMULATION campus seed devices with same hostname
            existing_sim = db.query(Device).filter(
                Device.hostname == raw_name,
                Device.environment == "SIMULATION",
            ).first()
            hostname = f"LAB-{raw_name}" if existing_sim else raw_name

            dev = db.query(Device).filter(Device.external_source_id == ext_id).first()
            if dev:
                dev.status = status_val
                dev.last_seen = now
                updated_devices += 1
            else:
                dev = Device(
                    hostname=hostname,
                    management_ip=n.get("management_ip") or "127.0.0.1",
                    device_type=n.get("device_type") or "router",
                    vendor="Cisco",
                    model=n.get("model") or f"{lab_source} Virtual Node",
                    os_version="Virtual Lab OS",
                    location=f"{lab_source} Lab",
                    asset_category="lab_virtual",
                    layer="lab",
                    environment="LAB",
                    external_source_id=ext_id,
                    status=status_val,
                    last_seen=now,
                )
                db.add(dev)
                db.flush()
                created_devices += 1
            ext_to_device[str(n["external_id"])] = dev

        # Mark previously synced LAB devices from this source that disappeared as offline
        stale_lab_devs = db.query(Device).filter(
            Device.environment == "LAB",
            Device.external_source_id.like(f"{lab_source}:%"),
        ).all()
        removed_devices = 0
        for d in stale_lab_devs:
            if d.external_source_id not in seen_ext_ids:
                d.status = "offline"
                removed_devices += 1

        # Sync links without duplicating
        for l in links:
            src = ext_to_device.get(str(l.get("source_node_id")))
            dst = ext_to_device.get(str(l.get("target_node_id")))
            if not src or not dst:
                continue
            link_name = f"LAB-{src.hostname}-{dst.hostname}"[:100]
            existing_link = db.query(NetworkLink).filter(NetworkLink.name == link_name).first()
            if not existing_link:
                db.add(NetworkLink(
                    name=link_name,
                    source_device_id=src.id,
                    source_interface_name=l.get("source_port") or "Gi0/0",
                    target_device_id=dst.id,
                    target_interface_name=l.get("target_port") or "Gi0/0",
                    link_type="trunk",
                    status="up" if (src.status == "online" and dst.status == "online") else "down",
                    bandwidth_mbps=1000,
                ))
                created_links += 1

        db.commit()
        return {
            "environment": "LAB",
            "lab_source": lab_source,
            "created_devices": created_devices,
            "updated_devices": updated_devices,
            "removed_or_offline_devices": removed_devices,
            "created_links": created_links,
            "synchronized_at": now.isoformat(),
        }
