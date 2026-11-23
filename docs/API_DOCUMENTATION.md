# NetGuardian REST API Documentation

Base URI: `/api/v1`

---

## Authentication (`/auth`)
- `POST /api/v1/auth/login`: Authenticate operator and receive JWT token.
- `POST /api/v1/auth/token`: OAuth2 password flow compatibility.
- `GET /api/v1/auth/me`: Get current authenticated user profile and RBAC role.

## Device Management (`/devices`)
- `GET /api/v1/devices`: List all registered Cisco devices, status, and telemetry.
- `POST /api/v1/devices`: Register new Cisco device into inventory.
- `GET /api/v1/devices/{id}`: Inspect single device, interfaces, and routes.
- `PUT /api/v1/devices/{id}`: Update device attributes.
- `DELETE /api/v1/devices/{id}`: Remove device from inventory.

## Interface Telemetry (`/interfaces`)
- `GET /api/v1/interfaces`: List switchports, operational statuses, and 802.1Q trunk allowed lists.
- `GET /api/v1/interfaces/{id}`: Detailed interface error counters and bandwidth utilization.
- `PUT /api/v1/interfaces/{id}/admin-status`: Administratively shutdown or enable interface (`up`/`down`).

## VLAN & Routing (`/vlans`, `/routes`)
- `GET /api/v1/vlans`: List active VLAN IDs, subnets, and default gateways.
- `POST /api/v1/vlans`: Create new VLAN definition.
- `GET /api/v1/routes`: Retrieve routing tables, next-hop addresses, and routing protocol tags.

## Monitoring & Health (`/monitoring`)
- `GET /api/v1/monitoring/overview`: Transparent network health (0-100), availability, performance, and risk score.
- `GET /api/v1/monitoring/metrics`: Historical metric timeline for charts.
- `GET /api/v1/monitoring/events`: Live ingested telemetry and syslog stream.
- `POST /api/v1/monitoring/poll`: Trigger on-demand device polling cycle.

## Incident Management (`/incidents`)
- `GET /api/v1/incidents`: Filter and list active/historical correlated incidents.
- `GET /api/v1/incidents/{id}`: Retrieve incident timeline, affected devices, and root cause.
- `PUT /api/v1/incidents/{id}/status`: Transition incident state.

## Root-Cause Diagnostics (`/diagnostics`)
- `POST /api/v1/diagnostics/run`: Execute evidence-based diagnostic rules on an incident.
- `GET /api/v1/diagnostics/{incident_id}`: Retrieve calculated confidence, explanation, and recommendation.
- `GET /api/v1/diagnostics/{incident_id}/evidence`: Multi-symptom evidence graph nodes and edges.

## Digital Twin Simulator (`/simulator`)
- `GET /api/v1/simulator/topology`: Logical network topology model.
- `POST /api/v1/simulator/run`: Execute What-If simulation (e.g. VLAN trunk pruning, switch failure).
- `GET /api/v1/simulator/blast-radius`: Calculate downstream isolated devices and service dependencies.

## Remediation Hub (`/remediation`)
- `GET /api/v1/remediation`: List proposed Cisco configurations.
- `POST /api/v1/remediation/{id}/approve`: Administrator approval checkpoint.
- `POST /api/v1/remediation/{id}/reject`: Reject proposal.
- `POST /api/v1/remediation/{id}/execute`: Take config snapshot, execute Cisco commands, run automated verification.
- `POST /api/v1/remediation/{id}/rollback`: Revert configuration to previous state.

## CCNA Training Lab (`/training`)
- `GET /api/v1/training/scenarios`: List curated CCNA troubleshooting exercises.
- `POST /api/v1/training/inject-fault`: Controlled failure injection into lab simulator.
- `POST /api/v1/training/grade-diagnosis`: Grade student troubleshooting hypothesis against ground truth.

## Configuration Drift & Audit (`/drift`, `/audit`)
- `GET /api/v1/drift/compare/{device_id}`: Unified diff between running-config and approved baseline.
- `GET /api/v1/audit`: Immutable audit trail of operator approvals and configuration changes.

## WebSockets
- `WS /ws`: Real-time bi-directional telemetry broadcast and anomaly event streaming.
