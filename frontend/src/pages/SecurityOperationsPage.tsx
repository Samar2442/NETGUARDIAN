import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { StatCard } from '../components/common/StatCard';
import { Badge } from '../components/common/Badge';
import { Network3DCard } from '../components/3d/Network3DCard';
import { ShieldAlert, ShieldCheck, Lock, FileCheck2, AlertTriangle, Clock } from 'lucide-react';

export const SecurityOperationsPage: React.FC = () => {
  const [overview, setOverview] = useState<any | null>(null);
  const [detections, setDetections] = useState<any[]>([]);
  const [selectedDetection, setSelectedDetection] = useState<any | null>(null);
  const [vlanAssess, setVlanAssess] = useState<any | null>(null);
  const [deviceAssess, setDeviceAssess] = useState<any[]>([]);
  const [secIncidents, setSecIncidents] = useState<any[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<any | null>(null);
  const [evidence, setEvidence] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [recommendations, setRecommendations] = useState<any | null>(null);

  // Filters
  const [severityFilter, setSeverityFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [deviceFilter, setDeviceFilter] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [hoursFilter, setHoursFilter] = useState(24);

  // Evidence form
  const [evDesc, setEvDesc] = useState('');
  const [sceneDevices, setSceneDevices] = useState<any[]>([]);
  const [sceneLinks, setSceneLinks] = useState<any[]>([]);

  const loadAll = async () => {
    const [ov, dets, vl, devs, incs, rawDevs, rawLinks] = await Promise.all([
      api.getSecurityOverview().catch(() => null),
      api.getSecurityDetections({
        severity: severityFilter || undefined,
        detection_type: typeFilter || undefined,
        device: deviceFilter || undefined,
        department: deptFilter || undefined,
        status: statusFilter || undefined,
        hours: hoursFilter,
      }).catch(() => ({ items: [] })),
      api.getVlanSecurityAssessment().catch(() => null),
      api.getDeviceSecurityAssessments(20).catch(() => ({ items: [] })),
      api.getSecurityIncidents(30).catch(() => ({ items: [] })),
      api.getDevices().catch(() => []),
      api.getLinks().catch(() => []),
    ]);
    setOverview(ov);
    setDetections(dets?.items || []);
    setSceneDevices(rawDevs || []);
    setSceneLinks(rawLinks || []);
    if (!selectedDetection && dets?.items?.length) setSelectedDetection(dets.items[0]);
    setVlanAssess(vl);
    setDeviceAssess(devs?.items || []);
    setSecIncidents(incs?.items || []);
    if (!selectedIncident && incs?.items?.length) {
      loadIncidentDetail(incs.items[0]);
    }
  };

  const loadIncidentDetail = async (inc: any) => {
    setSelectedIncident(inc);
    const [ev, tl, rec] = await Promise.all([
      api.getSecurityIncidentEvidence(inc.id).catch(() => []),
      api.getIncidentTimeline(inc.id).catch(() => []),
      api.getSecurityIncidentRecommendations(inc.id).catch(() => null),
    ]);
    setEvidence(ev || []);
    setTimeline(tl || []);
    setRecommendations(rec);
  };

  useEffect(() => {
    loadAll();
  }, [severityFilter, typeFilter, deviceFilter, deptFilter, statusFilter, hoursFilter]);

  const handleMarkFalsePositive = async (detId: string) => {
    await api.markDetectionFalsePositive(detId, 'Reviewed and marked false positive by operator');
    loadAll();
  };

  const handleAddEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedIncident || !evDesc.trim()) return;
    await api.addSecurityIncidentEvidence(selectedIncident.id, {
      evidence_type: 'OPERATOR_OBSERVATION',
      description: evDesc.trim(),
      source_device_name: selectedIncident.source_device_name,
    });
    setEvDesc('');
    loadIncidentDetail(selectedIncident);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <ShieldAlert className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-slate-900 dark:text-white">Network Security Operations Center (SecOps)</h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Defensive threat detection, configuration posture assessment, and integrity-verified evidence management.
          </p>
        </div>
        <Badge variant="info">DATA SOURCE: SIMULATION (DEFENSIVE CAMPUS MODEL)</Badge>
      </div>

      <Network3DCard
        title="3D Security Event Heat Map"
        subtitle="Highlights campus devices associated with active defensive detections"
        nodes={sceneDevices}
        links={sceneLinks}
        mode="security"
        highlightIds={detections.map((d) => d.device_id).filter(Boolean)}
        heightClass="h-56"
      />

      {/* Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Security Posture Score"
          value={overview ? `${overview.overall_posture_score}%` : '—'}
          subtitle="VLAN / ACL / Firewall baseline"
          icon={ShieldCheck}
          color="cyan"
        />
        <StatCard
          title="Open Detections"
          value={String(overview?.open_detections ?? detections.length)}
          subtitle="Deduplicated defensive alerts"
          icon={AlertTriangle}
          color="amber"
        />
        <StatCard
          title="High / Critical Alerts"
          value={String(overview?.high_critical_detections ?? 0)}
          subtitle="Prioritized security signals"
          icon={ShieldAlert}
          color="rose"
        />
        <StatCard
          title="Security Incidents"
          value={String(secIncidents.length)}
          subtitle="Integrated incident lifecycle"
          icon={Lock}
          color="indigo"
        />
      </div>

      {/* Filters & Detection Feed */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xs font-mono uppercase text-slate-700 dark:text-slate-300 font-bold">Security Event &amp; Detection Feed</h2>
          <div className="flex flex-wrap gap-2 text-xs font-mono">
            <select value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} className="bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded px-2 py-1 text-slate-800 dark:text-slate-200">
              <option value="">All Severities</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>
            <select value={deptFilter} onChange={(e) => setDeptFilter(e.target.value)} className="bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded px-2 py-1 text-slate-800 dark:text-slate-200">
              <option value="">All Departments</option>
              <option value="CSE">CSE (VLAN 10)</option>
              <option value="IT">IT (VLAN 20)</option>
              <option value="ECE">ECE (VLAN 30)</option>
            </select>
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded px-2 py-1 text-slate-800 dark:text-slate-200">
              <option value="">All Statuses</option>
              <option value="OPEN">OPEN</option>
              <option value="CORRELATED">CORRELATED</option>
              <option value="SUPPRESSED">SUPPRESSED</option>
              <option value="FALSE_POSITIVE">FALSE_POSITIVE</option>
            </select>
            <select value={hoursFilter} onChange={(e) => setHoursFilter(Number(e.target.value))} className="bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded px-2 py-1 text-slate-800 dark:text-slate-200">
              <option value={24}>Last 24h</option>
              <option value={72}>Last 72h</option>
              <option value={168}>Last 7d</option>
            </select>
            <input
              value={deviceFilter}
              onChange={(e) => setDeviceFilter(e.target.value)}
              placeholder="Filter device..."
              className="bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded px-2 py-1 text-slate-800 dark:text-slate-200 w-36"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 overflow-x-auto max-h-64 overflow-y-auto">
            <table className="w-full text-xs font-mono text-left">
              <thead className="text-[10px] text-slate-500 dark:text-slate-400 uppercase border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-2 pr-2">Type</th>
                  <th className="py-2 pr-2">Device</th>
                  <th className="py-2 pr-2">VLAN</th>
                  <th className="py-2 pr-2">Severity</th>
                  <th className="py-2 pr-2">Class</th>
                  <th className="py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {detections.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-500">No security detections in selected window.</td>
                  </tr>
                ) : (
                  detections.map((d) => (
                    <tr
                      key={d.id}
                      onClick={() => setSelectedDetection(d)}
                      className="cursor-pointer hover:bg-slate-800/40 text-slate-700 dark:text-slate-300"
                    >
                      <td className="py-2 pr-2 font-semibold">{d.detection_type}</td>
                      <td className="py-2 pr-2">{d.source_device_name || '—'}</td>
                      <td className="py-2 pr-2">{d.vlan_id ?? '—'}</td>
                      <td className="py-2 pr-2">
                        <Badge variant={d.severity === 'CRITICAL' || d.severity === 'HIGH' ? 'danger' : 'warning'}>{d.severity}</Badge>
                      </td>
                      <td className="py-2 pr-2">{d.classification}</td>
                      <td className="py-2">{d.status} (x{d.occurrence_count})</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded p-3 text-xs font-mono space-y-2">
            <div className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-bold">Detection Detail</div>
            {selectedDetection ? (
              <>
                <div className="text-slate-800 dark:text-slate-200 font-bold">{selectedDetection.detection_type} ({selectedDetection.rule_id})</div>
                <div className="text-slate-500 dark:text-slate-400">Confidence: {selectedDetection.confidence}% • Class: {selectedDetection.classification}</div>
                <ul className="space-y-1 text-slate-700 dark:text-slate-300 text-[11px]">
                  {(selectedDetection.supporting_evidence || []).map((e: string, idx: number) => (
                    <li key={idx}>• {e}</li>
                  ))}
                </ul>
                {selectedDetection.status !== 'FALSE_POSITIVE' && (
                  <button
                    onClick={() => handleMarkFalsePositive(selectedDetection.id)}
                    className="mt-2 px-2.5 py-1 rounded bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-[11px]"
                  >
                    Mark False Positive
                  </button>
                )}
              </>
            ) : (
              <div className="text-slate-500">Select a detection to inspect evidence.</div>
            )}
          </div>
        </div>
      </div>

      {/* VLAN Segmentation & Device Security Assessment */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-mono uppercase text-slate-700 dark:text-slate-300 font-bold">VLAN Segmentation Assessment</h3>
            <Badge variant={vlanAssess?.status === 'ASSESSED' ? 'success' : 'warning'}>
              {vlanAssess?.status || 'UNKNOWN'}
            </Badge>
          </div>
          <div className="space-y-2 text-xs font-mono">
            {(vlanAssess?.vlans || []).map((v: any) => (
              <div key={v.vlan_id} className="p-3 rounded bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800">
                <div className="flex justify-between font-bold text-slate-800 dark:text-slate-200">
                  <span>VLAN {v.vlan_id} ({v.department}) — {v.subnet}</span>
                  <span className="text-cyan-400">{v.score}% ({v.status})</span>
                </div>
                <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">{v.note}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 space-y-3">
          <h3 className="text-xs font-mono uppercase text-slate-700 dark:text-slate-300 font-bold">Device Security Baseline</h3>
          <div className="overflow-x-auto max-h-60 overflow-y-auto">
            <table className="w-full text-xs font-mono text-left">
              <thead className="text-[10px] text-slate-500 dark:text-slate-400 uppercase border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="py-1.5 pr-2">Device</th>
                  <th className="py-1.5 pr-2">Dept</th>
                  <th className="py-1.5 pr-2">Score</th>
                  <th className="py-1.5">State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {deviceAssess.map((d) => (
                  <tr key={d.device_id} className="text-slate-700 dark:text-slate-300">
                    <td className="py-1.5 pr-2 font-semibold">{d.hostname}</td>
                    <td className="py-1.5 pr-2">{d.department || 'Core'}</td>
                    <td className="py-1.5 pr-2">{d.score}%</td>
                    <td className="py-1.5">
                      <Badge variant={d.status === 'UNKNOWN' || d.status === 'NOT_ASSESSED' ? 'neutral' : 'info'}>{d.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Security Incidents, Evidence Viewer, Timeline & Recommendations */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 space-y-4">
        <h3 className="text-xs font-mono uppercase text-slate-700 dark:text-slate-300 font-bold">Security Incidents, Immutable Evidence &amp; Response</h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {secIncidents.length === 0 ? (
              <div className="text-xs font-mono text-slate-500">No security incidents recorded.</div>
            ) : (
              secIncidents.map((inc) => (
                <div
                  key={inc.id}
                  onClick={() => loadIncidentDetail(inc)}
                  className={`p-3 rounded border cursor-pointer text-xs font-mono ${
                    selectedIncident?.id === inc.id
                      ? 'bg-slate-100 dark:bg-slate-800 border-cyan-500/60'
                      : 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:border-slate-700'
                  }`}
                >
                  <div className="flex justify-between font-bold text-slate-800 dark:text-slate-200">
                    <span>{inc.incident_number}</span>
                    <Badge variant={inc.security_severity === 'CRITICAL' ? 'danger' : 'warning'}>{inc.security_severity}</Badge>
                  </div>
                  <div className="text-slate-500 dark:text-slate-400 mt-1 truncate">{inc.title}</div>
                </div>
              ))
            )}
          </div>

          <div className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded p-3 text-xs font-mono space-y-2">
            <div className="flex items-center space-x-2 text-cyan-400 font-bold uppercase text-[10px]">
              <FileCheck2 className="w-3.5 h-3.5" />
              <span>Evidence Records (SHA-256)</span>
            </div>
            <div className="space-y-1.5 max-h-40 overflow-y-auto">
              {evidence.map((ev) => (
                <div key={ev.id} className="p-2 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                  <div className="flex justify-between">
                    <span className="font-bold text-slate-800 dark:text-slate-200">{ev.evidence_type}</span>
                    <Badge variant={ev.integrity_valid ? 'success' : 'danger'}>
                      {ev.integrity_valid ? 'HASH VALID' : 'TAMPERED'}
                    </Badge>
                  </div>
                  <div className="text-slate-700 dark:text-slate-300 mt-1">{ev.description}</div>
                  <div className="text-[10px] text-slate-500 mt-1 truncate">SHA-256: {ev.integrity_hash}</div>
                </div>
              ))}
            </div>
            {selectedIncident && (
              <form onSubmit={handleAddEvidence} className="flex gap-2 pt-1">
                <input
                  value={evDesc}
                  onChange={(e) => setEvDesc(e.target.value)}
                  placeholder="Append evidence note..."
                  className="flex-1 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded px-2 py-1 text-xs text-slate-800 dark:text-slate-200"
                />
                <button type="submit" className="px-2.5 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-xs">
                  Add
                </button>
              </form>
            )}
          </div>

          <div className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded p-3 text-xs font-mono space-y-3">
            <div>
              <div className="flex items-center space-x-2 text-amber-400 font-bold uppercase text-[10px] mb-1">
                <Clock className="w-3.5 h-3.5" />
                <span>Investigation Timeline &amp; Recommendations</span>
              </div>
              <ul className="space-y-1 text-slate-700 dark:text-slate-300 text-[11px] max-h-28 overflow-y-auto">
                {timeline.map((t, i) => (
                  <li key={i}>• [{t.action}] {t.actor}</li>
                ))}
              </ul>
            </div>
            {recommendations?.recommendations && (
              <ul className="space-y-1 text-emerald-300 text-[11px] border-t border-slate-200 dark:border-slate-800 pt-2">
                {recommendations.recommendations.map((r: string, i: number) => (
                  <li key={i}>→ {r}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
