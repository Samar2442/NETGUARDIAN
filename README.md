# NETGUARDIAN
### Intelligent Network Fault Detection, Root-Cause Analysis, Digital Twin & Explainable Self-Healing Platform

> **Tagline**: *Detect. Understand. Predict. Recover.*  
> **Institution**: SaturnX Academy — Senior Networking & Cybersecurity Engineering Project

---

## 1. Executive Summary

NetGuardian is a modular, enterprise-grade network intelligence platform designed around Cisco networking and CCNA principles. Built for Network Operations Centers (NOC), infrastructure administrators, and educational cybersecurity labs, it automates the full incident remediation cycle:

$$\text{DETECT} \longrightarrow \text{COLLECT EVIDENCE} \longrightarrow \text{CORRELATE} \longrightarrow \text{IDENTIFY ROOT CAUSE} \longrightarrow \text{PREDICT IMPACT} \longrightarrow \text{RECOMMEND FIX} \longrightarrow \text{HUMAN APPROVAL} \longrightarrow \text{CONTROLLED REMEDIATION} \longrightarrow \text{VERIFY RECOVERY} \longrightarrow \text{RESOLVE / ROLLBACK}$$

---

## 2. Platform Architecture

NetGuardian implements a 3-layer architecture:

- **Layer 1: Cisco Network Layer**
  - High-fidelity simulated topology (Cisco ISR 4451 Core Router, Catalyst 3850 L3 Switch, Catalyst 3850 Distribution Switch, Catalyst 2960-X Access Switches, Data Center Servers, and Student Lab Workstations).
  - Multi-VLAN architecture: VLAN 1 (Management), VLAN 10 (Admin), VLAN 20 (Servers), VLAN 30 (Student Lab), VLAN 99 (Voice/IoT).
  - Dynamic routing via OSPF and static default routing.
  - Pluggable adapters: Simulation Adapter, SNMP Traps, and Cisco IOS SSH (Netmiko/Paramiko).

- **Layer 2: NetGuardian Intelligence Layer**
  - **Discovery Engine**: Dynamic device, interface, and MAC/IP inventory.
  - **Monitoring Engine**: Periodic ICMP and interface oper/admin polling.
  - **Correlation Engine**: Clusters multi-symptom alerts into unified incidents across time windows and VLAN boundaries.
  - **RCA Engine**: Evaluates 12+ evidence-based diagnostic rules with documented confidence weights (never black-box arbitrary AI numbers).
  - **Evidence Graph Engine**: Synthesizes interactive dependency chains (`Client → VLAN → Switch → Trunk → Root Cause → Gateway`).
  - **Digital Twin Engine**: In-memory `networkx` graph traversal for What-If simulation decoupled from live hardware.
  - **Blast-Radius Engine**: Computes isolated endpoints and affected services.
  - **Health Scoring Engine**: Transparent formula: $\text{Health} = (\text{Avail} \times 0.3) + (\text{Perf} \times 0.2) + (\text{Config} \times 0.2) + (\text{Sec} \times 0.15) + (\text{Redun} \times 0.15)$.
  - **Remediation & Approval Engine**: Enforces mandatory human approval, pre-change config backups, safe execution, automated verification, and instant rollback.
  - **Training Lab Engine**: CCNA fault injection and automated troubleshooting grading.

- **Layer 3: Enterprise Web Application Layer**
  - React 18, TypeScript, Tailwind CSS, React Flow topology canvas, Recharts telemetry curves, and Lucide React icons.
  - 16 fully functional pages (Overview, Topology, Devices, Interfaces, VLANs, Routing, Monitoring, Incidents, RCA, Digital Twin, Remediation, Training Lab, Analytics, Audit Logs, Settings, Login).

---

## 3. Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, React Flow (@xyflow/react), Recharts, Zustand, TanStack Query, Lucide React |
| **Backend** | Python 3.12+, FastAPI, SQLAlchemy, Alembic, Pydantic v2, Uvicorn, NetworkX, WebSockets, Bcrypt, PyJWT |
| **Database** | PostgreSQL (Production Docker) & SQLite (Zero-friction local development) |
| **Networking** | Cisco IOS CLI, 802.1Q IEEE VLAN Trunking, OSPFv2, ICMP, SNMP, Syslog |
| **Deployment**| Docker, Docker Compose |

---

## 4. Quick Start (Local Run Without Docker)

### Prerequisites
- Python 3.12+
- Node.js 18+ and npm

### 1. Backend Setup
```powershell
# Navigate to backend and create virtual environment
cd d:\NETGUARDIAN\backend
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database and seed baseline Cisco network
python -m app.database.seed

# Run backend API server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The FastAPI backend will be available at `http://127.0.0.1:8000` with Swagger UI at `http://127.0.0.1:8000/docs`.

### 2. Frontend Setup
```powershell
# Open a new terminal and navigate to frontend
cd d:\NETGUARDIAN\frontend

# Install packages
npm install

# Start Vite development server
npm run dev
```
Open your browser at `http://localhost:5173`.

### 3. Default Credentials
- **Administrator**: `admin` / `NetGuardianAdmin2026!`
- **Network Engineer**: `neteng` / `CiscoEngineer2026!`
- **Auditor / Viewer**: `auditor` / `ViewerAuditor2026!`

---

## 5. Docker Deployment

To launch the full production stack with PostgreSQL:
```bash
docker-compose up --build -d
```
- Frontend UI: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

---

## 6. Acceptance Criteria: Complete Demonstration Walkthrough

NetGuardian includes an automated end-to-end verification script executing all 19 workflow steps:

```powershell
$env:PYTHONPATH="backend"
.\backend\venv\Scripts\python.exe scripts/demo_runner.py
```

### The 19 Workflow Steps Executed:
1. **Launch NetGuardian**: System initialized with healthy baseline topology.
2. **Inspect Topology**: 11 nodes, 10 links rendered with 3-tier hierarchy.
3. **Verify Baseline State**: `HQ-Access-SW-02` `GigabitEthernet0/1` allows VLAN `1,10,20,30,99`.
4. **Open Training Lab / Digital Twin**: Select "VLAN 30 Missing from Trunk Port".
5. **Fault Injection**: Injects defect removing VLAN 30 from `HQ-Access-SW-02` trunk `Gi0/1`.
6. **Monitoring Detection**: Ingests `%SW_TRUNK-4-VLAN_NOT_ALLOWED` syslog and client ICMP timeouts.
7. **Event Correlation**: Clusters events across VLAN 30 into incident `INC-20261123-101`.
8. **Root Cause Analysis**: Evaluates diagnostic rule: **"VLAN 30 missing from HQ-Access-SW-02 trunk port GigabitEthernet0/1."** with **96.0% confidence**.
9. **Evidence Graph**: Displays causal link: `PC-Student-01 → VLAN 30 → HQ-Access-SW-02 → Gi0/1 Trunk → VLAN Missing → Gateway Unreachable`.
10. **Digital Twin Simulation**: Computes isolated endpoints (`PC-Student-01`, `PC-Student-02`) and no redundant path.
11. **Recommendation**: Proposes exact Cisco command:
    ```cisco
    interface GigabitEthernet0/1
     switchport trunk allowed vlan add 30
    ```
12. **Risk Assessment**: Classifies risk as `LOW (INTERFACE CONFIG ONLY)` with rollback plan.
13. **Human Approval**: Administrator clicks "Approve Remediation".
14. **Controlled Execution**: Takes configuration snapshot and applies commands.
15. **Verification Engine**: Confirms VLAN 30 in allowed list, pings default gateway (5/5 received, 0% loss), and verifies ARP.
16. **Connectivity Restored**: Workstations in VLAN 30 recover network access.
17. **Health Score Recalculated**: Network health score restores from degraded to `95.2/100`.
18. **Incident Resolved**: Incident status changes to `RESOLVED` with resolution timestamp.
19. **Immutable Audit Trail**: Operation logged in audit registry.

---

## 7. Automated Testing Suite

NetGuardian includes automated tests covering authentication, RBAC, correlation, RCA, Digital Twin, blast-radius, and remediation:

```powershell
$env:PYTHONPATH="backend"
$env:TESTING="true"
.\backend\venv\Scripts\pytest.exe backend/tests -v
```
**Test Results**: `13 passed, 100% pass rate`.

---

## 8. Repository Structure

```
netguardian/
├── backend/
│   ├── app/
│   │   ├── api/v1/         # FastAPI REST routes (auth, devices, topology, rca, etc.)
│   │   ├── core/           # Security, password hashing, JWT, app configuration
│   │   ├── models/         # SQLAlchemy ORM models (devices, vlans, incidents, etc.)
│   │   ├── schemas/        # Pydantic v2 validation models
│   │   ├── engines/        # 17 intelligence engines (rca, digital twin, remediation, etc.)
│   │   ├── database/       # Database session and Cisco topology seed script
│   │   ├── websocket/      # Bi-directional WebSocket telemetry broadcaster
│   │   └── main.py         # Application entry point and lifespan
│   ├── tests/              # Automated unit and integration tests
│   ├── requirements.txt    # Python dependencies
│   ├── alembic.ini         # Database migration configuration
│   └── Dockerfile          # Backend Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/     # Layout, React Flow Cisco nodes, Evidence Graph, StatCards
│   │   ├── pages/          # 16 complete UI pages
│   │   ├── services/       # Typed API client
│   │   ├── store/          # Zustand global state (auth, RBAC, telemetry)
│   │   ├── types/          # TypeScript domain models
│   │   ├── App.tsx         # Routing configuration
│   │   └── main.tsx        # React root entry point
│   ├── package.json        # NPM dependencies
│   ├── vite.config.ts      # Vite configuration & API proxy
│   └── Dockerfile          # Frontend production Dockerfile
├── scripts/
│   └── demo_runner.py      # Automated 19-step acceptance criteria demo
├── docs/
│   ├── ARCHITECTURE.md     # Detailed technical architecture specification
│   ├── DIAGNOSTIC_RULES.md # Documented diagnostic rules and confidence formulas
│   └── API_DOCUMENTATION.md# Complete REST API reference
├── network-lab/            # Cisco topology diagrams and VLAN directory
├── docker-compose.yml      # Multi-container production deployment
└── README.md               # Project documentation
```

---

## 9. License & Credits

Developed for **SaturnX Academy** as a Senior Network Operations, Digital Twin, and Cybersecurity Platform.  
Built with integrity: strict separation of simulated lab telemetry from physical Cisco hardware, mathematical confidence calculations, and human-in-the-loop remediation safety.
