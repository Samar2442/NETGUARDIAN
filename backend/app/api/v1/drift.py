from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from app.database.session import get_db
from app.models import Device, ConfigSnapshot, ConfigDrift
from app.engines.drift.drift_engine import ConfigDriftEngine

router = APIRouter(prefix="/drift", tags=["Configuration Drift"])

@router.get("/compare/{device_id}")
def compare_device_config(device_id: str, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    baseline = db.query(ConfigSnapshot).filter(
        ConfigSnapshot.device_id == device_id,
        ConfigSnapshot.config_type == "baseline"
    ).order_by(ConfigSnapshot.created_at.desc()).first()

    # Generate current running-config representation
    current_lines = [
        "!",
        f"hostname {device.hostname}",
        "!"
    ]
    for iface in device.interfaces:
        current_lines.append(f"interface {iface.name}")
        if iface.description:
            current_lines.append(f" description {iface.description}")
        if iface.mode == "trunk":
            current_lines.append(" switchport mode trunk")
            current_lines.append(f" switchport trunk allowed vlan {iface.allowed_vlans}")
        elif iface.mode == "access":
            current_lines.append(" switchport mode access")
            current_lines.append(f" switchport access vlan {iface.access_vlan}")
        if iface.admin_status == "down":
            current_lines.append(" shutdown")
        current_lines.append("!")
    current_lines.append("end")

    current_text = "\n".join(current_lines)
    baseline_text = baseline.content if baseline else current_text

    comparison = ConfigDriftEngine.compare_configs(baseline_text, current_text)
    return {
        "device_id": device_id,
        "hostname": device.hostname,
        "has_baseline": baseline is not None,
        "comparison": comparison,
        "current_config": current_text,
        "baseline_config": baseline_text
    }
