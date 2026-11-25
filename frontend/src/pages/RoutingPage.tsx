import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Route, Device } from '../types';
import { Badge } from '../components/common/Badge';
import { GitBranch, Search, RefreshCw, Network } from 'lucide-react';

export const RoutingPage: React.FC = () => {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [devices, setDevices] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      setLoading(true);
      const [rts, devs] = await Promise.all([api.getRoutes(), api.getDevices()]);
      setRoutes(rts);
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

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <GitBranch className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-slate-900 dark:text-white">IP Routing Tables & OSPF Adjacency</h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Global routing table analysis, static default routes (0.0.0.0/0), connected subnets, and dynamic OSPF paths.
          </p>
        </div>

        <button
          onClick={loadData}
          className="px-3 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded text-xs font-mono border border-slate-300 dark:border-slate-700"
        >
          Refresh Routes
        </button>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 dark:text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="p-3.5">Device Hostname</th>
                <th className="p-3.5">Destination Subnet</th>
                <th className="p-3.5">Netmask</th>
                <th className="p-3.5">Next-Hop Gateway</th>
                <th className="p-3.5">Egress Interface</th>
                <th className="p-3.5">Protocol</th>
                <th className="p-3.5">Metric</th>
                <th className="p-3.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {routes.map((r) => (
                <tr key={r.id} className="hover:bg-slate-850/50">
                  <td className="p-3.5 font-bold text-slate-800 dark:text-slate-200">{devices[r.device_id] || 'Unknown'}</td>
                  <td className="p-3.5 text-cyan-400 font-bold">{r.destination_network}</td>
                  <td className="p-3.5 text-slate-500 dark:text-slate-400">{r.netmask}</td>
                  <td className="p-3.5 text-slate-700 dark:text-slate-300">{r.next_hop || 'Directly Connected'}</td>
                  <td className="p-3.5 text-amber-400">{r.outgoing_interface || 'N/A'}</td>
                  <td className="p-3.5 uppercase">
                    <Badge variant={r.protocol === 'ospf' ? 'purple' : r.protocol === 'static' ? 'info' : 'neutral'}>
                      {r.protocol}
                    </Badge>
                  </td>
                  <td className="p-3.5 text-slate-500 dark:text-slate-400">{r.metric}</td>
                  <td className="p-3.5">
                    <Badge variant={r.is_active ? 'success' : 'danger'}>
                      {r.is_active ? 'ACTIVE' : 'INACTIVE'}
                    </Badge>
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
