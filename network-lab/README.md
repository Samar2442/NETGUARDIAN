# NetGuardian CCNA Network Lab Topology

The NetGuardian reference network models a standard 3-tier Cisco campus architecture:

```
                          +------------------------+
                          |     HQ-Core-RTR-01     | (Cisco ISR 4451)
                          |       10.0.1.1         | WAN Gateway / Edge BGP & OSPF
                          +-----------┬------------+
                                      │ Gi0/0/0 (192.168.100.1/30)
                                      │ Te1/1/1 (192.168.100.2/30)
                          +-----------┴------------+
                          |     HQ-Core-SW-01      | (Catalyst 3850 L3)
                          |       10.0.1.2         | SVI Gateways (VLAN 10, 20, 30)
                          +-----┬------------┬-----+
                                │            │ Servers (VLAN 20)
       Te1/1/2 (802.1Q Trunk)   │            ├─ HQ-DC-SRV-APP01 (10.0.20.10)
                                │            ├─ HQ-DC-SRV-DB01  (10.0.20.20)
                          +-----┴------------+--+ HQ-DC-SRV-DHCP  (10.0.20.5)
                          |     HQ-Dist-SW-01     | (Catalyst 3850 L2/L3 Dist)
                          |       10.0.1.3        |
                          +-----┬------------┬----+
       Gi1/0/11 (Trunk 10,20,30)│            │ Gi1/0/12 (Trunk 10,20,30)
                                │            │
     +--------------------------┴---+    +---┴--------------------------+
     |       HQ-Access-SW-01        |    |       HQ-Access-SW-02        | (Catalyst 2960-X)
     |          10.0.1.11           |    |          10.0.1.12           | [PRIMARY LAB SWITCH]
     +--------------┬---------------+    +--------------┬---------------+
                    │ Fa0/1                             │ Fa0/1, Fa0/2
        +-----------┴----------+            +-----------┴----------+
        |     PC-Admin-01      |            |     PC-Student-01    | (VLAN 30)
        |     10.0.10.101      |            |     PC-Student-02    | (VLAN 30)
        |  (Admin - VLAN 10)   |            +----------------------+
        +----------------------+
```

## VLAN Directory
- **VLAN 1**: Default Management (`10.0.1.0/24`, Gateway: `10.0.1.1`)
- **VLAN 10**: Administration (`10.0.10.0/24`, Gateway: `10.0.10.1`)
- **VLAN 20**: Engineering & Servers (`10.0.20.0/24`, Gateway: `10.0.20.1`)
- **VLAN 30**: Student & Training Lab (`10.0.30.0/24`, Gateway: `10.0.30.1`)
- **VLAN 99**: Voice & IoT (`10.0.99.0/24`, Gateway: `10.0.99.1`)
