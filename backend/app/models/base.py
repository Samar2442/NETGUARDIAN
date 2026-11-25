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
    event_code = Column(String(60), nullable=True)
    severity = Column(String(20), default="medium", index=True)  # critical, high, medium, low, info
    message = Column(Text, nullable=False)
    details = Column(JSON, default=dict)
    raw_payload = Column(Text, nullable=True)
    device_id = Column(String(36), nullable=True, index=True)
    interface_id = Column(String(36), nullable=True, index=True)
    vlan_id = Column(Integer, nullable=True, index=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    acknowledged = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)
    is_correlated = Column(Boolean, default=False, index=True)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=True, index=True)

class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_number = Column(String(30), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), default="high", index=True)  # critical, high, medium, low
    priority = Column(String(10), default="P2", index=True)  # P1, P2, P3, P4
    status = Column(String(30), default="DETECTED", index=True)
    lifecycle_state = Column(String(30), default="NEW", index=True)
    # NEW, ACKNOWLEDGED, IN_PROGRESS, MITIGATED, RESOLVED, CLOSED
    source_device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    source_device_name = Column(String(100), nullable=True)
    affected_device_ids = Column(JSON, default=list)
    affected_interface_ids = Column(JSON, default=list)
    affected_vlan_ids = Column(JSON, default=list)
    affected_endpoints_count = Column(Integer, default=0)
    root_event_id = Column(String(36), nullable=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    assigned_to = Column(String(50), nullable=True, index=True)
    assigned_at = Column(DateTime, nullable=True)
    escalation_level = Column(Integer, default=0)
    escalated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(50), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    source = Column(String(30), default="SIMULATION")
    incident_category = Column(String(20), default="NETWORK", index=True)  # NETWORK, SECURITY
    security_severity = Column(String(20), nullable=True)
    affected_services = Column(JSON, default=list)

    events = relationship("Event", backref="incident", lazy="dynamic")
    diagnosis = relationship("Diagnosis", uselist=False, back_populates="incident")
    remediations = relationship("RemediationProposal", back_populates="incident")

class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id"), unique=True, nullable=False)
    root_cause = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False)  # vlan_trunk, routing, interface, dhcp, acl, stp, etherchannel, drift, link_failure, hardware_resource, insufficient_evidence
    status = Column(String(30), default="CONFIRMED")  # CONFIRMED, PROBABLE, UNCERTAIN, INSUFFICIENT_EVIDENCE
    confidence = Column(Float, nullable=False)  # 0 to 100 percentage
    severity = Column(String(20), nullable=False)
    explanation = Column(Text, nullable=False)
    supporting_evidence = Column(JSON, default=list)
    contradicting_evidence = Column(JSON, default=list)
    secondary_symptoms = Column(JSON, default=list)
    related_event_ids = Column(JSON, default=list)
    independent_failures = Column(JSON, default=list)
    affected_devices = Column(JSON, default=list)
    affected_vlans = Column(JSON, default=list)
    affected_services = Column(JSON, default=list)
    candidate_causes = Column(JSON, default=list)
    timeline = Column(JSON, default=list)
    recommended_action = Column(Text, nullable=False)
    verification_steps = Column(JSON, default=list)
    evidence_graph = Column(JSON, default=dict)
    analysis_timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
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


class Student(Base):
    """Synthetic university student identity record (never real PII)."""
    __tablename__ = "students"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    student_id = Column(String(32), unique=True, nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    department = Column(String(50), nullable=False, index=True)  # CSE, IT, ECE
    academic_year = Column(Integer, nullable=False, default=1)
    semester = Column(Integer, nullable=False, default=1)
    enrollment_status = Column(String(30), nullable=False, default="ACTIVE", index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    device_id = Column(String(36), ForeignKey("devices.id"), unique=True, nullable=True, index=True)
    enrollment_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    device = relationship("Device", foreign_keys=[device_id])


class Faculty(Base):
    """Synthetic university faculty member record (never real PII)."""
    __tablename__ = "faculty"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    faculty_id = Column(String(32), unique=True, nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    department = Column(String(50), nullable=False, index=True)  # CSE, IT, ECE
    designation = Column(String(80), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    employment_status = Column(String(30), nullable=False, default="ACTIVE", index=True)
    office_location = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ITPersonnel(Base):
    """Synthetic IT & Network Operations personnel record (not application login accounts)."""
    __tablename__ = "it_personnel"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    employee_id = Column(String(32), unique=True, nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    job_title = Column(String(80), nullable=False)
    team = Column(String(60), nullable=False)
    access_classification = Column(String(40), nullable=False)
    employment_status = Column(String(30), nullable=False, default="ACTIVE", index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class DeviceTelemetry(Base):
    """Time-series simulated telemetry snapshot for a campus network device."""
    __tablename__ = "device_telemetry"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    cpu_usage_pct = Column(Float, nullable=False)
    memory_usage_pct = Column(Float, nullable=False)
    temperature_celsius = Column(Float, nullable=False, default=38.0)
    uptime_seconds = Column(Integer, nullable=False, default=0)
    availability_pct = Column(Float, nullable=False, default=100.0)
    latency_ms = Column(Float, nullable=False, default=1.5)
    packet_loss_pct = Column(Float, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default="online")
    telemetry_source = Column(String(20), nullable=False, default="SIMULATION")
    simulation_run_id = Column(String(64), nullable=True, index=True)


class InterfaceTelemetry(Base):
    """Time-series simulated telemetry snapshot for a network interface."""
    __tablename__ = "interface_telemetry"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    interface_id = Column(String(36), ForeignKey("interfaces.id"), nullable=False, index=True)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    inbound_bps = Column(Float, nullable=False, default=0.0)
    outbound_bps = Column(Float, nullable=False, default=0.0)
    utilization_pct = Column(Float, nullable=False, default=0.0)
    input_errors = Column(Integer, nullable=False, default=0)
    output_errors = Column(Integer, nullable=False, default=0)
    input_discards = Column(Integer, nullable=False, default=0)
    output_discards = Column(Integer, nullable=False, default=0)
    operational_status = Column(String(20), nullable=False, default="up")
    duplex = Column(String(10), nullable=False, default="full")
    telemetry_source = Column(String(20), nullable=False, default="SIMULATION")
    simulation_run_id = Column(String(64), nullable=True, index=True)


class FaultScenario(Base):
    """Controlled network fault simulation record (never modifies real hardware)."""
    __tablename__ = "fault_scenarios"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scenario_name = Column(String(120), nullable=False)
    scenario_type = Column(String(40), nullable=False, index=True)
    target_device_id = Column(String(36), ForeignKey("devices.id"), nullable=False, index=True)
    target_interface_id = Column(String(36), ForeignKey("interfaces.id"), nullable=True)
    target_link_id = Column(String(36), ForeignKey("network_links.id"), nullable=True)
    severity = Column(String(20), nullable=False, default="HIGH")
    parameters = Column(JSON, default=dict)
    status = Column(String(20), nullable=False, default="ACTIVE", index=True)  # ACTIVE, RECOVERED
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    ended_at = Column(DateTime, nullable=True)
    max_duration_seconds = Column(Integer, nullable=False, default=1800)
    created_by = Column(String(50), nullable=False)
    simulation_run_id = Column(String(64), nullable=True)
    telemetry_source = Column(String(20), nullable=False, default="SIMULATION")


class IncidentNote(Base):
    """Engineer investigation note attached to an incident."""
    __tablename__ = "incident_notes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False, index=True)
    author = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class IncidentActivity(Base):
    """Immutable investigation timeline entry for an incident."""
    __tablename__ = "incident_activities"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False, index=True)
    actor = Column(String(50), nullable=False)
    action = Column(String(60), nullable=False, index=True)
    details = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class IncidentEscalation(Base):
    """Escalation policy trigger record (prevents duplicate escalation per level)."""
    __tablename__ = "incident_escalations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False, index=True)
    escalation_level = Column(Integer, nullable=False, default=1)
    severity = Column(String(20), nullable=False)
    reason = Column(String(255), nullable=False)
    escalated_to = Column(String(50), nullable=False, default="admin")
    escalated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class CampusService(Base):
    """Logical campus IT/network service backed by infrastructure dependencies."""
    __tablename__ = "campus_services"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    service_key = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)
    service_category = Column(String(50), nullable=False)
    criticality = Column(String(20), nullable=False, default="HIGH")
    owner_team = Column(String(80), nullable=False)
    department_scope = Column(String(50), nullable=False, default="All")
    operational_status = Column(String(30), nullable=False, default="OPERATIONAL")
    sla_target_pct = Column(Float, nullable=False, default=99.5)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ServiceDependency(Base):
    """Maps a CampusService to real DB Device, VLAN, or NetworkLink entities."""
    __tablename__ = "service_dependencies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    service_id = Column(String(36), ForeignKey("campus_services.id"), nullable=False, index=True)
    resource_type = Column(String(20), nullable=False)  # device, vlan, link
    resource_id = Column(String(36), nullable=False, index=True)
    resource_name = Column(String(120), nullable=False)
    dependency_role = Column(String(30), nullable=False, default="PRIMARY")  # PRIMARY, CORE_PATH, REDUNDANT_PATH
    is_critical = Column(Boolean, default=True)


class SecurityDetectionRule(Base):
    """Configurable defensive security detection rule."""
    __tablename__ = "security_detection_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    rule_id = Column(String(40), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    detection_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="MEDIUM")
    threshold = Column(Integer, nullable=False, default=3)
    window_seconds = Column(Integer, nullable=False, default=300)
    cooldown_seconds = Column(Integer, nullable=False, default=120)
    enabled = Column(Boolean, nullable=False, default=True)
    description = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SecurityDetection(Base):
    """Defensive security detection record with deduplication and SIMULATION labeling."""
    __tablename__ = "security_detections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    detection_type = Column(String(50), nullable=False, index=True)
    rule_id = Column(String(40), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=75.0)
    source_device_id = Column(String(36), ForeignKey("devices.id"), nullable=True, index=True)
    source_device_name = Column(String(100), nullable=True)
    related_endpoint = Column(String(100), nullable=True)
    vlan_id = Column(Integer, nullable=True, index=True)
    department = Column(String(100), nullable=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    occurrence_count = Column(Integer, nullable=False, default=1)
    supporting_evidence = Column(JSON, default=list)
    status = Column(String(30), nullable=False, default="OPEN", index=True)
    false_positive_reason = Column(String(255), nullable=True)
    data_source = Column(String(30), nullable=False, default="SIMULATION")
    classification = Column(String(30), nullable=False, default="SIMULATION")
    event_id = Column(String(36), ForeignKey("events.id"), nullable=True)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=True, index=True)


class SecurityEvidence(Base):
    """Append-only security incident evidence record with SHA-256 integrity hash."""
    __tablename__ = "security_evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False, index=True)
    source_detection_id = Column(String(36), ForeignKey("security_detections.id"), nullable=True)
    source_device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)
    source_device_name = Column(String(100), nullable=True)
    evidence_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    description = Column(Text, nullable=False)
    integrity_hash = Column(String(64), nullable=False)
    collection_method = Column(String(50), nullable=False, default="AUTOMATED_SIMULATION")
    data_classification = Column(String(30), nullable=False, default="SIMULATION")
    collected_by = Column(String(50), nullable=False, default="system")
