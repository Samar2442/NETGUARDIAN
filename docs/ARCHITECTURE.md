# NetGuardian System Architecture

NetGuardian is built upon a resilient 3-layer architecture designed for enterprise network intelligence, explainable root-cause diagnosis, and controlled self-healing.

```
+---------------------------------------------------------------------------------------+
|                                Layer 3: Web Application                               |
| React 18 | TypeScript | Vite | Tailwind CSS | React Flow Topology | Recharts Analytics|
+---------------------------------------------------------------------------------------+
                                           │  REST / WebSockets
+------------------------------------------▼--------------------------------------------+
|                       Layer 2: NetGuardian Intelligence Layer                         |
|                                                                                       |
|  [Discovery Engine]       [Telemetry Monitor]       [Correlation Engine]              |
|  [Root-Cause Analysis]    [Evidence Graph Engine]   [Digital Twin Simulator]          |
|  [Blast-Radius Traversal] [Health & Risk Scoring]   [Recommendation Engine]           |
|  [Approval Enforcement]   [Remediation Engine]      [Verification Engine]             |
|  [Configuration Rollback] [Drift Engine]            [CCNA Training Lab]               |
+---------------------------------------------------------------------------------------+
                                           │  Adapters
+------------------------------------------▼--------------------------------------------+
|                              Layer 1: Cisco Network Layer                             |
|  Mock/Simulator Engine  │  SNMP Telemetry Adapter  │  Cisco IOS SSH Netmiko Adapter   |
|  Routers (ISR 4451)     │  L3 Switches (3850)      │  Access Switches (2960-X)        |
|  802.1Q Trunks / VLANs  │  OSPF Routing Domain     │  Data Center Servers & Endpoints |
+---------------------------------------------------------------------------------------+
```

## The 17 Core NetGuardian Intelligence Engines

1. **Network Discovery Engine**: Discovers, registers, and inventories Cisco devices, interfaces, MAC/IP mappings, and locations.
2. **Monitoring Engine**: Polling engine collecting ICMP reachability, interface oper/admin statuses, error counters, and bandwidth.
3. **Telemetry Collection Engine**: High-throughput ingestion of Cisco Syslog traps, SNMP metrics, and telemetry events.
4. **Event Processing Engine**: Normalizes heterogenous notifications into structured event objects.
5. **Event Correlation Engine**: Clusters multi-symptom alerts across time windows, VLAN segments, and switch boundaries into unified incidents.
6. **Root-Cause Analysis Engine**: Evaluates 12+ evidence-based CCNA diagnostic rules with weighted confidence metrics.
7. **Evidence Graph Engine**: Synthesizes client -> VLAN -> switch -> trunk -> root cause -> gateway dependency chains for interactive visualization.
8. **Configuration Drift Engine**: Computes unified diffs between approved baseline snapshots and running configurations.
9. **Digital Twin Engine**: Builds in-memory networkx graph models to simulate failures decoupled from real hardware.
10. **Blast-Radius Analysis Engine**: Traverses graph dependencies to determine downstream service and workstation impact.
11. **Health Scoring Engine**: Transparent 5-factor mathematical scoring: (Avail*0.3 + Perf*0.2 + Config*0.2 + Sec*0.15 + Redun*0.15).
12. **Risk Assessment Engine**: Evaluates exposure level based on active incidents, error rates, and path redundancy.
13. **Recommendation Engine**: Generates syntax-validated Cisco CLI remediation scripts with safety checks.
14. **Approval Engine**: Enforces role-based human approval checkpoints before any network configuration change.
15. **Remediation Engine**: Takes automated configuration backups, executes Cisco changes, and records session logs.
16. **Verification Engine**: Executes post-change diagnostic probes (802.1Q allowed lists, ICMP echo, ARP) to verify recovery.
17. **Rollback Engine**: Automatically reverses configuration mutations if verification fails or operator requests rollback.
