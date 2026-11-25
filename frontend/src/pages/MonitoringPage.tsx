import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Badge } from '../components/common/Badge';
import { StatCard } from '../components/common/StatCard';
import { Network3DCard } from '../components/3d/Network3DCard';
import { Activity, Play, Server, Cpu, Layers, Bell, Check } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

type Tab = 'overview' | 'devices' | 'interfaces' | 'vlans' | 'events';

export const MonitoringPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('overview');
  const [overview, setOverview] = useState<any | null>(null);
  const [healthHist, setHealthHist] = useState<any[]>([]);
  const [devices, setDevices] = useState<any[]>([]);
  const [selectedHistory, setSelectedHistory] = useState<any | null>(null);
  const [interfaces, setInterfaces] = useState<any[]>([]);
  const [vlans, setVlans] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [sevFilter, setSevFilter] = useState('');
  const [rangeMinutes, setRangeMinutes] = useState(60);
  const [polling, setPolling] = useState(false);
  const [sceneDevices, setSceneDevices] = useState<any[]>([]);
  const [sceneLinks, setSceneLinks] = useState<any[]>([]);

  const loadAll = async () => {
    try {
      const [ov, hh, devs, lks] = await Promise.all([
        api.getTelemetryOverview().catch(() => null),
        api.getTelemetryHealthHistory(24).catch(() => ({ history: [] })),
        api.getDevices().catch(() => []),
        api.getLinks().catch(() => []),
      ]);
      if (ov) setOverview(ov);
      setHealthHist(hh.history || []);
      setSceneDevices(devs || []);
      setSceneLinks(lks || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadAll();
    const id = setInterval(loadAll, 5000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (tab === 'devices') {
      api.getTelemetryDevices({ search: search || undefined, limit: 60 }).then(setDevices).catch(console.error);
    } else if (tab === 'interfaces') {
      api.getTelemetryInterfaces(60).then(setInterfaces).catch(console.error);
    } else if (tab === 'vlans') {
      api.getTelemetryVlans().then(setVlans).catch(console.error);
    } else if (tab === 'events') {
      api.getFilteredEvents({ severity: sevFilter || undefined, search: search || undefined, limit: 60 }).then(setEvents).catch(console.error);
    }
  }, [tab, search, sevFilter]);

  const handleManualCollect = async () => {
    try {
      setPolling(true);
      await api.collectTelemetryNow();
      await loadAll();
      if (tab === 'devices') api.getTelemetryDevices({ limit: 60 }).then(setDevices);
      if (tab === 'events') api.getFilteredEvents({ limit: 60 }).then(setEvents);
    } finally {
      setPolling(false);
    }
  };

  const handleInspectDevice = async (deviceId: string) => {
    const hist = await api.getDeviceTelemetryHistory(deviceId, rangeMinutes);
    setSelectedHistory(hist);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <Activity className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-slate-900 dark:text-white">NOC Live Telemetry & Event Monitoring</h1>
            <Badge variant="info">SOURCE: SIMULATION</Badge>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Time-varying simulated telemetry across campus devices, interfaces, and departmental VLANs.
            {overview?.timestamp ? ` Last update: ${new Date(overview.timestamp).toLocaleTimeString()}` : ''}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {([
            ['overview', 'Live Overview'],
            ['devices', 'Devices'],
            ['interfaces', 'Interfaces'],
            ['vlans', 'VLAN Health'],
            ['events', 'Events'],
          ] as [Tab, string][]).map(([k, label]) => (
            <button
              key={k}
              onClick={() => setTab(k)}
              className={`px-3 py-1.5 rounded text-xs font-mono border ${
                tab === k ? 'bg-cyan-600/20 border-cyan-600 text-cyan-300 font-bold' : 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400'
              }`}
            >
              {label}
            </button>
          ))}
          <button
            onClick={handleManualCollect}
            disabled={polling}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-mono font-semibold"
          >
            <Play className="w-3.5 h-3.5" />
            <span>{polling ? 'Collecting...' : 'Collect Cycle'}</span>
          </button>
        </div>
      </div>

      {tab === 'overview' && overview && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard title="Monitored Devices" value={`${overview.online_devices} / ${overview.total_devices}`} subtitle={`Degraded: ${overview.degraded_devices} | Offline: ${overview.offline_devices}`} icon={Server} color="cyan" />
            <StatCard title="Availability (SIM)" value={`${overview.availability_pct}%`} subtitle={`Avg CPU: ${overview.avg_cpu_pct}% | Mem: ${overview.avg_memory_pct}%`} icon={Activity} color="emerald" />
            <StatCard title="Avg Latency / Loss" value={`${overview.avg_latency_ms} ms`} subtitle={`Packet Loss: ${overview.avg_packet_loss_pct}%`} icon={Cpu} color="indigo" />
            <StatCard title="Active Incidents" value={overview.active_incidents} subtitle={`Critical Alerts: ${overview.critical_alerts} | Faults: ${overview.active_faults}`} icon={Bell} color={overview.active_incidents > 0 ? 'rose' : 'emerald'} />
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs font-mono uppercase text-slate-500 dark:text-slate-400">Network Health & Availability Trend (SIMULATION)</h2>
              <select
                value={rangeMinutes}
                onChange={(e) => setRangeMinutes(Number(e.target.value))}
                className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-2 py-1 text-xs font-mono text-slate-700 dark:text-slate-300"
              >
                <option value={15}>15 Minutes</option>
                <option value={60}>1 Hour</option>
                <option value={360}>6 Hours</option>
                <option value={1440}>24 Hours</option>
              </select>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={healthHist}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="timestamp" tickFormatter={(v) => new Date(v).toLocaleTimeString()} stroke="#64748b" fontSize={10} />
                  <YAxis stroke="#64748b" fontSize={10} domain={[0, 100]} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: 11 }} />
                  <Line type="monotone" dataKey="overall_health" stroke="#22d3ee" name="Health %" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="availability" stroke="#10b981" name="Availability %" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <Network3DCard
            title="3D Device Health & Load State"
            subtitle="Real-time simulated CPU/status visualization across campus tiers"
            nodes={sceneDevices}
            links={sceneLinks}
            mode="health"
            heightClass="h-64"
          />
        </div>
      )}

      {tab === 'devices' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
            <div className="p-3 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center">
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter by hostname..."
                className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-3 py-1.5 text-xs font-mono text-slate-800 dark:text-slate-200 w-64"
              />
              <span className="text-[11px] font-mono text-slate-500 dark:text-slate-400">Click row for telemetry history</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="px-3 py-2">Hostname</th>
                    <th className="px-3 py-2">Type</th>
                    <th className="px-3 py-2">CPU</th>
                    <th className="px-3 py-2">Mem</th>
                    <th className="px-3 py-2">Latency</th>
                    <th className="px-3 py-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800 text-slate-800 dark:text-slate-200">
                  {devices.map((d) => (
                    <tr key={d.device_id} onClick={() => handleInspectDevice(d.device_id)} className="hover:bg-slate-800/50 cursor-pointer">
                      <td className="px-3 py-2 font-bold text-cyan-400">{d.hostname}</td>
                      <td className="px-3 py-2">{d.device_type}</td>
                      <td className="px-3 py-2">{d.cpu_usage_pct}%</td>
                      <td className="px-3 py-2">{d.memory_usage_pct}%</td>
                      <td className="px-3 py-2">{d.latency_ms} ms</td>
                      <td className="px-3 py-2">
                        <Badge variant={d.status === 'online' ? 'success' : d.status === 'degraded' ? 'warning' : 'danger'}>{d.status}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 font-mono text-xs h-fit">
            <h3 className="text-slate-500 dark:text-slate-400 uppercase mb-3">Device History (SIMULATION)</h3>
            {!selectedHistory ? (
              <div className="text-slate-500">Select a device to inspect CPU and memory history.</div>
            ) : (
              <div>
                <div className="font-bold text-cyan-400 mb-2">{selectedHistory.hostname}</div>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={selectedHistory.points || []}>
                      <XAxis dataKey="timestamp" hide />
                      <YAxis domain={[0, 100]} fontSize={10} stroke="#64748b" />
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: 11 }} />
                      <Line type="monotone" dataKey="cpu_usage_pct" stroke="#22d3ee" name="CPU %" dot={false} />
                      <Line type="monotone" dataKey="memory_usage_pct" stroke="#a855f7" name="Mem %" dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'interfaces' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="px-3 py-2.5">Device</th>
                <th className="px-3 py-2.5">Interface</th>
                <th className="px-3 py-2.5">Status</th>
                <th className="px-3 py-2.5">Utilization</th>
                <th className="px-3 py-2.5">Errors (In/Out)</th>
                <th className="px-3 py-2.5">Discards (In/Out)</th>
                <th className="px-3 py-2.5">Duplex</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800 text-slate-800 dark:text-slate-200">
              {interfaces.map((i) => (
                <tr key={i.interface_id}>
                  <td className="px-3 py-2 font-bold text-cyan-400">{i.device_hostname}</td>
                  <td className="px-3 py-2">{i.name}</td>
                  <td className="px-3 py-2"><Badge variant={i.operational_status === 'up' ? 'success' : 'danger'}>{i.operational_status}</Badge></td>
                  <td className="px-3 py-2">{i.utilization_pct}%</td>
                  <td className="px-3 py-2">{i.input_errors} / {i.output_errors}</td>
                  <td className="px-3 py-2">{i.input_discards} / {i.output_discards}</td>
                  <td className="px-3 py-2">{i.duplex}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'vlans' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {vlans.map((v) => (
            <div key={v.vlan_id} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 font-mono text-xs space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-base font-bold text-cyan-400">VLAN {v.vlan_id} — {v.department}</span>
                <Badge variant={v.vlan_health_pct >= 95 ? 'success' : 'warning'}>{v.vlan_health_pct}%</Badge>
              </div>
              <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">Subnet:</span><span>{v.subnet}</span></div>
              <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">Endpoints (On/Off):</span><span>{v.online_endpoints} / {v.offline_endpoints} (Total {v.total_endpoints})</span></div>
              <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">Avg Latency:</span><span>{v.avg_latency_ms} ms</span></div>
              <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">Avg Packet Loss:</span><span>{v.avg_packet_loss_pct}%</span></div>
              <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">Active Incidents:</span><span className={v.active_incidents > 0 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>{v.active_incidents}</span></div>
            </div>
          ))}
        </div>
      )}

      {tab === 'events' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
          <div className="p-3 border-b border-slate-200 dark:border-slate-800 flex flex-wrap gap-2 items-center justify-between">
            <div className="flex gap-2">
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search events..." className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-3 py-1.5 text-xs font-mono text-slate-800 dark:text-slate-200" />
              <select value={sevFilter} onChange={(e) => setSevFilter(e.target.value)} className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-3 py-1.5 text-xs font-mono text-slate-800 dark:text-slate-200">
                <option value="">All Severities</option>
                <option value="CRITICAL">CRITICAL</option>
                <option value="MAJOR">MAJOR</option>
                <option value="WARNING">WARNING</option>
                <option value="INFO">INFO</option>
              </select>
            </div>
            <Badge variant="info">SIMULATION EVENTS: {events.length}</Badge>
          </div>
          <div className="divide-y divide-slate-200 dark:divide-slate-800 max-h-[500px] overflow-y-auto">
            {events.map((ev) => (
              <div key={ev.id} className="p-3 font-mono text-xs flex items-center justify-between">
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-slate-500 dark:text-slate-400 text-[10px]">{new Date(ev.timestamp).toLocaleTimeString()}</span>
                    <Badge variant={ev.severity === 'CRITICAL' || ev.severity === 'high' ? 'danger' : ev.severity === 'INFO' ? 'success' : 'warning'}>{ev.severity}</Badge>
                    <span className="font-bold text-slate-900 dark:text-slate-100">{ev.source_name}</span>
                  </div>
                  <div className="text-slate-700 dark:text-slate-300">{ev.message}</div>
                </div>
                {!ev.acknowledged && (
                  <button
                    onClick={() => api.acknowledgeEvent(ev.id).then(() => api.getFilteredEvents({ limit: 60 }).then(setEvents))}
                    className="px-2.5 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 rounded text-[10px] text-cyan-300 flex items-center space-x-1"
                  >
                    <Check className="w-3 h-3" /><span>Ack</span>
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
