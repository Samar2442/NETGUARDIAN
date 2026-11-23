const API_BASE = '/api/v1';

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('netguardian_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = 'API request failed';
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errorDetail;
    } catch {
      // ignore
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  // Auth
  login: (data: any) => request<any>('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  getMe: () => request<any>('/auth/me'),

  // Monitoring & Health
  getHealthOverview: () => request<any>('/monitoring/overview'),
  getMetricsHistory: (limit = 24) => request<any[]>(`/monitoring/metrics?limit=${limit}`),
  getEvents: (limit = 50) => request<any[]>(`/monitoring/events?limit=${limit}`),
  pollMetrics: () => request<any>('/monitoring/poll', { method: 'POST' }),

  // Devices & Interfaces
  getDevices: () => request<any[]>('/devices'),
  getDevice: (id: string) => request<any>(`/devices/${id}`),
  getInterfaces: () => request<any[]>('/interfaces'),
  toggleInterfaceAdmin: (id: string, status: string) =>
    request<any>(`/interfaces/${id}/admin-status?status=${status}`, { method: 'PUT' }),

  // VLANs & Routing
  getVlans: () => request<any[]>('/vlans'),
  getRoutes: () => request<any[]>('/routes'),

  // Topology
  getTopology: () => request<any>('/topology'),
  getLinks: () => request<any[]>('/topology/links'),

  // Incidents & RCA
  getIncidents: () => request<any[]>('/incidents'),
  getIncident: (id: string) => request<any>(`/incidents/${id}`),
  runDiagnostics: (incidentId: string) =>
    request<any>(`/diagnostics/run?incident_id=${incidentId}`, { method: 'POST' }),
  getEvidence: (incidentId: string) => request<any>(`/diagnostics/${incidentId}/evidence`),

  // Digital Twin Simulator
  runSimulation: (data: any) => request<any>('/simulator/run', { method: 'POST', body: JSON.stringify(data) }),
  getBlastRadius: (type: string, id: string) =>
    request<any>(`/simulator/blast-radius?target_type=${type}&target_id=${id}`),

  // Remediation
  getRemediations: () => request<any[]>('/remediation'),
  approveRemediation: (id: string, approved_by = 'admin') =>
    request<any>(`/remediation/${id}/approve`, { method: 'POST', body: JSON.stringify({ approved_by }) }),
  rejectRemediation: (id: string, rejected_by = 'admin') =>
    request<any>(`/remediation/${id}/reject`, { method: 'POST', body: JSON.stringify({ rejected_by }) }),
  executeRemediation: (id: string, executed_by = 'admin') =>
    request<any>(`/remediation/${id}/execute`, { method: 'POST', body: JSON.stringify({ executed_by }) }),
  rollbackRemediation: (id: string, username = 'admin') =>
    request<any>(`/remediation/${id}/rollback`, { method: 'POST', body: JSON.stringify({ username }) }),

  // CCNA Training Lab
  getTrainingScenarios: () => request<any[]>('/training/scenarios'),
  injectFault: (scenario_key: string, username = 'admin') =>
    request<any>('/training/inject-fault', { method: 'POST', body: JSON.stringify({ scenario_key, username }) }),
  gradeDiagnosis: (expected: string, student: string) =>
    request<any>('/training/grade-diagnosis', {
      method: 'POST',
      body: JSON.stringify({ expected_root_cause: expected, student_diagnosis: student }),
    }),

  // Drift & Audit
  getDeviceDrift: (deviceId: string) => request<any>(`/drift/compare/${deviceId}`),
  getAuditLogs: (limit = 100) => request<any[]>(`/audit?limit=${limit}`),
};
