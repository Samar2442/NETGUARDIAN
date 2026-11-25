import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Badge } from '../components/common/Badge';
import { StatCard } from '../components/common/StatCard';
import { ShieldCheck, Layers, Clock, Download } from 'lucide-react';

export const ServicesSlaPage: React.FC = () => {
  const [services, setServices] = useState<any[]>([]);
  const [slaOverview, setSlaOverview] = useState<any | null>(null);
  const [metrics, setMetrics] = useState<any | null>(null);
  const [deps, setDeps] = useState<any[]>([]);
  const [selectedName, setSelectedName] = useState<string>('');

  const loadData = async () => {
    try {
      const [svcs, sla, met] = await Promise.all([
        api.getCampusServices(),
        api.getSlaOverview(),
        api.getSlaMetrics(),
      ]);
      setServices(svcs);
      setSlaOverview(sla);
      setMetrics(met);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const inspectDeps = async (svc: any) => {
    setSelectedName(svc.name);
    const d = await api.getServiceDependencies(svc.id);
    setDeps(d);
  };

  const downloadReport = async (reportType: string, format: 'csv' | 'pdf') => {
    const token = localStorage.getItem('netguardian_token');
    const res = await fetch(`/api/v1/reports/${reportType}?format=${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `netguardian_${reportType}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <ShieldCheck className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-slate-900 dark:text-white">Campus Service Intelligence, SLA & Management Reporting</h1>
            <Badge variant="info">SIMULATION / DEMO SLA</Badge>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Dependency-aware service health across 7 campus services, MTTD/MTTA/MTTR metrics, and CSV/PDF management reports.
          </p>
        </div>
      </div>

      {slaOverview && metrics && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="SLA Compliance" value={`${slaOverview.compliance_pct}%`} subtitle={`${slaOverview.compliant_services} / ${slaOverview.total_services} Services`} icon={ShieldCheck} color="emerald" />
          <StatCard title="MTTD (Simulated)" value={metrics.mttd_seconds !== null ? `${metrics.mttd_seconds}s` : 'N/A'} subtitle="Mean Time to Detect" icon={Clock} color="cyan" />
          <StatCard title="MTTA" value={metrics.mtta_seconds !== null ? `${metrics.mtta_seconds}s` : 'Insufficient Data'} subtitle={`Samples: ${metrics.mtta_sample_size}`} icon={Clock} color="indigo" />
          <StatCard title="MTTR" value={metrics.mttr_seconds !== null ? `${metrics.mttr_seconds}s` : 'Insufficient Data'} subtitle={`Samples: ${metrics.mttr_sample_size}`} icon={Clock} color="amber" />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="px-4 py-2.5">Campus Service</th>
                <th className="px-4 py-2.5">Scope</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Availability</th>
                <th className="px-4 py-2.5">SLA Target</th>
                <th className="px-4 py-2.5">Compliance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800 text-slate-800 dark:text-slate-200">
              {services.map((s) => (
                <tr key={s.id} onClick={() => inspectDeps(s)} className="hover:bg-slate-800/50 cursor-pointer">
                  <td className="px-4 py-2.5 font-bold text-cyan-400">{s.name}</td>
                  <td className="px-4 py-2.5">{s.department_scope}</td>
                  <td className="px-4 py-2.5">
                    <Badge variant={s.operational_status === 'OPERATIONAL' ? 'success' : s.operational_status === 'OUTAGE' ? 'danger' : 'warning'}>
                      {s.operational_status}
                    </Badge>
                  </td>
                  <td className="px-4 py-2.5">{s.availability_pct}%</td>
                  <td className="px-4 py-2.5">{s.sla_target_pct}%</td>
                  <td className="px-4 py-2.5">
                    <Badge variant={s.sla_compliant ? 'success' : 'danger'}>{s.sla_compliant ? 'COMPLIANT' : 'BREACH'}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 font-mono text-xs space-y-3 h-fit">
          <div className="text-slate-500 dark:text-slate-400 uppercase border-b border-slate-200 dark:border-slate-800 pb-2 flex items-center space-x-2">
            <Layers className="w-4 h-4 text-cyan-400" />
            <span>Dependencies {selectedName ? `— ${selectedName}` : ''}</span>
          </div>
          {deps.length === 0 ? (
            <div className="text-slate-500">Click a service row to inspect its infrastructure dependencies.</div>
          ) : (
            <div className="space-y-1.5 max-h-64 overflow-y-auto">
              {deps.map((d) => (
                <div key={d.id} className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-2.5 py-1.5 flex justify-between">
                  <span>{d.resource_name}</span>
                  <Badge variant={d.dependency_role === 'REDUNDANT_PATH' ? 'info' : 'neutral'}>{d.dependency_role}</Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Management Reporting Export Bar */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <h2 className="text-xs font-mono uppercase text-slate-500 dark:text-slate-400 mb-3">Management Reports (CSV / PDF Exports)</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 font-mono text-xs">
          {[
            ['daily_incidents', 'Daily Incident Summary'],
            ['weekly_incidents', 'Weekly Incident Summary'],
            ['monthly_sla', 'Monthly SLA Report'],
            ['department_health', 'Department Network Health'],
            ['critical_incidents', 'Critical Incident Report'],
            ['engineer_workload', 'Engineer Workload Summary'],
          ].map(([key, label]) => (
            <div key={key} className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded p-3 flex items-center justify-between">
              <span className="text-slate-800 dark:text-slate-200">{label}</span>
              <div className="flex space-x-1.5">
                <button onClick={() => downloadReport(key, 'csv')} className="px-2 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-cyan-300 rounded flex items-center space-x-1">
                  <Download className="w-3 h-3" /><span>CSV</span>
                </button>
                <button onClick={() => downloadReport(key, 'pdf')} className="px-2 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-amber-300 rounded flex items-center space-x-1">
                  <Download className="w-3 h-3" /><span>PDF</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
