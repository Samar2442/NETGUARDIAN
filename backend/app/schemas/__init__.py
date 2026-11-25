from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[str] = "network_engineer"

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Device Schemas
class InterfaceBase(BaseModel):
    name: str
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    subnet_mask: Optional[str] = None
    admin_status: str = "up"
    oper_status: str = "up"
    speed_mbps: int = 1000
    duplex: str = "full"
    mode: str = "routed"
    access_vlan: Optional[int] = None
    allowed_vlans: Optional[str] = None
    native_vlan: int = 1
    in_octets: int = 0
    out_octets: int = 0
    in_errors: int = 0
    out_errors: int = 0
    packet_drops: int = 0
    bandwidth_utilization_pct: float = 0.0
    is_uplink: bool = False
    is_channel_member: bool = False
    channel_group: Optional[int] = None
    description: Optional[str] = None

class InterfaceCreate(InterfaceBase):
    device_id: str

class InterfaceResponse(InterfaceBase):
    id: str
    device_id: str
    updated_at: datetime

    class Config:
        from_attributes = True

class DeviceBase(BaseModel):
    hostname: str
    management_ip: str
    device_type: str
    vendor: str = "Cisco"
    model: str = "Catalyst 3850"
    os_version: str = "Cisco IOS-XE 17.6.4"
    location: str = "HQ Datacenter"
    department: Optional[str] = None
    vlan_id: Optional[int] = None
    mac_address: Optional[str] = None
    connected_switch_id: Optional[str] = None
    connected_interface: Optional[str] = None
    asset_category: str = "infrastructure"
    layer: Optional[str] = None
    status: str = "online"
    monitoring_status: str = "active"

class DeviceCreate(DeviceBase):
    pass

class DeviceUpdate(BaseModel):
    hostname: Optional[str] = None
    management_ip: Optional[str] = None
    device_type: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    vlan_id: Optional[int] = None
    status: Optional[str] = None
    monitoring_status: Optional[str] = None

class DeviceResponse(DeviceBase):
    id: str
    uptime_seconds: int
    cpu_percent: float
    memory_percent: float
    last_seen: datetime
    created_at: datetime
    updated_at: datetime
    interfaces: List[InterfaceResponse] = []

    class Config:
        from_attributes = True

# VLAN Schemas
class VLANBase(BaseModel):
    vlan_id: int
    name: str
    department: Optional[str] = None
    description: Optional[str] = None
    subnet: str
    gateway_ip: str
    status: str = "active"

class VLANCreate(VLANBase):
    pass

class VLANResponse(VLANBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True

# Route Schemas
class RouteBase(BaseModel):
    destination_network: str
    netmask: str
    next_hop: Optional[str] = None
    outgoing_interface: Optional[str] = None
    protocol: str = "connected"
    metric: int = 0
    is_active: bool = True

class RouteCreate(RouteBase):
    device_id: str

class RouteResponse(RouteBase):
    id: str
    device_id: str
    updated_at: datetime

    class Config:
        from_attributes = True

# Link Schemas
class NetworkLinkCreate(BaseModel):
    name: str
    source_device_id: str
    source_interface_name: str
    target_device_id: str
    target_interface_name: str
    link_type: str = "ethernet"
    admin_status: str = "up"
    status: str = "up"
    bandwidth_mbps: int = 1000
    duplex: str = "full"
    allowed_vlans: Optional[str] = None
    is_redundant: bool = False


class NetworkLinkResponse(BaseModel):
    id: str
    name: str
    source_device_id: str
    source_interface_name: str
    target_device_id: str
    target_interface_name: str
    link_type: str
    admin_status: str = "up"
    status: str
    bandwidth_mbps: int
    duplex: str = "full"
    allowed_vlans: Optional[str] = None
    utilization_pct: float = 12.0
    latency_ms: float
    packet_loss_pct: float
    is_redundant: bool
    last_state_change: Optional[datetime] = None
    updated_at: datetime

    class Config:
        from_attributes = True

# Event & Incident Schemas
class EventResponse(BaseModel):
    id: str
    timestamp: datetime
    source_type: str
    source_id: Optional[str] = None
    source_name: str
    event_type: str
    event_code: Optional[str] = None
    severity: str
    message: str
    details: Dict[str, Any] = {}
    acknowledged: bool = False
    resolved: bool = False
    is_correlated: bool
    incident_id: Optional[str] = None

    class Config:
        from_attributes = True

class DiagnosisResponse(BaseModel):
    id: str
    incident_id: str
    root_cause: str
    category: str
    confidence: float
    severity: str
    explanation: str
    supporting_evidence: List[str] = []
    contradicting_evidence: List[str] = []
    recommended_action: str
    verification_steps: List[str] = []
    evidence_graph: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True

class RemediationResponse(BaseModel):
    id: str
    incident_id: str
    device_id: str
    title: str
    target_interface: Optional[str] = None
    operation: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    execution_mode: str = "SIMULATION"
    proposed_commands: str
    rollback_commands: str
    risk_level: str
    expected_result: str
    status: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    config_revision: Optional[str] = None
    approval_digest: Optional[str] = None
    executed_by: Optional[str] = None
    execution_started_at: Optional[datetime] = None
    execution_finished_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    verification_status: Optional[str] = None
    execution_log: Optional[str] = None
    rollback_log: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class IncidentResponse(BaseModel):
    id: str
    incident_number: str
    title: str
    description: str
    severity: str
    status: str
    source_device_id: Optional[str] = None
    source_device_name: Optional[str] = None
    affected_device_ids: List[str] = []
    affected_vlan_ids: List[int] = []
    affected_endpoints_count: int = 0
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    source: str = "SIMULATION"
    diagnosis: Optional[DiagnosisResponse] = None
    remediations: List[RemediationResponse] = []

    class Config:
        from_attributes = True

# Health & Metrics Schemas
class HealthOverviewResponse(BaseModel):
    overall_health: float
    availability: float
    performance: float
    configuration: float
    security: float
    redundancy: float
    risk_score: float
    active_incidents: int
    critical_alerts: int
    total_devices: int
    online_devices: int
    offline_devices: int
    avg_latency_ms: float
    avg_packet_loss_pct: float
    environment: str = "LAB-SIMULATION"
    is_demo: bool = True

# Audit Schemas
class AuditLogResponse(BaseModel):
    id: str
    timestamp: datetime
    user_id: Optional[str] = None
    username: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    details: Dict[str, Any] = {}
    ip_address: str
    status: str

    class Config:
        from_attributes = True
