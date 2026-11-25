import ipaddress
from collections import defaultdict
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.models import Device, NetworkInterface, NetworkLink, VLAN


class TopologyValidationEngine:
    """
    Read-only Campus Topology & VLAN Validation Engine.
    Detects disconnected devices, missing uplinks, invalid link references,
    duplicate IPs/MACs, invalid VLAN references, overlapping subnets,
    invalid gateways, VLAN-department mismatches, and subnet placement errors.
    Never modifies network configuration during validation.
    """

    @staticmethod
    def validate_new_vlan(
        db: Session,
        vlan_id: int,
        subnet: str,
        gateway_ip: str,
    ) -> None:
        if vlan_id < 1 or vlan_id > 4094:
            raise ValueError(f"VLAN ID {vlan_id} must be between 1 and 4094.")

        try:
            net = ipaddress.ip_network(subnet, strict=False)
        except ValueError as e:
            raise ValueError(f"Invalid subnet CIDR '{subnet}': {e}")

        try:
            gw = ipaddress.ip_address(gateway_ip)
        except ValueError as e:
            raise ValueError(f"Invalid gateway IP '{gateway_ip}': {e}")

        if gw not in net or gw == net.network_address or gw == net.broadcast_address:
            raise ValueError(f"Gateway '{gateway_ip}' must be a valid host address inside '{subnet}'.")

        existing_vlans = db.query(VLAN).all()
        for v in existing_vlans:
            if v.vlan_id == vlan_id:
                raise ValueError(f"VLAN ID {vlan_id} already exists.")
            try:
                other_net = ipaddress.ip_network(v.subnet, strict=False)
                if net.overlaps(other_net):
                    raise ValueError(
                        f"Subnet '{subnet}' overlaps with existing VLAN {v.vlan_id} ({v.subnet})."
                    )
            except ValueError as inner:
                if "overlaps" in str(inner):
                    raise

    @staticmethod
    def validate_new_link(
        db: Session,
        source_device_id: str,
        source_interface_name: str,
        target_device_id: str,
        target_interface_name: str,
        allowed_vlans: Optional[str] = None,
    ) -> None:
        if source_device_id == target_device_id:
            raise ValueError("Self-links are not permitted.")

        src = db.query(Device).filter(Device.id == source_device_id).first()
        tgt = db.query(Device).filter(Device.id == target_device_id).first()
        if not src or not tgt:
            raise ValueError("Both source_device_id and target_device_id must reference existing devices.")

        dup = (
            db.query(NetworkLink)
            .filter(
                (
                    (NetworkLink.source_device_id == source_device_id)
                    & (NetworkLink.source_interface_name == source_interface_name)
                    & (NetworkLink.target_device_id == target_device_id)
                    & (NetworkLink.target_interface_name == target_interface_name)
                )
                | (
                    (NetworkLink.source_device_id == target_device_id)
                    & (NetworkLink.source_interface_name == target_interface_name)
                    & (NetworkLink.target_device_id == source_device_id)
                    & (NetworkLink.target_interface_name == source_interface_name)
                )
            )
            .first()
        )
        if dup:
            raise ValueError("Duplicate network link between the specified device interfaces.")

        if allowed_vlans:
            valid_vlan_ids = {v.vlan_id for v in db.query(VLAN).all()}
            for raw in allowed_vlans.split(","):
                tok = raw.strip()
                if not tok:
                    continue
                if not tok.isdigit() or int(tok) not in valid_vlan_ids:
                    raise ValueError(f"Link references undefined VLAN '{tok}'.")

    @staticmethod
    def validate_topology(db: Session) -> Dict[str, Any]:
        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        devices = db.query(Device).all()
        interfaces = db.query(NetworkInterface).all()
        links = db.query(NetworkLink).all()
        vlans = db.query(VLAN).all()

        device_by_id = {d.id: d for d in devices}
        vlan_by_id = {v.vlan_id: v for v in vlans}
        valid_vlan_ids = set(vlan_by_id.keys())

        # 1. Validate VLANs (subnets, gateways, overlaps)
        parsed_nets: Dict[int, ipaddress.IPv4Network] = {}
        for v in vlans:
            if v.vlan_id < 1 or v.vlan_id > 4094:
                errors.append({"code": "INVALID_VLAN_ID", "message": f"VLAN {v.vlan_id} out of range.", "resource": f"VLAN {v.vlan_id}"})
                continue
            try:
                net = ipaddress.ip_network(v.subnet, strict=False)
                parsed_nets[v.vlan_id] = net
                gw = ipaddress.ip_address(v.gateway_ip)
                if gw not in net or gw == net.network_address or gw == net.broadcast_address:
                    errors.append({
                        "code": "INVALID_GATEWAY",
                        "message": f"VLAN {v.vlan_id} gateway {v.gateway_ip} is not a valid host in {v.subnet}.",
                        "resource": f"VLAN {v.vlan_id}",
                    })
            except ValueError as e:
                errors.append({
                    "code": "INVALID_SUBNET_OR_GATEWAY",
                    "message": f"VLAN {v.vlan_id} invalid subnet/gateway: {e}",
                    "resource": f"VLAN {v.vlan_id}",
                })

        vlan_list = list(parsed_nets.items())
        for i in range(len(vlan_list)):
            vid_a, net_a = vlan_list[i]
            for j in range(i + 1, len(vlan_list)):
                vid_b, net_b = vlan_list[j]
                if net_a.overlaps(net_b):
                    errors.append({
                        "code": "OVERLAPPING_SUBNETS",
                        "message": f"VLAN {vid_a} ({net_a}) overlaps with VLAN {vid_b} ({net_b}).",
                        "resource": f"VLAN {vid_a} / VLAN {vid_b}",
                    })

        # 2. Validate duplicate IPs and MACs
        ip_owners: Dict[str, List[str]] = defaultdict(list)
        mac_owners: Dict[str, List[str]] = defaultdict(list)
        for d in devices:
            if d.management_ip:
                ip_owners[d.management_ip].append(d.hostname)
            if d.mac_address:
                mac_owners[d.mac_address.lower()].append(d.hostname)

        for ip, owners in ip_owners.items():
            if len(owners) > 1:
                errors.append({
                    "code": "DUPLICATE_IP",
                    "message": f"IP address {ip} assigned to multiple devices: {', '.join(owners)}.",
                    "resource": ip,
                })

        for mac, owners in mac_owners.items():
            if len(owners) > 1:
                errors.append({
                    "code": "DUPLICATE_MAC",
                    "message": f"MAC address {mac} assigned to multiple devices: {', '.join(owners)}.",
                    "resource": mac,
                })

        # 3. Validate links (self-links, nonexistent devices, duplicates, undefined VLANs)
        connected_device_ids = set()
        seen_link_pairs = set()
        ifaces_by_device: Dict[str, Dict[str, NetworkInterface]] = defaultdict(dict)
        for iface in interfaces:
            ifaces_by_device[iface.device_id][iface.name] = iface

        for l in links:
            if l.source_device_id == l.target_device_id:
                errors.append({
                    "code": "SELF_LINK",
                    "message": f"Link '{l.name}' connects device '{l.source_device_id}' to itself.",
                    "resource": l.name,
                })
            if l.source_device_id not in device_by_id or l.target_device_id not in device_by_id:
                errors.append({
                    "code": "INVALID_LINK_REFERENCE",
                    "message": f"Link '{l.name}' references a nonexistent device.",
                    "resource": l.name,
                })
                continue

            connected_device_ids.add(l.source_device_id)
            connected_device_ids.add(l.target_device_id)

            pair = tuple(sorted([
                (l.source_device_id, l.source_interface_name),
                (l.target_device_id, l.target_interface_name),
            ]))
            if pair in seen_link_pairs:
                warnings.append({
                    "code": "DUPLICATE_LINK",
                    "message": f"Duplicate link detected: '{l.name}'.",
                    "resource": l.name,
                })
            seen_link_pairs.add(pair)

            if l.allowed_vlans:
                for tok in [x.strip() for x in l.allowed_vlans.split(",") if x.strip()]:
                    if not tok.isdigit() or int(tok) not in valid_vlan_ids:
                        errors.append({
                            "code": "UNDEFINED_VLAN_ON_LINK",
                            "message": f"Link '{l.name}' references undefined VLAN '{tok}'.",
                            "resource": l.name,
                        })

        # 4. Disconnected devices & missing uplinks
        for d in devices:
            if d.id not in connected_device_ids:
                errors.append({
                    "code": "DISCONNECTED_DEVICE",
                    "message": f"Device '{d.hostname}' has no network links.",
                    "resource": d.hostname,
                })
            if d.device_type in {"access_switch", "l2_switch"}:
                dev_ifaces = list(ifaces_by_device[d.id].values())
                has_uplink = any(i.is_uplink or i.mode == "trunk" for i in dev_ifaces)
                if not has_uplink:
                    warnings.append({
                        "code": "MISSING_UPLINK",
                        "message": f"Switch '{d.hostname}' has no configured uplink trunk interface.",
                        "resource": d.hostname,
                    })

        # 5. Interface VLAN references & trunk checks
        for iface in interfaces:
            dev = device_by_id.get(iface.device_id)
            dname = dev.hostname if dev else iface.device_id
            if iface.access_vlan is not None and iface.access_vlan not in valid_vlan_ids:
                errors.append({
                    "code": "INVALID_ACCESS_VLAN",
                    "message": f"Interface {dname}:{iface.name} references undefined access VLAN {iface.access_vlan}.",
                    "resource": f"{dname}:{iface.name}",
                })
            if iface.mode == "trunk" and iface.allowed_vlans:
                allowed = [x.strip() for x in iface.allowed_vlans.split(",") if x.strip()]
                for tok in allowed:
                    if not tok.isdigit() or int(tok) not in valid_vlan_ids:
                        errors.append({
                            "code": "UNDEFINED_TRUNK_VLAN",
                            "message": f"Trunk {dname}:{iface.name} claims undefined VLAN '{tok}'.",
                            "resource": f"{dname}:{iface.name}",
                        })
                # Check if departmental access switch trunk is missing its department VLAN
                if dev and dev.vlan_id and str(dev.vlan_id) not in allowed:
                    errors.append({
                        "code": "TRUNK_MISSING_REQUIRED_VLAN",
                        "message": f"Trunk {dname}:{iface.name} is missing departmental VLAN {dev.vlan_id}.",
                        "resource": f"{dname}:{iface.name}",
                    })

        # 6. Endpoint VLAN, department, and subnet consistency
        for d in devices:
            if d.asset_category == "student_endpoint" or d.device_type == "endpoint":
                if d.vlan_id is None or d.vlan_id not in valid_vlan_ids:
                    errors.append({
                        "code": "ENDPOINT_INVALID_VLAN",
                        "message": f"Endpoint '{d.hostname}' has invalid or missing VLAN '{d.vlan_id}'.",
                        "resource": d.hostname,
                    })
                    continue

                vlan_obj = vlan_by_id[d.vlan_id]
                if d.department and vlan_obj.department and d.department != vlan_obj.department:
                    errors.append({
                        "code": "VLAN_DEPARTMENT_MISMATCH",
                        "message": f"Endpoint '{d.hostname}' department '{d.department}' does not match VLAN {d.vlan_id} department '{vlan_obj.department}'.",
                        "resource": d.hostname,
                    })

                if d.vlan_id in parsed_nets and d.management_ip:
                    try:
                        ip_obj = ipaddress.ip_address(d.management_ip)
                        if ip_obj not in parsed_nets[d.vlan_id]:
                            errors.append({
                                "code": "ENDPOINT_WRONG_SUBNET",
                                "message": f"Endpoint '{d.hostname}' IP {d.management_ip} is outside VLAN {d.vlan_id} subnet {vlan_obj.subnet}.",
                                "resource": d.hostname,
                            })
                    except ValueError:
                        errors.append({
                            "code": "ENDPOINT_INVALID_IP",
                            "message": f"Endpoint '{d.hostname}' has invalid IP '{d.management_ip}'.",
                            "resource": d.hostname,
                        })

                if d.connected_switch_id and d.connected_switch_id not in device_by_id:
                    errors.append({
                        "code": "ENDPOINT_INVALID_SWITCH",
                        "message": f"Endpoint '{d.hostname}' references nonexistent switch '{d.connected_switch_id}'.",
                        "resource": d.hostname,
                    })

        return {
            "valid": len(errors) == 0,
            "summary": {
                "critical_errors": len(errors),
                "warnings": len(warnings),
                "devices_checked": len(devices),
                "links_checked": len(links),
                "vlans_checked": len(vlans),
            },
            "errors": errors,
            "warnings": warnings,
        }
