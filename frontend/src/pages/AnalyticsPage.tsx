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
import { LineChart as AnalyticsIcon, Clock, ShieldCheck, Zap, Activity } from 'lucide-react';

export const AnalyticsPage: React.FC = () => {
  const [health, setHealth] = useState<HealthOverview | null>(null);
  const [metrics, setMetrics] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([api.getHealthOverview(), api.getMetricsHistory(24)]).then(([h, m]) => {
      setHealth(h);
      setMetrics(m);
    });
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <AnalyticsIcon className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-white">Network Analytics & Reliability Trends</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Historical availability, Mean Time to Detect (MTTD), Mean Time to Recover (MTTR), and risk trends.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Mean Time to Detect (MTTD)"
          value="4.2 sec"
          subtitle="Correlation engine latency"
          icon={Clock}
          color="cyan"
        />
        <StatCard
          title="Mean Time to Recover (MTTR)"
          value="18.5 sec"
          subtitle="Controlled remediation"
          icon={Zap}
          color="emerald"
        />
        <StatCard
          title="Diagnostic Accuracy"
          value="96.2%"
          subtitle="Validated CCNA rule sets"
          icon={ShieldCheck}
          color="indigo"
        />
        <StatCard
          title="Infrastructure Uptime"
          value="99.94%"
          subtitle="Core Cisco topology"
          icon={Activity}
          color="emerald"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Health Trend */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <h3 className="text-xs font-mono uppercase text-slate-400 mb-3">24-Hour Overall Health Score (%)</h3>
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
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
          <h3 className="text-xs font-mono uppercase text-slate-400 mb-3">Average Hop Latency (ms)</h3>
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
