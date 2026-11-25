import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { StatCard } from '../components/common/StatCard';
import { Badge } from '../components/common/Badge';
import { Plug, Server, Activity, Radio, RefreshCw, AlertCircle } from 'lucide-react';

export const NetworkIntegrationPage: React.FC = () => {
  const [profiles, setProfiles] = useState<any[]>([]);
  const [telemetryHealth, setTelemetryHealth] = useState<any | null>(null);
  const [syslogEvents, setSyslogEvents] = useState<any[]>([]);
  const [labServers, setLabServers] = useState<any[]>([]);
  const [devices, setDevices] = useState<any[]>([]);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const loadData = async () => {
    const [pr, th, sy, lb, dv] = await Promise.all([
      api.getIntegrationProfiles().catch(() => ({ items: [] })),
      api.getRealTelemetryHealth().catch(() => null),
      api.getSyslogEvents(20).catch(() => []),
      api.getLabServers().catch(() => []),
      api.getDevices().catch(() => []),
    ]);
    setProfiles(pr?.items || []);
    setTelemetryHealth(th);
    setSyslogEvents(sy || []);
    setLabServers(lb || []);
    setDevices(dv || []);
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleTest = async (id: string) => {
    const res = await api.testIntegrationProfile(id).catch((e) => ({ connected: false, detail: String(e) }));
    setStatusMsg(res.connected ? 'Connection verified (SSH host-key checked).' : `Connection error: ${res.detail}`);
    loadData();
  };

  const handleDiscoverLab = async (id: string) => {
    const res = await api.discoverLabServer(id).catch((e) => ({ error: String(e) }));
    setStatusMsg(res.error ? `Lab discovery error: ${res.error}` : 'Virtual lab discovery updated.');
    loadData();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <Plug className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-white">Device Connectivity, Real-Time Telemetry &amp; Virtual Labs</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Read-only Cisco SSH/SNMPv3 profiles, Syslog ingestion, and GNS3/EVE-NG virtual lab synchronization.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Badge variant="info">SIMULATION • LAB • PRODUCTION (DISABLED BY DEFAULT)</Badge>
        </div>
      </div>

      {statusMsg && (
        <div className="p-3 rounded bg-slate-900 border border-cyan-700/50 text-xs font-mono text-cyan-300 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{statusMsg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Connection Profiles"
          value={String(profiles.length)}
          subtitle={`Connected: ${telemetryHealth?.connected ?? 0} | Error: ${telemetryHealth?.error ?? 0}`}
          icon={Plug}
          color="cyan"
        />
        <StatCard
          title="Managed Devices"
          value={String(devices.length)}
          subtitle="Campus SIMULATION + LAB inventory"
          icon={Server}
          color="emerald"
        />
        <StatCard
          title="Virtual Lab Servers"
          value={String(labServers.length)}
          subtitle="GNS3 & EVE-NG connectors"
          icon={Activity}
          color="indigo"
        />
        <StatCard
          title="Stale Real Devices"
          value={String(telemetryHealth?.stale_devices?.length ?? 0)}
          subtitle="Telemetry freshness monitor"
          icon={Radio}
          color="amber"
        />
      </div>

      {/* Connection Profiles & Capabilities */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
        <h2 className="text-xs font-mono uppercase text-slate-300 font-bold">Device Connection Profiles &amp; Capabilities</h2>
        {profiles.length === 0 ? (
          <div className="text-xs font-mono text-slate-500 py-6 text-center">
            No external LAB/PRODUCTION profiles configured. Campus SIMULATION remains active independently.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono text-left">
              <thead className="text-[10px] text-slate-400 uppercase border-b border-slate-800">
                <tr>
                  <th className="py-2 pr-2">Device</th>
                  <th className="py-2 pr-2">IP</th>
                  <th className="py-2 pr-2">Env</th>
                  <th className="py-2 pr-2">Protocol</th>
                  <th className="py-2 pr-2">Status</th>
                  <th className="py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {profiles.map((p) => (
                  <tr key={p.id} className="text-slate-300">
                    <td className="py-2 pr-2 font-semibold">{p.device_name}</td>
                    <td className="py-2 pr-2">{p.management_ip}:{p.port}</td>
                    <td className="py-2 pr-2"><Badge variant="info">{p.environment}</Badge></td>
                    <td className="py-2 pr-2">{p.protocol}</td>
                    <td className="py-2 pr-2">
                      <Badge variant={p.connection_status === 'CONNECTED' ? 'success' : p.connection_status === 'ERROR' ? 'danger' : 'neutral'}>
                        {p.connection_status}
                      </Badge>
                    </td>
                    <td className="py-2 flex gap-2">
                      <button onClick={() => handleTest(p.id)} className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200">
                        Test
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Virtual Lab Servers & Syslog Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
          <h3 className="text-xs font-mono uppercase text-slate-300 font-bold">GNS3 &amp; EVE-NG Virtual Lab Servers</h3>
          {labServers.length === 0 ? (
            <div className="text-xs font-mono text-slate-500 py-6 text-center">No GNS3 or EVE-NG servers registered.</div>
          ) : (
            <div className="space-y-2 text-xs font-mono">
              {labServers.map((s) => (
                <div key={s.id} className="p-3 rounded bg-slate-950 border border-slate-800 flex items-center justify-between">
                  <div>
                    <div className="font-bold text-slate-200">{s.name} ({s.lab_type})</div>
                    <div className="text-slate-400">{s.base_url} • Status: {s.connection_status}</div>
                    {s.last_error && <div className="text-rose-400 text-[11px]">{s.last_error}</div>}
                  </div>
                  <button
                    onClick={() => handleDiscoverLab(s.id)}
                    className="px-2.5 py-1 rounded bg-cyan-600 hover:bg-cyan-500 text-white flex items-center gap-1"
                  >
                    <RefreshCw className="w-3 h-3" />
                    <span>Discover</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-3">
          <h3 className="text-xs font-mono uppercase text-slate-300 font-bold">Syslog &amp; Device Event Feed</h3>
          <div className="space-y-1.5 max-h-60 overflow-y-auto text-xs font-mono">
            {syslogEvents.length === 0 ? (
              <div className="text-slate-500 text-center py-6">No syslog events ingested.</div>
            ) : (
              syslogEvents.map((e) => (
                <div key={e.id} className="p-2 rounded bg-slate-950 border border-slate-800 flex justify-between gap-2">
                  <span className="text-slate-300 truncate">{e.source_name}: {e.message}</span>
                  <Badge variant="neutral">{e.source}</Badge>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
