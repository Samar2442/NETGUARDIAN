import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Device } from '../types';
import { Badge } from '../components/common/Badge';
import { Server, Search, RefreshCw, Cpu, Layers, HardDrive, Shield } from 'lucide-react';

export const DevicesPage: React.FC = () => {
  const [devices, setDevices] = useState<Device[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const loadDevices = async () => {
    try {
      setLoading(true);
      const data = await api.getDevices();
      setDevices(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDevices();
  }, []);

  const filtered = devices.filter(
    (d) =>
      d.hostname.toLowerCase().includes(search.toLowerCase()) ||
      d.management_ip.includes(search) ||
      d.device_type.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <Server className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-slate-900 dark:text-white">Device Inventory & Management</h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Registered Cisco routers, Catalyst L2/L3 switches, servers, and endpoint devices.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-500 dark:text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search hostname or IP..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono rounded pl-9 pr-3 py-2 text-slate-800 dark:text-slate-200 focus:outline-none focus:border-cyan-500 w-56"
            />
          </div>
          <button
            onClick={loadDevices}
            className="flex items-center space-x-1 px-3 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded text-xs font-mono border border-slate-300 dark:border-slate-700"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Device Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 dark:text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="p-3.5">Hostname</th>
                <th className="p-3.5">Management IP</th>
                <th className="p-3.5">Device Type</th>
                <th className="p-3.5">Model / OS</th>
                <th className="p-3.5">Status</th>
                <th className="p-3.5">CPU / MEM</th>
                <th className="p-3.5">Location</th>
                <th className="p-3.5">Interfaces</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filtered.map((d) => (
                <tr key={d.id} className="hover:bg-slate-850/50 transition-colors">
                  <td className="p-3.5 font-bold text-slate-900 dark:text-slate-100 flex items-center space-x-2">
                    <Server className="w-4 h-4 text-cyan-400" />
                    <span>{d.hostname}</span>
                  </td>
                  <td className="p-3.5 text-cyan-400 font-bold">{d.management_ip}</td>
                  <td className="p-3.5 uppercase text-slate-700 dark:text-slate-300">
                    <Badge variant="purple">{d.device_type.replace('_', ' ')}</Badge>
                  </td>
                  <td className="p-3.5 text-slate-500 dark:text-slate-400">
                    <div className="text-slate-800 dark:text-slate-200">{d.model}</div>
                    <div className="text-[10px] text-slate-500 dark:text-slate-400">{d.os_version}</div>
                  </td>
                  <td className="p-3.5">
                    <Badge variant={d.status === 'online' ? 'success' : d.status === 'degraded' ? 'warning' : 'danger'}>
                      {d.status.toUpperCase()}
                    </Badge>
                  </td>
                  <td className="p-3.5 text-slate-700 dark:text-slate-300">
                    <span className="text-slate-800 dark:text-slate-200">{d.cpu_percent}%</span> / <span className="text-slate-500 dark:text-slate-400">{d.memory_percent}%</span>
                  </td>
                  <td className="p-3.5 text-slate-500 dark:text-slate-400">{d.location}</td>
                  <td className="p-3.5 text-slate-700 dark:text-slate-300">
                    {d.interfaces?.length || 0} configured
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
