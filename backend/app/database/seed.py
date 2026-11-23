import sys
from datetime import datetime, timezone, timedelta
from app.database.session import engine, SessionLocal, Base
from app.models import (
    User, Device, NetworkInterface, VLAN, Route, NetworkLink,
    Event, Incident, Diagnosis, RemediationProposal, ConfigSnapshot,
    ConfigDrift, HealthMetric, AuditLog, TrainingScenario, TrainingSession
)
from app.core.security import get_password_hash

def seed_database(db=None):
    import os, secrets
    from app.core.config import settings

    def resolve_password(env_var: str, role_desc: str) -> str:
        """Return a hashed password.
        In DEMO mode a random password is generated when the env var is absent.
        In production the env var is mandatory – missing results in a clear error.
        """
        raw = os.getenv(env_var)
        if raw:
            return get_password_hash(raw)
        if settings.DEMO_MODE:
            # generate a temporary random password for local dev; do NOT log it
            generated = secrets.token_urlsafe(12)
            return get_password_hash(generated)
        raise RuntimeError(f"Missing required environment variable {env_var} for {role_desc} user creation")
    close_at_end = False
    if db is None:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        close_at_end = True

    try:
        # Check if already seeded
        if db.query(User).first():
            print("[i] Database already contains records. Skipping seed.")
            return

        print("[*] Seeding default users (DEMO ENVIRONMENT)...")
        users = [
            User(
                username="admin",
                email="admin@netguardian.saturnx.local",
                hashed_password=resolve_password("ADMIN_PASSWORD", "admin"),
                role="admin",
                is_active=True
            ),
            User(
                username="neteng",
                email="engineer@netguardian.saturnx.local",
                hashed_password=resolve_password("ENGINEER_PASSWORD", "network_engineer"),
                role="network_engineer",
                is_active=True
            ),
            User(
                username="auditor",
                email="auditor@netguardian.saturnx.local",
                hashed_password=resolve_password("VIEWER_PASSWORD", "viewer"),
                role="viewer",
                is_active=True
            ),
        ]
        db.add_all(users)
        db.commit()

        print("[*] Seeding VLANs...")
        vlans = [
            VLAN(vlan_id=1, name="default", subnet="10.0.1.0/24", gateway_ip="10.0.1.1", description="Default Management VLAN"),
            VLAN(vlan_id=10, name="Administration", subnet="10.0.10.0/24", gateway_ip="10.0.10.1", description="Corporate Executive & Admin"),
            VLAN(vlan_id=20, name="Engineering-Servers", subnet="10.0.20.0/24", gateway_ip="10.0.20.1", description="Data Center & Developers"),
            VLAN(vlan_id=30, name="Student-Lab", subnet="10.0.30.0/24", gateway_ip="10.0.30.1", description="Academy Student Training Lab"),
            VLAN(vlan_id=99, name="Voice-IoT", subnet="10.0.99.0/24", gateway_ip="10.0.99.1", description="VoIP & IoT Devices"),
        ]
        db.add_all(vlans)
        db.commit()

        print("[*] Seeding Cisco Devices...")
        devices_data = [
            {
                "hostname": "HQ-Core-RTR-01",
                "management_ip": "10.0.1.1",
                "device_type": "router",
                "model": "Cisco ISR 4451",
                "os_version": "Cisco IOS-XE 17.6.4",
                "location": "HQ Datacenter - Rack A1",
                "status": "online",
                "cpu": 16.4,
                "mem": 42.1,
            },
            {
                "hostname": "HQ-Core-SW-01",
                "management_ip": "10.0.1.2",
                "device_type": "l3_switch",
                "model": "Cisco Catalyst 3850-24T L3",
                "os_version": "Cisco IOS-XE 17.6.4",
                "location": "HQ Datacenter - Rack A2",
                "status": "online",
                "cpu": 14.8,
                "mem": 36.5,
            },
            {
                "hostname": "HQ-Dist-SW-01",
                "management_ip": "10.0.1.3",
                "device_type": "l2_switch",
                "model": "Cisco Catalyst 3850-48P",
                "os_version": "Cisco IOS-XE 17.6.4",
                "location": "HQ Datacenter - Rack B1",
                "status": "online",
                "cpu": 12.0,
                "mem": 32.8,
            },
            {
                "hostname": "HQ-Access-SW-01",
                "management_ip": "10.0.1.11",
                "device_type": "access_switch",
                "model": "Cisco Catalyst 2960-X",
                "os_version": "Cisco IOS 15.2(7)E",
                "location": "Building 1 - Floor 2 IDF",
                "status": "online",
                "cpu": 9.2,
                "mem": 28.4,
            },
            {
                "hostname": "HQ-Access-SW-02",
                "management_ip": "10.0.1.12",
                "device_type": "access_switch",
                "model": "Cisco Catalyst 2960-X",
                "os_version": "Cisco IOS 15.2(7)E",
                "location": "Building 1 - Student Lab IDF",
                "status": "online",
                "cpu": 11.5,
                "mem": 30.1,
            },
            {
                "hostname": "HQ-DC-SRV-APP01",
                "management_ip": "10.0.20.10",
                "device_type": "server",
                "model": "Cisco UCS C220 M5",
                "os_version": "Ubuntu 24.04 LTS",
                "location": "HQ Datacenter - Rack C1",
                "status": "online",
                "cpu": 25.0,
                "mem": 58.0,
            },
            {
                "hostname": "HQ-DC-SRV-DB01",
                "management_ip": "10.0.20.20",
                "device_type": "server",
                "model": "Cisco UCS C240 M5",
                "os_version": "Ubuntu 24.04 LTS",
                "location": "HQ Datacenter - Rack C2",
                "status": "online",
                "cpu": 32.4,
                "mem": 64.2,
            },
            {
                "hostname": "HQ-DC-SRV-DHCP",
                "management_ip": "10.0.20.5",
                "device_type": "server",
                "model": "Virtual Appliance",
                "os_version": "Debian 12",
                "location": "HQ Datacenter - Hypervisor 01",
                "status": "online",
                "cpu": 8.0,
                "mem": 21.0,
            },
            {
                "hostname": "PC-Admin-01",
                "management_ip": "10.0.10.101",
                "device_type": "endpoint",
                "model": "Workstation Dell OptiPlex",
                "os_version": "Windows 11 Enterprise",
                "location": "Building 1 - Exec Suite",
                "status": "online",
                "cpu": 15.0,
                "mem": 40.0,
            },
            {
                "hostname": "PC-Student-01",
                "management_ip": "10.0.30.101",
                "device_type": "endpoint",
                "model": "Lab Workstation",
                "os_version": "Ubuntu Desktop 24.04",
                "location": "Lab 3 - Seat 01",
                "status": "online",
                "cpu": 18.0,
                "mem": 35.0,
            },
            {
                "hostname": "PC-Student-02",
                "management_ip": "10.0.30.102",
                "device_type": "endpoint",
                "model": "Lab Workstation",
                "os_version": "Ubuntu Desktop 24.04",
                "location": "Lab 3 - Seat 02",
                "status": "online",
                "cpu": 14.0,
                "mem": 32.0,
            },
        ]

        device_map = {}
        for d in devices_data:
            dev = Device(
                hostname=d["hostname"],
                management_ip=d["management_ip"],
                device_type=d["device_type"],
                vendor="Cisco" if "PC" not in d["hostname"] and "SRV" not in d["hostname"] else ("Dell" if "PC" in d["hostname"] else "Cisco UCS"),
                model=d["model"],
                os_version=d["os_version"],
                location=d["location"],
                status=d["status"],
                monitoring_status="active",
                uptime_seconds=864000,
                cpu_percent=d["cpu"],
                memory_percent=d["mem"],
            )
            db.add(dev)
            db.flush()
            device_map[dev.hostname] = dev

        db.commit()

        print("[*] Seeding Interfaces...")
        interfaces = [
            # HQ-Core-RTR-01
            NetworkInterface(
                device_id=device_map["HQ-Core-RTR-01"].id,
                name="GigabitEthernet0/0/0",
                ip_address="192.168.100.1",
                subnet_mask="255.255.255.252",
                admin_status="up",
                oper_status="up",
                speed_mbps=1000,
                mode="routed",
                description="Uplink to Core Switch Te1/1/1",
                is_uplink=True,
                bandwidth_utilization_pct=18.5,
            ),
            NetworkInterface(
                device_id=device_map["HQ-Core-RTR-01"].id,
                name="GigabitEthernet0/0/1",
                ip_address="203.0.113.2",
                subnet_mask="255.255.255.248",
                admin_status="up",
                oper_status="up",
                speed_mbps=1000,
                mode="routed",
                description="WAN Gateway to ISP-1",
                bandwidth_utilization_pct=42.0,
            ),

            # HQ-Core-SW-01 (L3 Switch)
            NetworkInterface(
                device_id=device_map["HQ-Core-SW-01"].id,
                name="TenGigabitEthernet1/1/1",
                ip_address="192.168.100.2",
                subnet_mask="255.255.255.252",
                admin_status="up",
                oper_status="up",
                speed_mbps=10000,
                mode="routed",
                description="Link to HQ-Core-RTR-01 Gi0/0/0",
                bandwidth_utilization_pct=18.5,
            ),
            NetworkInterface(
                device_id=device_map["HQ-Core-SW-01"].id,
                name="TenGigabitEthernet1/1/2",
                admin_status="up",
                oper_status="up",
                speed_mbps=10000,
                mode="trunk",
                allowed_vlans="1,10,20,30,99",
                native_vlan=1,
                description="Trunk to Dist Switch Gi1/0/1",
                is_uplink=True,
                bandwidth_utilization_pct=34.2,
            ),
            NetworkInterface(
                device_id=device_map["HQ-Core-SW-01"].id,
                name="Vlan10",
                ip_address="10.0.10.1",
                subnet_mask="255.255.255.0",
                admin_status="up",
                oper_status="up",
                mode="routed",
                description="SVI Default Gateway VLAN 10",
            ),
            NetworkInterface(
                device_id=device_map["HQ-Core-SW-01"].id,
                name="Vlan20",
                ip_address="10.0.20.1",
                subnet_mask="255.255.255.0",
                admin_status="up",
                oper_status="up",
                mode="routed",
                description="SVI Default Gateway VLAN 20",
            ),
            NetworkInterface(
                device_id=device_map["HQ-Core-SW-01"].id,
                name="Vlan30",
                ip_address="10.0.30.1",
                subnet_mask="255.255.255.0",
                admin_status="up",
                oper_status="up",
                mode="routed",
                description="SVI Default Gateway VLAN 30 (Student Lab)",
            ),

            # HQ-Dist-SW-01
            NetworkInterface(
                device_id=device_map["HQ-Dist-SW-01"].id,
                name="GigabitEthernet1/0/1",
                admin_status="up",
                oper_status="up",
                speed_mbps=10000,
                mode="trunk",
                allowed_vlans="1,10,20,30,99",
                native_vlan=1,
                description="Trunk Uplink to HQ-Core-SW-01",
                is_uplink=True,
                bandwidth_utilization_pct=34.2,
            ),
            NetworkInterface(
                device_id=device_map["HQ-Dist-SW-01"].id,
                name="GigabitEthernet1/0/11",
                admin_status="up",
                oper_status="up",
                speed_mbps=1000,
                mode="trunk",
                allowed_vlans="1,10,20,30,99",
                native_vlan=1,
                description="Trunk Downlink to HQ-Access-SW-01 Gi0/1",
                bandwidth_utilization_pct=15.0,
            ),
            NetworkInterface(
                device_id=device_map["HQ-Dist-SW-01"].id,
                name="GigabitEthernet1/0/12",
                admin_status="up",
                oper_status="up",
                speed_mbps=1000,
                mode="trunk",
                allowed_vlans="1,10,20,30,99",
                native_vlan=1,
                description="Trunk Downlink to HQ-Access-SW-02 Gi0/1",
                bandwidth_utilization_pct=21.0,
            ),

            # HQ-Access-SW-01
            NetworkInterface(
                device_id=device_map["HQ-Access-SW-01"].id,
                name="GigabitEthernet0/1",
                admin_status="up",
                oper_status="up",
                speed_mbps=1000,
                mode="trunk",
                allowed_vlans="1,10,20,30,99",
                native_vlan=1,
                description="Trunk Uplink to HQ-Dist-SW-01 Gi1/0/11",
                is_uplink=True,
                bandwidth_utilization_pct=15.0,
            ),
            NetworkInterface(
                device_id=device_map["HQ-Access-SW-01"].id,
                name="FastEthernet0/1",
                admin_status="up",
                oper_status="up",
                speed_mbps=100,
                mode="access",
                access_vlan=10,
                description="Access port to PC-Admin-01",
                bandwidth_utilization_pct=5.2,
            ),

            # HQ-Access-SW-02 (THE CRITICAL ACCESS SWITCH FOR VLAN 30)
            NetworkInterface(
                device_id=device_map["HQ-Access-SW-02"].id,
                name="GigabitEthernet0/1",
                admin_status="up",
                oper_status="up",
                speed_mbps=1000,
                mode="trunk",
                allowed_vlans="1,10,20,30,99",  # HEALTHY BASELINE! When injected, 30 will be removed!
                native_vlan=1,
                description="Trunk Uplink to HQ-Dist-SW-01 Gi1/0/12",
                is_uplink=True,
                bandwidth_utilization_pct=21.0,
            ),
            NetworkInterface(
                device_id=device_map["HQ-Access-SW-02"].id,
                name="FastEthernet0/1",
                admin_status="up",
                oper_status="up",
                speed_mbps=100,
                mode="access",
                access_vlan=30,
                description="Access Port - PC-Student-01",
                bandwidth_utilization_pct=8.4,
            ),
            NetworkInterface(
                device_id=device_map["HQ-Access-SW-02"].id,
                name="FastEthernet0/2",
                admin_status="up",
                oper_status="up",
                speed_mbps=100,
                mode="access",
                access_vlan=30,
                description="Access Port - PC-Student-02",
                bandwidth_utilization_pct=6.1,
            ),

            # HQ-DC-SRV-APP01
            NetworkInterface(
                device_id=device_map["HQ-DC-SRV-APP01"].id,
                name="eth0",
                ip_address="10.0.20.10",
                subnet_mask="255.255.255.0",
                admin_status="up",
                oper_status="up",
                speed_mbps=10000,
                mode="access",
                access_vlan=20,
                description="Production App Server Primary NIC",
                bandwidth_utilization_pct=28.0,
            ),
            # HQ-DC-SRV-DB01
            NetworkInterface(
                device_id=device_map["HQ-DC-SRV-DB01"].id,
                name="eth0",
                ip_address="10.0.20.20",
                subnet_mask="255.255.255.0",
                admin_status="up",
                oper_status="up",
                speed_mbps=10000,
                mode="access",
                access_vlan=20,
                description="PostgreSQL Database Primary NIC",
                bandwidth_utilization_pct=35.0,
            ),
            # HQ-DC-SRV-DHCP
            NetworkInterface(
                device_id=device_map["HQ-DC-SRV-DHCP"].id,
                name="eth0",
                ip_address="10.0.20.5",
                subnet_mask="255.255.255.0",
                admin_status="up",
                oper_status="up",
                speed_mbps=1000,
                mode="access",
                access_vlan=20,
                description="Central DHCP & DNS Server",
                bandwidth_utilization_pct=4.0,
            ),
            # PC-Admin-01
            NetworkInterface(
                device_id=device_map["PC-Admin-01"].id,
                name="Ethernet0",
                ip_address="10.0.10.101",
                subnet_mask="255.255.255.0",
                admin_status="up",
                oper_status="up",
                speed_mbps=1000,
                mode="access",
                access_vlan=10,
                description="Admin Client NIC",
                bandwidth_utilization_pct=5.2,
            ),
            # PC-Student-01
            NetworkInterface(
                device_id=device_map["PC-Student-01"].id,
                name="eth0",
                ip_address="10.0.30.101",
                subnet_mask="255.255.255.0",
                admin_status="up",
                oper_status="up",
                speed_mbps=100,
                mode="access",
                access_vlan=30,
                description="Student 01 NIC",
                bandwidth_utilization_pct=8.4,
            ),
            # PC-Student-02
            NetworkInterface(
                device_id=device_map["PC-Student-02"].id,
                name="eth0",
                ip_address="10.0.30.102",
                subnet_mask="255.255.255.0",
                admin_status="up",
                oper_status="up",
                speed_mbps=100,
                mode="access",
                access_vlan=30,
                description="Student 02 NIC",
                bandwidth_utilization_pct=6.1,
            ),
        ]
        db.add_all(interfaces)
        db.commit()

        print("[*] Seeding Network Links...")
        links = [
            NetworkLink(
                name="RTR01-Gi0/0/0 <-> CoreSW01-Te1/1/1",
                source_device_id=device_map["HQ-Core-RTR-01"].id,
                source_interface_name="GigabitEthernet0/0/0",
                target_device_id=device_map["HQ-Core-SW-01"].id,
                target_interface_name="TenGigabitEthernet1/1/1",
                link_type="routed",
                status="up",
                bandwidth_mbps=1000,
                latency_ms=0.8,
            ),
            NetworkLink(
                name="CoreSW01-Te1/1/2 <-> DistSW01-Gi1/0/1",
                source_device_id=device_map["HQ-Core-SW-01"].id,
                source_interface_name="TenGigabitEthernet1/1/2",
                target_device_id=device_map["HQ-Dist-SW-01"].id,
                target_interface_name="GigabitEthernet1/0/1",
                link_type="trunk",
                status="up",
                bandwidth_mbps=10000,
                latency_ms=0.4,
                is_redundant=True,
            ),
            NetworkLink(
                name="DistSW01-Gi1/0/11 <-> AccessSW01-Gi0/1",
                source_device_id=device_map["HQ-Dist-SW-01"].id,
                source_interface_name="GigabitEthernet1/0/11",
                target_device_id=device_map["HQ-Access-SW-01"].id,
                target_interface_name="GigabitEthernet0/1",
                link_type="trunk",
                status="up",
                bandwidth_mbps=1000,
                latency_ms=0.9,
            ),
            NetworkLink(
                name="DistSW01-Gi1/0/12 <-> AccessSW02-Gi0/1",
                source_device_id=device_map["HQ-Dist-SW-01"].id,
                source_interface_name="GigabitEthernet1/0/12",
                target_device_id=device_map["HQ-Access-SW-02"].id,
                target_interface_name="GigabitEthernet0/1",
                link_type="trunk",
                status="up",
                bandwidth_mbps=1000,
                latency_ms=1.1,
            ),
            NetworkLink(
                name="AccessSW01-Fa0/1 <-> PC-Admin-01",
                source_device_id=device_map["HQ-Access-SW-01"].id,
                source_interface_name="FastEthernet0/1",
                target_device_id=device_map["PC-Admin-01"].id,
                target_interface_name="Ethernet0",
                link_type="ethernet",
                status="up",
                bandwidth_mbps=100,
                latency_ms=1.5,
            ),
            NetworkLink(
                name="AccessSW02-Fa0/1 <-> PC-Student-01",
                source_device_id=device_map["HQ-Access-SW-02"].id,
                source_interface_name="FastEthernet0/1",
                target_device_id=device_map["PC-Student-01"].id,
                target_interface_name="eth0",
                link_type="ethernet",
                status="up",
                bandwidth_mbps=100,
                latency_ms=1.6,
            ),
            NetworkLink(
                name="AccessSW02-Fa0/2 <-> PC-Student-02",
                source_device_id=device_map["HQ-Access-SW-02"].id,
                source_interface_name="FastEthernet0/2",
                target_device_id=device_map["PC-Student-02"].id,
                target_interface_name="eth0",
                link_type="ethernet",
                status="up",
                bandwidth_mbps=100,
                latency_ms=1.7,
            ),
            NetworkLink(
                name="CoreSW01 <-> HQ-DC-SRV-APP01",
                source_device_id=device_map["HQ-Core-SW-01"].id,
                source_interface_name="TenGigabitEthernet1/1/2",
                target_device_id=device_map["HQ-DC-SRV-APP01"].id,
                target_interface_name="eth0",
                link_type="ethernet",
                status="up",
                bandwidth_mbps=1000,
                latency_ms=0.5,
            ),
            NetworkLink(
                name="CoreSW01 <-> HQ-DC-SRV-DB01",
                source_device_id=device_map["HQ-Core-SW-01"].id,
                source_interface_name="TenGigabitEthernet1/1/2",
                target_device_id=device_map["HQ-DC-SRV-DB01"].id,
                target_interface_name="eth0",
                link_type="ethernet",
                status="up",
                bandwidth_mbps=1000,
                latency_ms=0.5,
            ),
            NetworkLink(
                name="CoreSW01 <-> HQ-DC-SRV-DHCP",
                source_device_id=device_map["HQ-Core-SW-01"].id,
                source_interface_name="TenGigabitEthernet1/1/2",
                target_device_id=device_map["HQ-DC-SRV-DHCP"].id,
                target_interface_name="eth0",
                link_type="ethernet",
                status="up",
                bandwidth_mbps=1000,
                latency_ms=0.5,
            ),
        ]
        db.add_all(links)
        db.commit()

        print("[*] Seeding Cisco Routes...")
        routes = [
            Route(device_id=device_map["HQ-Core-RTR-01"].id, destination_network="0.0.0.0", netmask="0.0.0.0", next_hop="203.0.113.1", outgoing_interface="GigabitEthernet0/0/1", protocol="static", metric=1),
            Route(device_id=device_map["HQ-Core-RTR-01"].id, destination_network="10.0.0.0", netmask="255.255.0.0", next_hop="192.168.100.2", outgoing_interface="GigabitEthernet0/0/0", protocol="ospf", metric=10),
            Route(device_id=device_map["HQ-Core-SW-01"].id, destination_network="0.0.0.0", netmask="0.0.0.0", next_hop="192.168.100.1", outgoing_interface="TenGigabitEthernet1/1/1", protocol="ospf", metric=10),
            Route(device_id=device_map["HQ-Core-SW-01"].id, destination_network="10.0.10.0", netmask="255.255.255.0", next_hop=None, outgoing_interface="Vlan10", protocol="connected", metric=0),
            Route(device_id=device_map["HQ-Core-SW-01"].id, destination_network="10.0.20.0", netmask="255.255.255.0", next_hop=None, outgoing_interface="Vlan20", protocol="connected", metric=0),
            Route(device_id=device_map["HQ-Core-SW-01"].id, destination_network="10.0.30.0", netmask="255.255.255.0", next_hop=None, outgoing_interface="Vlan30", protocol="connected", metric=0),
        ]
        db.add_all(routes)
        db.commit()

        print("[*] Seeding Baseline Cisco Config Snapshots...")
        cisco_cfg_sw02 = """!
version 15.2
no service pad
service timestamps debug datetime msec
service timestamps log datetime msec
no service password-encryption
!
hostname HQ-Access-SW-02
!
vlan 1,10,20,30,99
!
interface GigabitEthernet0/1
 description Trunk Uplink to HQ-Dist-SW-01
 switchport trunk encapsulation dot1q
 switchport trunk allowed vlan 1,10,20,30,99
 switchport mode trunk
!
interface FastEthernet0/1
 description Student PC 01
 switchport access vlan 30
 switchport mode access
 spanning-tree portfast
!
interface FastEthernet0/2
 description Student PC 02
 switchport access vlan 30
 switchport mode access
 spanning-tree portfast
!
interface Vlan1
 ip address 10.0.1.12 255.255.255.0
 no shutdown
!
ip default-gateway 10.0.1.1
!
line con 0
line vty 0 4
 login
!
end"""

        snap_sw02 = ConfigSnapshot(
            device_id=device_map["HQ-Access-SW-02"].id,
            config_type="baseline",
            content=cisco_cfg_sw02,
            content_hash="d41d8cd98f00b204e9800998ecf8427e_baseline_sw02",
        )
        db.add(snap_sw02)
        db.commit()

        print("[*] Seeding Training Scenarios (CCNA Lab)...")
        scenarios = [
            TrainingScenario(
                scenario_key="vlan_30_trunk_missing",
                title="VLAN 30 Missing from Trunk Port",
                difficulty="Intermediate",
                category="VLAN & Trunking",
                description="Students in Lab 3 report complete connectivity loss to Internet, servers, and gateway 10.0.30.1. Other departments function normally.",
                fault_type="VLAN_TRUNK_PRUNED",
                target_device="HQ-Access-SW-02",
                target_component="GigabitEthernet0/1",
                symptoms=[
                    "Workstations in VLAN 30 cannot ping default gateway 10.0.30.1",
                    "DHCP renewals in VLAN 30 failing",
                    "Switch-2 trunk port Gi0/1 is UP/UP but VLAN 30 is pruned/missing from allowed list",
                    "VLAN 10 and 20 users operating normally"
                ],
                expected_root_cause="VLAN 30 missing from HQ-Access-SW-02 trunk port GigabitEthernet0/1 allowed VLAN list",
                recommended_commands="interface GigabitEthernet0/1\n switchport trunk allowed vlan add 30"
            ),
            TrainingScenario(
                scenario_key="interface_admin_down",
                title="Access Port Administratively Shutdown",
                difficulty="Beginner",
                category="Layer 2 Interface",
                description="Executive workstation PC-Admin-01 suddenly lost link light and cannot reach network resources.",
                fault_type="INTERFACE_SHUTDOWN",
                target_device="HQ-Access-SW-01",
                target_component="FastEthernet0/1",
                symptoms=[
                    "Port FastEthernet0/1 shows 'administratively down'",
                    "No link carrier detected on PC-Admin-01 NIC",
                    "Syslog %LINK-5-CHANGED: Interface FastEthernet0/1, changed state to administratively down"
                ],
                expected_root_cause="Interface FastEthernet0/1 on HQ-Access-SW-01 was administratively shut down",
                recommended_commands="interface FastEthernet0/1\n no shutdown"
            ),
            TrainingScenario(
                scenario_key="wrong_vlan_access",
                title="Mismatched Access Port VLAN Assignment",
                difficulty="Beginner",
                category="VLAN & Subnet",
                description="A student workstation is plugged into port Fa0/2 but receives an IP address in the wrong subnet and cannot reach lab servers.",
                fault_type="WRONG_VLAN",
                target_device="HQ-Access-SW-02",
                target_component="FastEthernet0/2",
                symptoms=[
                    "Client port Fa0/2 configured with 'switchport access vlan 10' instead of 30",
                    "Subnet mismatch between client IP and gateway",
                    "ARP resolution failure to default gateway"
                ],
                expected_root_cause="Access port FastEthernet0/2 assigned to VLAN 10 instead of VLAN 30",
                recommended_commands="interface FastEthernet0/2\n switchport access vlan 30"
            ),
            TrainingScenario(
                scenario_key="dhcp_pool_exhaustion",
                title="Central DHCP Server Reachability Outage",
                difficulty="Intermediate",
                category="Infrastructure Services",
                description="New workstations booting up receive APIPA addresses 169.254.x.x across multiple VLANs.",
                fault_type="DHCP_FAILURE",
                target_device="HQ-DC-SRV-DHCP",
                target_component="eth0",
                symptoms=[
                    "DHCP Discover packets broadcast but no DHCP Offer received",
                    "Clients falling back to 169.254.0.0/16 APIPA addresses",
                    "IP Helper address on Core SVI unable to reach 10.0.20.5"
                ],
                expected_root_cause="DHCP server process halted or server interface eth0 offline on HQ-DC-SRV-DHCP",
                recommended_commands="systemctl restart isc-dhcp-server\nip link set eth0 up"
            ),
            TrainingScenario(
                scenario_key="ospf_neighbor_down",
                title="OSPF Routing Adjacency Deadlock",
                difficulty="Advanced",
                category="IP Routing",
                description="HQ-Core-RTR-01 cannot learn routes to internal server subnets 10.0.20.0/24 and 10.0.30.0/24.",
                fault_type="OSPF_FAILURE",
                target_device="HQ-Core-RTR-01",
                target_component="GigabitEthernet0/0/0",
                symptoms=[
                    "OSPF state stuck in INIT or DOWN with HQ-Core-SW-01",
                    "MTU mismatch or passive-interface configured on uplink",
                    "Missing external routes in core routing table"
                ],
                expected_root_cause="OSPF hello timer mismatch or passive-interface enabled on core interconnect",
                recommended_commands="router ospf 1\n no passive-interface GigabitEthernet0/0/0"
            ),
            TrainingScenario(
                scenario_key="acl_blocking_traffic",
                title="Standard/Extended ACL Filtering Gateway Access",
                difficulty="Intermediate",
                category="Network Security",
                description="Traffic from Student Lab VLAN 30 to Database Server 10.0.20.20 is being rejected, though ping to gateway works.",
                fault_type="ACL_BLOCK",
                target_device="HQ-Core-SW-01",
                target_component="Vlan30",
                symptoms=[
                    "TCP port 5432 connection timed out to 10.0.20.20",
                    "ACL 101 match counters incrementing deny statements",
                    "Show access-lists indicates implicit deny or deny ip any 10.0.20.20"
                ],
                expected_root_cause="Extended ACL 101 applied inbound on Vlan30 denies traffic to DB subnet",
                recommended_commands="ip access-list extended LAB_SECURITY\n permit tcp 10.0.30.0 0.0.0.255 host 10.0.20.20 eq 5432"
            )
        ]
        db.add_all(scenarios)
        db.commit()

        print("[*] Seeding Initial Health Metrics...")
        now = datetime.now(timezone.utc)
        for i in range(12, 0, -1):
            t = now - timedelta(hours=i)
            # Baseline healthy: 94-98%
            metric = HealthMetric(
                timestamp=t,
                overall_health=94.5 + (i % 3),
                availability=98.0,
                performance=92.5 + (i % 2),
                configuration=96.0,
                security=93.0,
                redundancy=91.0,
                risk_score=7.5 - (i * 0.1),
                active_incidents=0,
                total_devices=len(devices_data),
                online_devices=len(devices_data),
                avg_latency_ms=1.4 + (i * 0.05),
                avg_packet_loss_pct=0.0
            )
            db.add(metric)
        db.commit()

        print("[*] Recording System Audit Log...")
        audit = AuditLog(
            username="system",
            action="SYSTEM_INIT",
            resource_type="SYSTEM",
            resource_id="NETGUARDIAN-INIT",
            details={"message": "NetGuardian Enterprise Network Intelligence Platform initialized with Cisco topology."},
            status="SUCCESS"
        )
        db.add(audit)
        db.commit()

        print("[+] Seed completed successfully! Healthy baseline Cisco network ready.")

    except Exception as e:
        db.rollback()
        print(f"[!] Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
