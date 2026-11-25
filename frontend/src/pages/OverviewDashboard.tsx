import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { HealthOverview, Incident } from '../types';
import { StatCard } from '../components/common/StatCard';
import { Badge } from '../components/common/Badge';
import { Network3DCard } from '../components/3d/Network3DCard';
import { Link } from 'react-router-dom';
import {
  Server,
  AlertTriangle,
  Activity,
  ShieldCheck,
  Zap,
  ArrowRight,
  TrendingDown,
  Layers,
  CheckCircle2,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

export const OverviewDashboard: React.FC = () => {
  const [health, setHealth] = useState<HealthOverview | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [metricsHistory, setMetricsHistory] = useState<any[]>([]);
  const [devices, setDevices] = useState<any[]>([]);
  const [links, setLinks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [h, incs, hist, devs, lks] = await Promise.all([
        api.getHealthOverview(),
        api.getIncidents(),
        api.getMetricsHistory(15),
        api.getDevices().catch(() => []),
        api.getLinks().catch(() => []),
      ]);
      setHealth(h);
      setIncidents(incs);
      setMetricsHistory(hist);
      setDevices(devs || []);
      setLinks(lks || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">Operations Overview</h1>
            <Badge variant="info">DEMO LAB: ACTIVE</Badge>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Real-time Cisco infrastructure health, active incidents, and automated correlation telemetry.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Link
            to="/training"
            className="px-3.5 py-2 bg-indigo-50 dark:bg-indigo-600/20 hover:bg-indigo-100 dark:hover:bg-indigo-600/30 text-indigo-600 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 rounded text-xs font-semibold font-mono flex items-center space-x-2 transition-colors"
          >
            <span>CCNA Fault Injection</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
          <Link
            to="/remediation"
            className="px-3.5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold flex items-center space-x-2 transition-colors"
          >
            <span>Remediation Hub</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          title="Network Health Score"
          value={`${health?.overall_health ?? 96}%`}
          subtitle="Availability: 98% | Config: 96%"
          icon={Activity}
          color={(health?.overall_health ?? 100) > 85 ? 'emerald' : 'amber'}
        />
        <StatCard
          title="Network Risk Score"
          value={`${health?.risk_score ?? 4}%`}
          subtitle="Impact on core services"
          icon={TrendingDown}
          color={(health?.risk_score ?? 0) > 20 ? 'rose' : 'cyan'}
        />
        <StatCard
          title="Monitored Devices"
          value={`${health?.online_devices ?? 11} / ${health?.total_devices ?? 11}`}
          subtitle={`${health?.offline_devices ?? 0} Offline`}
          icon={Server}
          color="cyan"
        />
        <StatCard
          title="Active Incidents"
          value={health?.active_incidents ?? 0}
          subtitle={`${health?.critical_alerts ?? 0} Critical / High`}
          icon={AlertTriangle}
          color={(health?.active_incidents ?? 0) > 0 ? 'rose' : 'emerald'}
        />
        <StatCard
          title="Average Latency"
          value={`${health?.avg_latency_ms ?? 1.2} ms`}
          subtitle={`Loss: ${health?.avg_packet_loss_pct ?? 0}%`}
          icon={Zap}
          color="indigo"
        />
      </div>

      {/* Middle row: Trend Chart & Health Components */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Telemetry Chart */}
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Historical Health &amp; Performance Trend</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">Live 10-second polling window telemetry</p>
            </div>
            <Badge variant="success">LIVE TELEMETRY</Badge>
          </div>
          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metricsHistory.length ? metricsHistory : [
                { timestamp: '1', overall_health: 96, risk_score: 4 },
                { timestamp: '2', overall_health: 95, risk_score: 5 },
                { timestamp: '3', overall_health: 96, risk_score: 4 },
                { timestamp: '4', overall_health: 94, risk_score: 6 },
              ]}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" className="dark:stroke-slate-800" />
                <XAxis dataKey="timestamp" stroke="#94a3b8" tick={false} />
                <YAxis domain={[0, 100]} stroke="#94a3b8" textAnchor="end" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Line
                  type="monotone"
                  dataKey="overall_health"
                  stroke="#10b981"
                  strokeWidth={2}
                  name="Health Score (%)"
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="risk_score"
                  stroke="#ef4444"
                  strokeWidth={2}
                  name="Risk Index"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Formula Breakdown */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center space-x-2 mb-2">
              <ShieldCheck className="w-5 h-5 text-cyan-500 dark:text-cyan-400" />
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Formula Breakdown</h2>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
              Calculated using documented diagnostic weights (never arbitrary AI scores):
            </p>

            <div className="space-y-3 font-mono text-xs">
              {[
                { label: 'Availability (30%)', value: health?.availability ?? 98, color: 'bg-emerald-500' },
                { label: 'Performance (20%)', value: health?.performance ?? 94, color: 'bg-cyan-500' },
                { label: 'Configuration (20%)', value: health?.configuration ?? 96, color: 'bg-blue-500' },
                { label: 'Security (15%)', value: health?.security ?? 92, color: 'bg-indigo-500' },
                { label: 'Redundancy (15%)', value: health?.redundancy ?? 91, color: 'bg-amber-500' },
              ].map(item => (
                <div key={item.label}>
                  <div className="flex justify-between text-slate-700 dark:text-slate-300 mb-1">
                    <span>{item.label}</span>
                    <span>{item.value}%</span>
                  </div>
                  <div className="w-full bg-slate-100 dark:bg-slate-950 rounded-full h-1.5">
                    <div className={`${item.color} h-1.5 rounded-full`} style={{ width: `${item.value}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 p-3 rounded bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-[11px] font-mono text-slate-500 dark:text-slate-400">
            Health = (Avail × 0.3) + (Perf × 0.2) + (Config × 0.2) + (Sec × 0.15) + (Redun × 0.15)
          </div>
        </div>
      </div>

      {/* 3D Campus Health Overview */}
      <Network3DCard
        title="Campus Network 3D Health Map"
        subtitle="Live 3-tier topology colored by device operational status (SIMULATION)"
        nodes={devices}
        links={links}
        mode="health"
        heightClass="h-64"
      />

      {/* Active Incidents & Correlation Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-500 dark:text-amber-400" />
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Correlated Active Incidents</h2>
          </div>
          <Link to="/incidents" className="text-xs text-cyan-600 dark:text-cyan-400 hover:underline font-mono">
            View All Incidents →
          </Link>
        </div>

        {incidents.length === 0 ? (
          <div className="p-8 text-center text-slate-500 dark:text-slate-400 font-mono text-xs">
            <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-80" />
            No active incidents detected. Cisco infrastructure operating at nominal baseline.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-50 dark:bg-slate-950/80 text-slate-500 dark:text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="p-3">Incident ID</th>
                  <th className="p-3">Title</th>
                  <th className="p-3">Severity</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Source Device</th>
                  <th className="p-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {incidents.slice(0, 5).map((inc) => (
                  <tr key={inc.id} className="hover:bg-slate-50 dark:hover:bg-slate-850/50 transition-colors">
                    <td className="p-3 text-cyan-600 dark:text-cyan-400 font-bold">{inc.incident_number}</td>
                    <td className="p-3 text-slate-800 dark:text-slate-200">{inc.title}</td>
                    <td className="p-3">
                      <Badge variant={inc.severity === 'critical' || inc.severity === 'high' ? 'danger' : 'warning'}>
                        {inc.severity.toUpperCase()}
                      </Badge>
                    </td>
                    <td className="p-3">
                      <Badge variant={inc.status === 'RESOLVED' ? 'success' : 'purple'}>
                        {inc.status}
                      </Badge>
                    </td>
                    <td className="p-3 text-slate-700 dark:text-slate-300">{inc.source_device_name || 'N/A'}</td>
                    <td className="p-3">
                      <Link
                        to={`/diagnostics?incident=${inc.id}`}
                        className="px-2.5 py-1 bg-cyan-50 dark:bg-cyan-950 hover:bg-cyan-100 dark:hover:bg-cyan-900 text-cyan-600 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-800 rounded text-[11px] transition-colors"
                      >
                        Inspect RCA →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
