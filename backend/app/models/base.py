import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON, Enum
)
from sqlalchemy.orm import relationship
from app.database.session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="network_engineer")  # admin, network_engineer, viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Device(Base):
    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    hostname = Column(String(100), unique=True, nullable=False, index=True)
    management_ip = Column(String(45), nullable=False, index=True)
    device_type = Column(String(50), nullable=False)  # router, firewall, l3_switch, l2_switch, access_switch, wireless_ap, server, endpoint
    vendor = Column(String(50), default="Cisco")
    model = Column(String(100), default="Catalyst 3850 / ISR 4331")
    os_version = Column(String(100), default="Cisco IOS-XE 17.6.4")
    location = Column(String(100), default="HQ Datacenter")
    department = Column(String(100), nullable=True, index=True)
    vlan_id = Column(Integer, nullable=True, index=True)
    mac_address = Column(String(20), unique=True, nullable=True, index=True)
    connected_switch_id = Column(String(36), nullable=True, index=True)
    connected_interface = Column(String(50), nullable=True)
    asset_category = Column(String(40), default="infrastructure", index=True)
    layer = Column(String(30), nullable=True)
    status = Column(String(20), default="online", index=True)  # online, degraded, offline
    monitoring_status = Column(String(20), default="active")  # active, paused, error
    uptime_seconds = Column(Integer, default=864000)
    cpu_percent = Column(Float, default=14.5)
    memory_percent = Column(Float, default=38.2)
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    interfaces = relationship("NetworkInterface", back_populates="device", cascade="all, delete-orphan")
    routes = relationship("Route", back_populates="device", cascade="all, delete-orphan")
    snapshots = relationship("ConfigSnapshot", back_populates="device", cascade="all, delete-orphan")
    drifts = relationship("ConfigDrift", back_populates="device", cascade="all, delete-orphan")

class NetworkInterface(Base):
    __tablename__ = "interfaces"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=False, index=True)
    name = Column(String(50), nullable=False, index=True)  # e.g. GigabitEthernet0/1
    mac_address = Column(String(20), nullable=True)
    ip_address = Column(String(45), nullable=True)
    subnet_mask = Column(String(45), nullable=True)
    admin_status = Column(String(10), default="up")  # up, down
    oper_status = Column(String(10), default="up", index=True)   # up, down, error-disabled
    speed_mbps = Column(Integer, default=1000)
    duplex = Column(String(10), default="full")  # full, half, auto
    mode = Column(String(20), default="routed")  # routed, access, trunk
    access_vlan = Column(Integer, nullable=True)
    allowed_vlans = Column(String(255), nullable=True)  # comma separated list e.g. "10,20,30,99"
    native_vlan = Column(Integer, default=1)
    in_octets = Column(Integer, default=1048576)
    out_octets = Column(Integer, default=948576)
    in_errors = Column(Integer, default=0)
    out_errors = Column(Integer, default=0)
    packet_drops = Column(Integer, default=0)
    bandwidth_utilization_pct = Column(Float, default=24.5)
    is_uplink = Column(Boolean, default=False)
    is_channel_member = Column(Boolean, default=False)
    channel_group = Column(Integer, nullable=True)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    device = relationship("Device", back_populates="interfaces")

class VLAN(Base):
    __tablename__ = "vlans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    vlan_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False)
    department = Column(String(100), nullable=True, index=True)
    description = Column(String(255), nullable=True)
    subnet = Column(String(50), nullable=False)
    gateway_ip = Column(String(45), nullable=False)
    status = Column(String(20), default="active")  # active, suspended
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Route(Base):
    __tablename__ = "routes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=False, index=True)
    destination_network = Column(String(50), nullable=False)
    netmask = Column(String(50), nullable=False)
    next_hop = Column(String(45), nullable=True)
    outgoing_interface = Column(String(50), nullable=True)
    protocol = Column(String(20), default="connected")  # connected, static, ospf, bgp
    metric = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    device = relationship("Device", back_populates="routes")

class NetworkLink(Base):
    __tablename__ = "network_links"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    source_device_id = Column(String(36), ForeignKey("devices.id"), nullable=False)
    source_interface_name = Column(String(50), nullable=False)
    target_device_id = Column(String(36), ForeignKey("devices.id"), nullable=False)
    target_interface_name = Column(String(50), nullable=False)
    link_type = Column(String(30), default="ethernet")  # ethernet, trunk, fiber, port-channel
    admin_status = Column(String(10), default="up")
    status = Column(String(20), default="up")  # up, degraded, down
    bandwidth_mbps = Column(Integer, default=1000)
    duplex = Column(String(10), default="full")
    allowed_vlans = Column(String(255), nullable=True)
    utilization_pct = Column(Float, default=12.0)
    latency_ms = Column(Float, default=1.2)
    packet_loss_pct = Column(Float, default=0.0)
    is_redundant = Column(Boolean, default=False)
    last_state_change = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Event(Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    source_type = Column(String(30), nullable=False)  # device, interface, vlan, route, syslog, icmp
    source_id = Column(String(36), nullable=True, index=True)
    source_name = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False, index=True)  # INTERFACE_DOWN, VLAN_MISSING, OSPF_ADJACENCY_DOWN, etc.
    severity = Column(String(20), default="medium", index=True)  # critical, high, medium, low, info
    message = Column(Text, nullable=False)
    details = Column(JSON, default=dict)
    raw_payload = Column(Text, nullable=True)
    is_correlated = Column(Boolean, default=False, index=True)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=True, index=True)

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_number = Column(String(30), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), default="high", index=True)  # critical, high, medium, low
    status = Column(String(30), default="DETECTED", index=True)
    # DETECTED, INVESTIGATING, ROOT_CAUSE_IDENTIFIED, REMEDIATION_PROPOSED, APPROVED, APPLIED, VERIFICATION, RESOLVED, ROLLBACK, ESCALATED
    source_device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    source_device_name = Column(String(100), nullable=True)
    affected_device_ids = Column(JSON, default=list)
    affected_vlan_ids = Column(JSON, default=list)
    affected_endpoints_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

    events = relationship("Event", backref="incident", lazy="dynamic")
    diagnosis = relationship("Diagnosis", uselist=False, back_populates="incident")
    remediations = relationship("RemediationProposal", back_populates="incident")

class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id"), unique=True, nullable=False)
    root_cause = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)  # vlan_trunk, routing, interface, dhcp, acl, stp, etherchannel, drift
    confidence = Column(Float, nullable=False)  # 0 to 100 percentage
    severity = Column(String(20), nullable=False)
    explanation = Column(Text, nullable=False)
    supporting_evidence = Column(JSON, default=list)
    contradicting_evidence = Column(JSON, default=list)
    recommended_action = Column(Text, nullable=False)
    verification_steps = Column(JSON, default=list)
    evidence_graph = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    incident = relationship("Incident", back_populates="diagnosis")

class RemediationProposal(Base):
    __tablename__ = "remediations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=False)
    title = Column(String(255), nullable=False)
    target_interface = Column(String(50), nullable=True)
    operation = Column(String(64), nullable=True)
    parameters = Column(JSON, default=dict)
    execution_mode = Column(String(20), default="SIMULATION")
    proposed_commands = Column(Text, nullable=False)
    rollback_commands = Column(Text, nullable=False)
    risk_level = Column(String(20), default="low")  # low, medium, high
    expected_result = Column(Text, nullable=False)
    status = Column(String(30), default="PENDING_APPROVAL")
    # PENDING_APPROVAL, APPROVED, REJECTED, EXECUTING, APPLIED, VERIFYING, VERIFIED, FAILED, ROLLED_BACK
    approved_by = Column(String(50), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    config_revision = Column(String(64), nullable=True)
    approval_digest = Column(String(64), nullable=True)
    executed_by = Column(String(50), nullable=True)
    execution_started_at = Column(DateTime, nullable=True)
    execution_finished_at = Column(DateTime, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    verification_status = Column(String(30), nullable=True)
    execution_log = Column(Text, nullable=True)
    rollback_log = Column(Text, nullable=True)
    backup_snapshot = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    incident = relationship("Incident", back_populates="remediations")

class ConfigSnapshot(Base):
    __tablename__ = "config_snapshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=False, index=True)
    config_type = Column(String(30), default="running-config")  # running-config, startup-config, baseline
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    device = relationship("Device", back_populates="snapshots")

class ConfigDrift(Base):
    __tablename__ = "config_drifts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=False, index=True)
    baseline_id = Column(String(36), ForeignKey("config_snapshots.id"), nullable=True)
    current_id = Column(String(36), ForeignKey("config_snapshots.id"), nullable=True)
    drift_detected = Column(Boolean, default=False)
    diff_text = Column(Text, nullable=True)
    drift_details = Column(JSON, default=dict)
    severity = Column(String(20), default="low")
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(20), default="unresolved")  # unresolved, acknowledged, remediated

    device = relationship("Device", back_populates="drifts")

class HealthMetric(Base):
    __tablename__ = "health_metrics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    overall_health = Column(Float, nullable=False)
    availability = Column(Float, nullable=False)
    performance = Column(Float, nullable=False)
    configuration = Column(Float, nullable=False)
    security = Column(Float, nullable=False)
    redundancy = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    active_incidents = Column(Integer, default=0)
    total_devices = Column(Integer, default=0)
    online_devices = Column(Integer, default=0)
    avg_latency_ms = Column(Float, default=1.8)
    avg_packet_loss_pct = Column(Float, default=0.0)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    user_id = Column(String(36), nullable=True)
    username = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSON, default=dict)
    ip_address = Column(String(45), default="127.0.0.1")
    status = Column(String(20), default="SUCCESS")  # SUCCESS, FAILED, WARNING

class TrainingScenario(Base):
    __tablename__ = "training_scenarios"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scenario_key = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(150), nullable=False)
    difficulty = Column(String(20), default="Intermediate")  # Beginner, Intermediate, Advanced
    category = Column(String(50), default="VLAN & Trunking")
    description = Column(Text, nullable=False)
    fault_type = Column(String(50), nullable=False)
    target_device = Column(String(100), nullable=False)
    target_component = Column(String(100), nullable=False)
    symptoms = Column(JSON, default=list)
    expected_root_cause = Column(String(255), nullable=False)
    recommended_commands = Column(Text, nullable=False)

class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=True)
    username = Column(String(50), default="admin")
    scenario_key = Column(String(50), nullable=False)
    status = Column(String(30), default="IN_PROGRESS")  # IN_PROGRESS, DIAGNOSED, RESOLVED, ABANDONED
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    student_diagnosis = Column(Text, nullable=True)
    student_confidence = Column(Float, nullable=True)
    detection_time_sec = Column(Integer, default=0)
    resolution_time_sec = Column(Integer, default=0)
    accuracy_score = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)
    feedback = Column(Text, nullable=True)
