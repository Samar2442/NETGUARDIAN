export type UserRole = 'admin' | 'network_engineer' | 'viewer';

export interface User {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface NetworkInterface {
  id: string;
  device_id: string;
  name: string;
  mac_address?: string;
  ip_address?: string;
  subnet_mask?: string;
  admin_status: 'up' | 'down';
  oper_status: 'up' | 'down' | 'error-disabled';
  speed_mbps: number;
  duplex: string;
  mode: 'routed' | 'access' | 'trunk';
  access_vlan?: number;
  allowed_vlans?: string;
  native_vlan: number;
  in_octets: number;
  out_octets: number;
  in_errors: number;
  out_errors: number;
  packet_drops: number;
  bandwidth_utilization_pct: number;
  is_uplink: boolean;
  is_channel_member: boolean;
  channel_group?: number;
  description?: string;
  updated_at: string;
}

export interface Device {
  id: string;
  hostname: string;
  management_ip: string;
  device_type: 'router' | 'l3_switch' | 'l2_switch' | 'access_switch' | 'server' | 'endpoint';
  vendor: string;
  model: string;
  os_version: string;
  location: string;
  status: 'online' | 'degraded' | 'offline';
  monitoring_status: string;
  uptime_seconds: number;
  cpu_percent: number;
  memory_percent: number;
  last_seen: string;
  created_at: string;
  updated_at: string;
  interfaces: NetworkInterface[];
}

export interface VLAN {
  id: string;
  vlan_id: number;
  name: string;
  description?: string;
  subnet: string;
  gateway_ip: string;
  status: string;
  created_at: string;
}

export interface Route {
  id: string;
  device_id: string;
  destination_network: string;
  netmask: string;
  next_hop?: string;
  outgoing_interface?: string;
  protocol: string;
  metric: number;
  is_active: boolean;
  updated_at: string;
}

export interface NetworkLink {
  id: string;
  name: string;
  source_device_id: string;
  source_interface_name: string;
  target_device_id: string;
  target_interface_name: string;
  link_type: string;
  status: 'up' | 'degraded' | 'down';
  bandwidth_mbps: number;
  latency_ms: number;
  packet_loss_pct: number;
  is_redundant: boolean;
  updated_at: string;
}

export interface Event {
  id: string;
  timestamp: string;
  source_type: string;
  source_id?: string;
  source_name: string;
  event_type: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  message: string;
  details: Record<string, any>;
  raw_payload?: string;
  is_correlated: boolean;
  incident_id?: string;
}

export interface Diagnosis {
  id: string;
  incident_id: string;
  root_cause: string;
  category: string;
  confidence: number;
  severity: string;
  explanation: string;
  supporting_evidence: string[];
  contradicting_evidence: string[];
  recommended_action: string;
  verification_steps: string[];
  evidence_graph: {
    nodes: Array<{ id: string; label: string; type: string; status?: string }>;
    edges: Array<{ source: string; target: string; label: string }>;
  };
  created_at: string;
}

export interface RemediationProposal {
  id: string;
  incident_id: string;
  device_id: string;
  title: string;
  target_interface?: string;
  proposed_commands: string;
  rollback_commands: string;
  risk_level: 'low' | 'medium' | 'high';
  expected_result: string;
  status: 'PENDING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'EXECUTING' | 'APPLIED' | 'VERIFYING' | 'VERIFIED' | 'FAILED' | 'ROLLED_BACK';
  approved_by?: string;
  approved_at?: string;
  applied_at?: string;
  verification_status?: string;
  execution_log?: string;
  rollback_log?: string;
  created_at: string;
}

export interface Incident {
  id: string;
  incident_number: string;
  title: string;
  description: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  status: 'DETECTED' | 'INVESTIGATING' | 'ROOT_CAUSE_IDENTIFIED' | 'REMEDIATION_PROPOSED' | 'APPROVED' | 'APPLIED' | 'VERIFICATION' | 'RESOLVED' | 'ROLLBACK' | 'ESCALATED';
  source_device_id?: string;
  source_device_name?: string;
  affected_device_ids: string[];
  affected_vlan_ids: number[];
  affected_endpoints_count: number;
  created_at: string;
  updated_at: string;
  resolved_at?: string;
  diagnosis?: Diagnosis;
  remediations: RemediationProposal[];
}

export interface HealthOverview {
  overall_health: number;
  availability: number;
  performance: number;
  configuration: number;
  security: number;
  redundancy: number;
  risk_score: number;
  active_incidents: number;
  critical_alerts: number;
  total_devices: number;
  online_devices: number;
  offline_devices: number;
  avg_latency_ms: number;
  avg_packet_loss_pct: number;
  environment: string;
  is_demo: boolean;
}

export interface AuditLog {
  id: string;
  timestamp: string;
  user_id?: string;
  username: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  details: Record<string, any>;
  ip_address: string;
  status: string;
}

export interface TrainingScenario {
  id: string;
  scenario_key: string;
  title: string;
  difficulty: string;
  category: string;
  description: string;
  fault_type: string;
  target_device: string;
  target_component: string;
  symptoms: string[];
  expected_root_cause: string;
  recommended_commands: string;
}
