import hashlib
from datetime import datetime, timezone
from typing import Dict, List
from sqlalchemy.orm import Session
from app.models import (
    Device,
    NetworkInterface,
    VLAN,
    Route,
    NetworkLink,
    Event,
    Incident,
    Diagnosis,
    RemediationProposal,
    ConfigSnapshot,
    ConfigDrift,
    HealthMetric,
    AuditLog,
    TrainingScenario,
)


CAMPUS_VLANS = [
    {
        "vlan_id": 10,
        "name": "CSE",
        "department": "CSE",
        "subnet": "10.10.10.0/24",
        "gateway_ip": "10.10.10.1",
        "description": "Computer Science & Engineering Department",
    },
    {
        "vlan_id": 20,
        "name": "IT",
        "department": "IT",
        "subnet": "10.10.20.0/24",
        "gateway_ip": "10.10.20.1",
        "description": "Information Technology Department",
    },
    {
        "vlan_id": 30,
        "name": "ECE",
        "department": "ECE",
        "subnet": "10.10.30.0/24",
        "gateway_ip": "10.10.30.1",
        "description": "Electronics & Communication Engineering Department",
    },
]


def _make_mac(prefix_byte: int, index: int) -> str:
    return f"02:{prefix_byte:02x}:00:00:{(index >> 8) & 0xff:02x}:{index & 0xff:02x}"


def seed_campus_network(db: Session, force_reset: bool = False) -> Dict[str, int]:
    """
    Deterministic, idempotent university campus network seeder.
    - Creates exactly 3 departmental VLANs (10 CSE, 20 IT, 30 ECE).
    - Creates 3-tier campus infrastructure (Edge, Core, Distribution, Access, Services, APs).
    - Creates 250 synthetic student endpoint assets distributed across departments.
    - Preserves User and AuditLog records during explicit resets.
    """
    if force_reset:
        db.query(RemediationProposal).delete()
        db.query(Diagnosis).delete()
        db.query(Event).delete()
        db.query(Incident).delete()
        db.query(ConfigDrift).delete()
        db.query(ConfigSnapshot).delete()
        db.query(NetworkLink).delete()
        db.query(NetworkInterface).delete()
        db.query(Route).delete()
        db.query(Device).delete()
        db.query(VLAN).delete()
        db.commit()

    # Check idempotency: if campus core already exists and not force_reset, do not duplicate
    existing_core = db.query(Device).filter(Device.hostname == "SW-CORE-01").first()
    if existing_core and not force_reset:
        return {"vlans": db.query(VLAN).count(), "devices": db.query(Device).count(), "links": db.query(NetworkLink).count()}

    # 1. Seed exactly 3 academic VLANs
    existing_vlans = {v.vlan_id for v in db.query(VLAN).all()}
    for v in CAMPUS_VLANS:
        if v["vlan_id"] not in existing_vlans:
            db.add(VLAN(
                vlan_id=v["vlan_id"],
                name=v["name"],
                department=v["department"],
                subnet=v["subnet"],
                gateway_ip=v["gateway_ip"],
                description=v["description"],
                status="active",
            ))
    db.commit()

    # 2. Infrastructure Devices
    infra_specs = [
        ("RTR-EDGE-01", "10.10.0.1", "router", "Cisco ISR 4451", "Campus-Edge", None, "edge", "infrastructure", 15.2, 41.0),
        ("FW-CAMPUS-01", "10.10.0.2", "firewall", "Cisco Firepower 2130", "Campus-Edge", None, "edge", "infrastructure", 18.4, 48.2),
        ("SW-CORE-01", "10.10.0.10", "l3_switch", "Cisco Catalyst 9500-24Y4C", "Campus-Core", None, "core", "infrastructure", 14.1, 37.5),
        ("SW-DIST-01", "10.10.0.21", "l2_switch", "Cisco Catalyst 9300-48P", "Campus-Distribution", None, "distribution", "infrastructure", 12.3, 33.2),
        ("SW-DIST-02", "10.10.0.22", "l2_switch", "Cisco Catalyst 9300-48P", "Campus-Distribution", None, "distribution", "infrastructure", 11.9, 32.8),
        ("SW-CSE-01", "10.10.10.2", "access_switch", "Cisco Catalyst 9200L-48P", "CSE", 10, "access", "infrastructure", 10.4, 29.5),
        ("SW-CSE-02", "10.10.10.3", "access_switch", "Cisco Catalyst 9200L-48P", "CSE", 10, "access", "infrastructure", 9.8, 28.9),
        ("SW-IT-01", "10.10.20.2", "access_switch", "Cisco Catalyst 9200L-48P", "IT", 20, "access", "infrastructure", 11.2, 31.0),
        ("SW-IT-02", "10.10.20.3", "access_switch", "Cisco Catalyst 9200L-48P", "IT", 20, "access", "infrastructure", 10.8, 30.2),
        ("SW-ECE-01", "10.10.30.2", "access_switch", "Cisco Catalyst 9200L-48P", "ECE", 30, "access", "infrastructure", 9.4, 27.6),
        ("SW-ECE-02", "10.10.30.3", "access_switch", "Cisco Catalyst 9200L-48P", "ECE", 30, "access", "infrastructure", 9.1, 27.1),
        ("SRV-DHCP-01", "10.10.0.51", "server", "Cisco UCS C220 M6", "Shared-Services", None, "services", "server", 19.5, 52.0),
        ("SRV-DNS-01", "10.10.0.52", "server", "Cisco UCS C220 M6", "Shared-Services", None, "services", "server", 12.8, 44.0),
        ("SRV-APP-01", "10.10.0.53", "server", "Cisco UCS C240 M6", "Shared-Services", None, "services", "server", 24.0, 58.3),
        ("SRV-NMS-01", "10.10.0.54", "server", "Cisco UCS C220 M6", "Shared-Services", None, "services", "server", 17.6, 49.4),
        ("AP-CSE-01", "10.10.10.5", "wireless_ap", "Cisco Catalyst 9120AXI", "CSE", 10, "access", "wireless_ap", 8.2, 24.0),
        ("AP-CSE-02", "10.10.10.6", "wireless_ap", "Cisco Catalyst 9120AXI", "CSE", 10, "access", "wireless_ap", 7.9, 23.5),
        ("AP-IT-01", "10.10.20.5", "wireless_ap", "Cisco Catalyst 9120AXI", "IT", 20, "access", "wireless_ap", 9.1, 25.4),
        ("AP-IT-02", "10.10.20.6", "wireless_ap", "Cisco Catalyst 9120AXI", "IT", 20, "access", "wireless_ap", 8.8, 24.9),
        ("AP-ECE-01", "10.10.30.5", "wireless_ap", "Cisco Catalyst 9120AXI", "ECE", 30, "access", "wireless_ap", 7.5, 22.8),
        ("AP-ECE-02", "10.10.30.6", "wireless_ap", "Cisco Catalyst 9120AXI", "ECE", 30, "access", "wireless_ap", 7.3, 22.4),
        # Compatibility lab devices for existing CCNA scenario & demo_runner
        ("HQ-Access-SW-02", "10.10.30.4", "access_switch", "Cisco Catalyst 2960-X", "ECE", 30, "access", "legacy_lab", 8.5, 26.0),
        ("PC-Student-01", "10.10.30.201", "endpoint", "Lab Workstation", "ECE", 30, "endpoint", "legacy_lab", 4.0, 18.0),
        ("PC-Student-02", "10.10.30.202", "endpoint", "Lab Workstation", "ECE", 30, "endpoint", "legacy_lab", 4.0, 18.0),
    ]

    dev_map: Dict[str, Device] = {d.hostname: d for d in db.query(Device).all()}
    mac_counter = 1
    for hostname, ip, dtype, model, dept, vid, layer, cat, cpu, mem in infra_specs:
        if hostname not in dev_map:
            dev = Device(
                hostname=hostname,
                management_ip=ip,
                device_type=dtype,
                vendor="Cisco" if cat != "legacy_lab" or dtype == "access_switch" else "Generic",
                model=model,
                os_version="Cisco IOS-XE 17.9.4" if cat == "infrastructure" else "Linux / Embedded",
                location=f"Campus {layer.title()} - {dept}",
                department=dept,
                vlan_id=vid,
                mac_address=_make_mac(0x0A, mac_counter),
                asset_category=cat,
                layer=layer,
                status="online",
                cpu_percent=cpu,
                memory_percent=mem,
            )
            db.add(dev)
            dev_map[hostname] = dev
        mac_counter += 1
    db.commit()

    # Refresh IDs
    dev_map = {d.hostname: d for d in db.query(Device).all()}

    # Helper to ensure interface
    def ensure_iface(dev: Device, name: str, mode: str, ip: str = None, access_vlan: int = None, allowed_vlans: str = None, is_uplink: bool = False):
        existing = db.query(NetworkInterface).filter(
            NetworkInterface.device_id == dev.id,
            NetworkInterface.name == name,
        ).first()
        if not existing:
            iface = NetworkInterface(
                device_id=dev.id,
                name=name,
                ip_address=ip,
                admin_status="up",
                oper_status="up",
                speed_mbps=10000 if is_uplink else 1000,
                duplex="full",
                mode=mode,
                access_vlan=access_vlan,
                allowed_vlans=allowed_vlans,
                is_uplink=is_uplink,
                bandwidth_utilization_pct=18.5 if is_uplink else 12.0,
            )
            db.add(iface)

    # Core & Distribution & Access Switch Interfaces
    ensure_iface(dev_map["RTR-EDGE-01"], "GigabitEthernet0/0/0", "routed", ip="10.10.0.1", is_uplink=True)
    ensure_iface(dev_map["FW-CAMPUS-01"], "GigabitEthernet0/0", "routed", ip="10.10.0.2", is_uplink=True)
    ensure_iface(dev_map["FW-CAMPUS-01"], "GigabitEthernet0/1", "routed", ip="10.10.0.3")

    ensure_iface(dev_map["SW-CORE-01"], "TenGigabitEthernet1/0/1", "routed", is_uplink=True)
    ensure_iface(dev_map["SW-CORE-01"], "TenGigabitEthernet1/0/2", "trunk", allowed_vlans="10,20,30", is_uplink=True)
    ensure_iface(dev_map["SW-CORE-01"], "TenGigabitEthernet1/0/3", "trunk", allowed_vlans="10,20,30", is_uplink=True)
    for idx in range(4, 8):
        ensure_iface(dev_map["SW-CORE-01"], f"GigabitEthernet1/0/{idx}", "routed")

    ensure_iface(dev_map["SW-DIST-01"], "TenGigabitEthernet1/0/1", "trunk", allowed_vlans="10,20,30", is_uplink=True)
    ensure_iface(dev_map["SW-DIST-01"], "TenGigabitEthernet1/0/2", "trunk", allowed_vlans="10,20,30", is_uplink=True)
    ensure_iface(dev_map["SW-DIST-02"], "TenGigabitEthernet1/0/1", "trunk", allowed_vlans="10,20,30", is_uplink=True)
    ensure_iface(dev_map["SW-DIST-02"], "TenGigabitEthernet1/0/2", "trunk", allowed_vlans="10,20,30", is_uplink=True)

    for sw_name in ["SW-CSE-01", "SW-CSE-02", "SW-IT-01", "SW-IT-02", "SW-ECE-01", "SW-ECE-02", "HQ-Access-SW-02"]:
        ensure_iface(dev_map[sw_name], "GigabitEthernet0/1", "trunk", allowed_vlans="10,20,30", is_uplink=True)
        ensure_iface(dev_map[sw_name], "GigabitEthernet0/2", "access", access_vlan=dev_map[sw_name].vlan_id)

    ensure_iface(dev_map["HQ-Access-SW-02"], "GigabitEthernet0/3", "access", access_vlan=30)

    # Infrastructure Links
    infra_links = [
        ("RTR-EDGE-01", "GigabitEthernet0/0/0", "FW-CAMPUS-01", "GigabitEthernet0/0", "fiber", None, 10000, False),
        ("FW-CAMPUS-01", "GigabitEthernet0/1", "SW-CORE-01", "TenGigabitEthernet1/0/1", "fiber", None, 10000, False),
        ("SW-CORE-01", "TenGigabitEthernet1/0/2", "SW-DIST-01", "TenGigabitEthernet1/0/1", "trunk", "10,20,30", 10000, True),
        ("SW-CORE-01", "TenGigabitEthernet1/0/3", "SW-DIST-02", "TenGigabitEthernet1/0/1", "trunk", "10,20,30", 10000, True),
        ("SW-DIST-01", "TenGigabitEthernet1/0/2", "SW-DIST-02", "TenGigabitEthernet1/0/2", "trunk", "10,20,30", 10000, True),
        ("SW-CORE-01", "GigabitEthernet1/0/4", "SRV-DHCP-01", "eth0", "ethernet", None, 1000, False),
        ("SW-CORE-01", "GigabitEthernet1/0/5", "SRV-DNS-01", "eth0", "ethernet", None, 1000, False),
        ("SW-CORE-01", "GigabitEthernet1/0/6", "SRV-APP-01", "eth0", "ethernet", None, 1000, False),
        ("SW-CORE-01", "GigabitEthernet1/0/7", "SRV-NMS-01", "eth0", "ethernet", None, 1000, False),
        ("SW-DIST-01", "GigabitEthernet1/0/3", "SW-CSE-01", "GigabitEthernet0/1", "trunk", "10,20,30", 1000, False),
        ("SW-DIST-01", "GigabitEthernet1/0/4", "SW-CSE-02", "GigabitEthernet0/1", "trunk", "10,20,30", 1000, False),
        ("SW-DIST-01", "GigabitEthernet1/0/5", "SW-IT-01", "GigabitEthernet0/1", "trunk", "10,20,30", 1000, False),
        ("SW-DIST-02", "GigabitEthernet1/0/3", "SW-IT-02", "GigabitEthernet0/1", "trunk", "10,20,30", 1000, False),
        ("SW-DIST-02", "GigabitEthernet1/0/4", "SW-ECE-01", "GigabitEthernet0/1", "trunk", "10,20,30", 1000, False),
        ("SW-DIST-02", "GigabitEthernet1/0/5", "SW-ECE-02", "GigabitEthernet0/1", "trunk", "10,20,30", 1000, False),
        ("SW-DIST-02", "GigabitEthernet1/0/6", "HQ-Access-SW-02", "GigabitEthernet0/1", "trunk", "10,20,30", 1000, False),
        ("SW-CSE-01", "GigabitEthernet0/2", "AP-CSE-01", "GigabitEthernet0", "ethernet", "10", 1000, False),
        ("SW-CSE-02", "GigabitEthernet0/2", "AP-CSE-02", "GigabitEthernet0", "ethernet", "10", 1000, False),
        ("SW-IT-01", "GigabitEthernet0/2", "AP-IT-01", "GigabitEthernet0", "ethernet", "20", 1000, False),
        ("SW-IT-02", "GigabitEthernet0/2", "AP-IT-02", "GigabitEthernet0", "ethernet", "20", 1000, False),
        ("SW-ECE-01", "GigabitEthernet0/2", "AP-ECE-01", "GigabitEthernet0", "ethernet", "30", 1000, False),
        ("SW-ECE-02", "GigabitEthernet0/2", "AP-ECE-02", "GigabitEthernet0", "ethernet", "30", 1000, False),
        ("HQ-Access-SW-02", "GigabitEthernet0/2", "PC-Student-01", "eth0", "ethernet", "30", 1000, False),
        ("HQ-Access-SW-02", "GigabitEthernet0/3", "PC-Student-02", "eth0", "ethernet", "30", 1000, False),
    ]

    existing_link_names = {l.name for l in db.query(NetworkLink).all()}
    for src_h, src_i, tgt_h, tgt_i, ltype, vlans_str, bw, red in infra_links:
        lname = f"{src_h} -> {tgt_h}"
        if lname not in existing_link_names:
            db.add(NetworkLink(
                name=lname,
                source_device_id=dev_map[src_h].id,
                source_interface_name=src_i,
                target_device_id=dev_map[tgt_h].id,
                target_interface_name=tgt_i,
                link_type=ltype,
                admin_status="up",
                status="up",
                bandwidth_mbps=bw,
                duplex="full",
                allowed_vlans=vlans_str,
                utilization_pct=15.0 if ltype == "trunk" else 10.0,
                is_redundant=red,
            ))
            existing_link_names.add(lname)
    db.commit()

    # 3. 250 Synthetic Student Endpoint Assets (80 CSE, 100 IT, 70 ECE)
    dept_configs = [
        ("CSE", 10, "10.10.10", 0x10, 80, ["SW-CSE-01", "SW-CSE-02"]),
        ("IT", 20, "10.10.20", 0x20, 100, ["SW-IT-01", "SW-IT-02"]),
        ("ECE", 30, "10.10.30", 0x30, 70, ["SW-ECE-01", "SW-ECE-02"]),
    ]

    new_endpoints: List[Device] = []
    endpoint_assignments = []
    for dept, vid, ip_prefix, mac_prefix, count, switches in dept_configs:
        half = count // 2
        for idx in range(1, count + 1):
            hostname = f"{dept}-PC-{idx:03d}"
            if hostname in dev_map:
                continue
            sw_name = switches[0] if idx <= half else switches[1]
            port_num = idx if idx <= half else (idx - half)
            sw_iface = f"GigabitEthernet1/0/{port_num}"
            sw_dev = dev_map[sw_name]
            ip_addr = f"{ip_prefix}.{10 + idx}"
            mac_addr = _make_mac(mac_prefix, idx)

            ep = Device(
                hostname=hostname,
                management_ip=ip_addr,
                device_type="endpoint",
                vendor="Dell",
                model="OptiPlex 7010",
                os_version="Ubuntu 24.04 LTS",
                location=f"{dept} Lab - {sw_name}",
                department=dept,
                vlan_id=vid,
                mac_address=mac_addr,
                connected_switch_id=sw_dev.id,
                connected_interface=sw_iface,
                asset_category="student_endpoint",
                layer="endpoint",
                status="online",
                cpu_percent=8.0,
                memory_percent=24.0,
            )
            new_endpoints.append(ep)
            endpoint_assignments.append((hostname, sw_dev.id, sw_iface, str(vid)))

    if new_endpoints:
        db.add_all(new_endpoints)
        db.commit()
        for ep in new_endpoints:
            dev_map[ep.hostname] = ep

    new_links: List[NetworkLink] = []
    for hostname, sw_id, sw_iface, vid_str in endpoint_assignments:
        lname = f"{hostname} -> {sw_iface}"
        if lname not in existing_link_names:
            new_links.append(NetworkLink(
                name=lname,
                source_device_id=sw_id,
                source_interface_name=sw_iface,
                target_device_id=dev_map[hostname].id,
                target_interface_name="eth0",
                link_type="ethernet",
                admin_status="up",
                status="up",
                bandwidth_mbps=1000,
                duplex="full",
                allowed_vlans=vid_str,
                utilization_pct=6.5,
                is_redundant=False,
            ))
    if new_links:
        db.add_all(new_links)
        db.commit()

    # 4. Baseline Config Snapshots for switches
    for sw_name in ["SW-CORE-01", "SW-DIST-01", "SW-DIST-02", "SW-CSE-01", "SW-CSE-02", "SW-IT-01", "SW-IT-02", "SW-ECE-01", "SW-ECE-02", "HQ-Access-SW-02"]:
        dev = dev_map[sw_name]
        has_snap = db.query(ConfigSnapshot).filter(ConfigSnapshot.device_id == dev.id).first()
        if not has_snap:
            cfg = (
                f"!\nhostname {dev.hostname}\n!\n"
                f"interface GigabitEthernet0/1\n"
                f" switchport mode trunk\n"
                f" switchport trunk allowed vlan 10,20,30\n!\nend\n"
            )
            db.add(ConfigSnapshot(
                device_id=dev.id,
                config_type="baseline",
                content=cfg,
                content_hash=hashlib.sha256(cfg.encode("utf-8")).hexdigest(),
            ))
    db.commit()

    # 5. Ensure CCNA Training Scenarios & Initial HealthMetric exist
    if not db.query(TrainingScenario).first():
        db.add_all([
            TrainingScenario(
                scenario_key="vlan_30_trunk_missing",
                title="ECE VLAN 30 Pruned from Access Trunk",
                difficulty="Intermediate",
                category="VLAN & Trunking",
                description="VLAN 30 was accidentally removed from GigabitEthernet0/1 trunk allowed list, isolating ECE lab workstations.",
                fault_type="VLAN_TRUNK_PRUNED",
                target_device="HQ-Access-SW-02",
                target_component="GigabitEthernet0/1",
                symptoms=[
                    "ECE lab workstations cannot ping gateway 10.10.30.1",
                    "802.1Q trunk allowed list excludes VLAN 30"
                ],
                expected_root_cause="VLAN 30 missing from HQ-Access-SW-02 trunk port GigabitEthernet0/1 allowed VLAN list.",
                recommended_commands="interface GigabitEthernet0/1\n switchport trunk allowed vlan add 30",
            ),
            TrainingScenario(
                scenario_key="interface_shutdown",
                title="Access Switch Uplink Administratively Down",
                difficulty="Beginner",
                category="Interfaces",
                description="An access switch uplink was administratively shut down.",
                fault_type="INTERFACE_SHUTDOWN",
                target_device="SW-CSE-01",
                target_component="GigabitEthernet0/1",
                symptoms=["Switch uplink carrier down", "CSE hosts unreachable"],
                expected_root_cause="Interface GigabitEthernet0/1 administratively down.",
                recommended_commands="interface GigabitEthernet0/1\n no shutdown",
            ),
            TrainingScenario(
                scenario_key="dhcp_server_down",
                title="Campus DHCP Server Unreachable",
                difficulty="Intermediate",
                category="IP Services",
                description="SRV-DHCP-01 service stopped responding to client DHCPDISCOVER broadcasts.",
                fault_type="DHCP_FAILURE",
                target_device="SRV-DHCP-01",
                target_component="eth0",
                symptoms=["New endpoints receive APIPA 169.254.x.x", "DHCP pool exhaustion alerts"],
                expected_root_cause="SRV-DHCP-01 service unreachable or link down.",
                recommended_commands="interface GigabitEthernet1/0/4\n no shutdown",
            ),
            TrainingScenario(
                scenario_key="uplink_congestion",
                title="Distribution Uplink Bandwidth Saturation",
                difficulty="Intermediate",
                category="Performance",
                description="Distribution-to-Core trunk link experiencing >95% utilization and packet drops.",
                fault_type="LINK_CONGESTION",
                target_device="SW-DIST-01",
                target_component="TenGigabitEthernet1/0/1",
                symptoms=["High latency > 120ms", "Output queue drops on trunk"],
                expected_root_cause="Bandwidth saturation on SW-DIST-01 uplink TenGigabitEthernet1/0/1.",
                recommended_commands="interface TenGigabitEthernet1/0/1\n no shutdown",
            ),
            TrainingScenario(
                scenario_key="acl_misconfiguration",
                title="Extended ACL Blocking Department Server Traffic",
                difficulty="Advanced",
                category="Security / ACL",
                description="Extended ACL applied inbound on SVI blocks ECE subnet traffic to application server.",
                fault_type="ACL_BLOCK",
                target_device="SW-CORE-01",
                target_component="Vlan30",
                symptoms=["TCP connections to SRV-APP-01 time out", "Implicit deny counters incrementing"],
                expected_root_cause="Extended ACL denies traffic from 10.10.30.0/24 to 10.10.0.53.",
                recommended_commands="interface Vlan30\n no shutdown",
            ),
        ])
        db.commit()

    if not db.query(HealthMetric).first():
        total_devs = db.query(Device).count()
        db.add(HealthMetric(
            overall_health=96.5,
            availability=100.0,
            performance=95.0,
            configuration=96.0,
            security=95.0,
            redundancy=94.0,
            risk_score=3.5,
            active_incidents=0,
            total_devices=total_devs,
            online_devices=total_devs,
            avg_latency_ms=1.2,
            avg_packet_loss_pct=0.0,
        ))
        db.commit()

    return {
        "vlans": db.query(VLAN).count(),
        "devices": db.query(Device).count(),
        "links": db.query(NetworkLink).count(),
    }
