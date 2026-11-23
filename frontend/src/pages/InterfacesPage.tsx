import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { NetworkInterface, Device } from '../types';
import { Badge } from '../components/common/Badge';
import { Cpu, Search, RefreshCw, Power } from 'lucide-react';

export const InterfacesPage: React.FC = () => {
  const [interfaces, setInterfaces] = useState<NetworkInterface[]>([]);
  const [devices, setDevices] = useState<Record<string, string>>({});
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      setLoading(true);
      const [ifaces, devs] = await Promise.all([api.getInterfaces(), api.getDevices()]);
      setInterfaces(ifaces);
      const devMap: Record<string, string> = {};
      devs.forEach((d: Device) => {
        devMap[d.id] = d.hostname;
      });
      setDevices(devMap);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleToggleStatus = async (iface: NetworkInterface) => {
    const nextStatus = iface.admin_status === 'up' ? 'down' : 'up';
    try {
      await api.toggleInterfaceAdmin(iface.id, nextStatus);
      await loadData();
    } catch (e) {
      console.error(e);
    }
  };

  const filtered = interfaces.filter(
    (i) =>
      i.name.toLowerCase().includes(search.toLowerCase()) ||
      (devices[i.device_id] || '').toLowerCase().includes(search.toLowerCase()) ||
      (i.allowed_vlans || '').includes(search)
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <Cpu className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-white">Interface Telemetry & Switchports</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Layer 2/3 switchport parameters, IEEE 802.1Q trunk allowed lists, error counters, and bandwidth.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <input
            type="text"
            placeholder="Search port or device..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-xs font-mono rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500 w-56"
          />
          <button
            onClick={loadData}
            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs font-mono border border-slate-700"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="p-3.5">Device</th>
                <th className="p-3.5">Interface</th>
                <th className="p-3.5">Admin / Oper</th>
                <th className="p-3.5">Mode</th>
                <th className="p-3.5">VLAN / Trunk Allowed</th>
                <th className="p-3.5">Speed / Duplex</th>
                <th className="p-3.5">Utilization</th>
                <th className="p-3.5">Control</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filtered.map((i) => (
                <tr key={i.id} className="hover:bg-slate-850/50">
                  <td className="p-3.5 font-bold text-slate-200">{devices[i.device_id] || 'Unknown'}</td>
                  <td className="p-3.5 text-cyan-400 font-bold">{i.name}</td>
                  <td className="p-3.5">
                    <span className="flex items-center space-x-1.5">
                      <Badge variant={i.admin_status === 'up' ? 'success' : 'danger'}>
                        {i.admin_status.toUpperCase()}
                      </Badge>
                      <span className="text-slate-400">/</span>
                      <Badge variant={i.oper_status === 'up' ? 'success' : 'danger'}>
                        {i.oper_status.toUpperCase()}
                      </Badge>
                    </span>
                  </td>
                  <td className="p-3.5 uppercase text-slate-300">
                    <Badge variant={i.mode === 'trunk' ? 'info' : 'purple'}>{i.mode}</Badge>
                  </td>
                  <td className="p-3.5 text-slate-300">
                    {i.mode === 'trunk' ? (
                      <div>
                        <span className="text-slate-400 text-[10px]">Allowed: </span>
                        <span className="text-amber-400 font-bold">{i.allowed_vlans || 'none'}</span>
                        <div className="text-[10px] text-slate-400">Native: {i.native_vlan}</div>
                      </div>
                    ) : (
                      <span>VLAN {i.access_vlan || 'routed'}</span>
                    )}
                  </td>
                  <td className="p-3.5 text-slate-400">
                    {i.speed_mbps} Mbps / {i.duplex}
                  </td>
                  <td className="p-3.5 text-slate-300">
                    <div className="flex items-center space-x-2">
                      <div className="w-16 bg-slate-950 rounded-full h-1.5">
                        <div
                          className="bg-cyan-500 h-1.5 rounded-full"
                          style={{ width: `${Math.min(100, i.bandwidth_utilization_pct || 15)}%` }}
                        ></div>
                      </div>
                      <span>{i.bandwidth_utilization_pct || 15}%</span>
                    </div>
                  </td>
                  <td className="p-3.5">
                    <button
                      onClick={() => handleToggleStatus(i)}
                      className={`p-1.5 rounded border transition-colors ${
                        i.admin_status === 'up'
                          ? 'border-rose-900 bg-rose-950/60 hover:bg-rose-900 text-rose-300'
                          : 'border-emerald-900 bg-emerald-950/60 hover:bg-emerald-900 text-emerald-300'
                      }`}
                      title={i.admin_status === 'up' ? 'Shutdown interface' : 'No shutdown interface'}
                    >
                      <Power className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
