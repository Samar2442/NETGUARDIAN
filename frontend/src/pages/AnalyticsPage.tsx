import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { HealthOverview } from '../types';
import { StatCard } from '../components/common/StatCard';
import { Badge } from '../components/common/Badge';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  BarChart,
  Bar,
} from 'recharts';
import { LineChart as AnalyticsIcon, Clock, ShieldCheck, Zap, Activity, AlertTriangle, TrendingUp } from 'lucide-react';

export const AnalyticsPage: React.FC = () => {
  const [health, setHealth] = useState<HealthOverview | null>(null);
  const [metrics, setMetrics] = useState<any[]>([]);
  const [predOverview, setPredOverview] = useState<any | null>(null);
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [forecasts, setForecasts] = useState<any[]>([]);
  const [horizon, setHorizon] = useState<number>(60);

  const loadAnalytics = (h: number) => {
    Promise.all([
      api.getHealthOverview().catch(() => null),
      api.getMetricsHistory(24).catch(() => []),
      api.getAnalyticsOverview(24, h).catch(() => null),
      api.getAnalyticsAnomalies(24, 25).catch(() => ({ anomalies: [] })),
      api.getCapacityForecast(24, h, 15).catch(() => ({ forecasts: [] })),
    ]).then(([hl, m, po, an, fc]) => {
      if (hl) setHealth(hl);
      setMetrics(m || []);
      setPredOverview(po);
      setAnomalies(an?.anomalies || []);
      setForecasts(fc?.forecasts || []);
    });
  };

  useEffect(() => {
    loadAnalytics(horizon);
  }, [horizon]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <AnalyticsIcon className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-slate-900 dark:text-white">Network Analytics & Reliability Trends</h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Statistical anomaly detection, capacity exhaustion forecasting, and reliability trends (SIMULATION).
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Badge variant={predOverview?.classification === 'INSUFFICIENT_DATA' ? 'warning' : 'info'}>
            {predOverview?.data_source || 'SIMULATION'} • {predOverview?.classification || 'LOADING'}
          </Badge>
          <select
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="bg-slate-50 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-800 dark:text-slate-200 font-mono"
          >
            <option value={60}>Horizon: 60m</option>
            <option value={240}>Horizon: 4h</option>
            <option value={720}>Horizon: 12h</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Detected Anomalies"
          value={String(predOverview?.anomalies_detected ?? anomalies.length)}
          subtitle="Statistical deviations (not incidents)"
          icon={AlertTriangle}
          color="amber"
        />
        <StatCard
          title="Predictive Warnings"
          value={String(predOverview?.predictive_warnings ?? 0)}
          subtitle={`Forecast horizon: ${horizon} min`}
          icon={TrendingUp}
          color="rose"
        />
        <StatCard
          title="Telemetry Samples (24h)"
          value={String(predOverview?.sample_count ?? 0)}
          subtitle="Real simulated observations"
          icon={Clock}
          color="cyan"
        />
        <StatCard
          title="Infrastructure Uptime"
          value={health ? `${health.overall_health?.toFixed(1)}%` : '99.9%'}
          subtitle="Campus topology health"
          icon={Activity}
          color="emerald"
        />
      </div>

      {/* Anomaly Detection & Capacity Forecasting Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-mono uppercase text-slate-500 dark:text-slate-400">Statistical Anomaly Feed</h3>
            <span className="text-[11px] font-mono text-slate-500">Moving Avg &amp; Rolling StdDev</span>
          </div>
          {anomalies.length === 0 ? (
            <div className="text-xs font-mono text-slate-500 py-8 text-center">
              No statistical anomalies detected in the selected 24h window.
            </div>
          ) : (
            <div className="overflow-x-auto max-h-72 overflow-y-auto">
              <table className="w-full text-xs font-mono text-left">
                <thead className="text-[10px] text-slate-500 dark:text-slate-400 uppercase border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-2 pr-2">Entity</th>
                    <th className="py-2 pr-2">Type</th>
                    <th className="py-2 pr-2">Observed / Mean</th>
                    <th className="py-2">Severity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {anomalies.map((a, idx) => (
                    <tr key={idx} className="text-slate-700 dark:text-slate-300">
                      <td className="py-2 pr-2 font-semibold">{a.entity_name}</td>
                      <td className="py-2 pr-2">{a.anomaly_type}</td>
                      <td className="py-2 pr-2">{a.observed_value} / {a.baseline_mean} (z={a.z_score})</td>
                      <td className="py-2">
                        <Badge variant={a.severity === 'CRITICAL' ? 'danger' : 'warning'}>{a.severity}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-mono uppercase text-slate-500 dark:text-slate-400">Capacity Exhaustion Forecast ({horizon}m)</h3>
            <span className="text-[11px] font-mono text-slate-500">Linear Trend Regression</span>
          </div>
          {forecasts.length === 0 ? (
            <div className="text-xs font-mono text-slate-500 py-8 text-center">
              INSUFFICIENT_DATA: Waiting for at least 3 telemetry samples per device.
            </div>
          ) : (
            <div className="overflow-x-auto max-h-72 overflow-y-auto">
              <table className="w-full text-xs font-mono text-left">
                <thead className="text-[10px] text-slate-500 dark:text-slate-400 uppercase border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-2 pr-2">Device</th>
                    <th className="py-2 pr-2">Current</th>
                    <th className="py-2 pr-2">Predicted</th>
                    <th className="py-2 pr-2">Slope/hr</th>
                    <th className="py-2">State</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {forecasts.map((f, idx) => (
                    <tr key={idx} className="text-slate-700 dark:text-slate-300">
                      <td className="py-2 pr-2 font-semibold">{f.entity_name}</td>
                      <td className="py-2 pr-2">{f.current_value !== null ? `${f.current_value}%` : '—'}</td>
                      <td className="py-2 pr-2">{f.predicted_value !== null ? `${f.predicted_value}%` : '—'}</td>
                      <td className="py-2 pr-2">{f.slope_per_hour !== null ? `${f.slope_per_hour}%` : '—'}</td>
                      <td className="py-2">
                        <Badge variant={f.status === 'INSUFFICIENT_DATA' ? 'neutral' : f.predictive_warning ? 'danger' : 'success'}>
                          {f.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Health Trend */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
          <h3 className="text-xs font-mono uppercase text-slate-500 dark:text-slate-400 mb-3">24-Hour Overall Health Score (%)</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metrics}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="timestamp" stroke="#64748b" tick={false} />
                <YAxis domain={[0, 100]} stroke="#64748b" />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }} />
                <Line type="monotone" dataKey="overall_health" stroke="#10b981" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Latency & Packet Loss */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
          <h3 className="text-xs font-mono uppercase text-slate-500 dark:text-slate-400 mb-3">Average Hop Latency (ms)</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={metrics}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="timestamp" stroke="#64748b" tick={false} />
                <YAxis stroke="#64748b" />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }} />
                <Bar dataKey="avg_latency_ms" fill="#06b6d4" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};
