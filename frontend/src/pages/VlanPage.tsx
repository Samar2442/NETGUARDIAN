import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { VLAN, NetworkInterface, Device } from '../types';
import { Badge } from '../components/common/Badge';
import { Layers } from 'lucide-react';

export const VlanPage: React.FC = () => {
  const [vlans, setVlans] = useState<VLAN[]>([]);
  const [deptOverview, setDeptOverview] = useState<any[]>([]);
  const [interfaces, setInterfaces] = useState<NetworkInterface[]>([]);
  const [devices, setDevices] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      setLoading(true);
      const [v, ifaces, devs, deptOv] = await Promise.all([
        api.getVlans(),
        api.getInterfaces(),
        api.getDevices(),
        api.getVlanDepartmentsOverview().catch(() => []),
      ]);
      setVlans(v);
      setInterfaces(ifaces);
      setDeptOverview(deptOv);
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

  const getTrunkHealth = (vlanId: number) => {
    const trunkIfaces = interfaces.filter((i) => i.mode === 'trunk');
    const missingOn = trunkIfaces.filter((i) => {
      const allowed = (i.allowed_vlans || '').split(',').map((x) => x.trim());
      return !allowed.includes(String(vlanId));
    });

    if (missingOn.length > 0) {
      return {
        status: 'PRUNED / MISCONFIGURED',
        variant: 'danger' as const,
        note: `Missing on: ${missingOn.map((i) => `${devices[i.device_id] || ''} ${i.name}`).join(', ')}`,
      };
    }
    return {
      status: 'PERMITTED ON ALL TRUNKS',
      variant: 'success' as const,
      note: 'All 802.1Q uplinks carrying tag',
    };
  };

  const getEndpointCount = (vlanId: number) => {
    const match = deptOverview.find((d) => d.vlan_id === vlanId);
    return match ? match.endpoint_count : 0;
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <Layers className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-white">Campus Departmental VLAN Management & 802.1Q Trunk Audit</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Three academic department VLANs (CSE, IT, ECE), SVI gateways, endpoint allocations, and trunk audit.
          </p>
        </div>
      </div>

      {/* Departmental VLAN Summary Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-800 text-xs font-mono uppercase text-slate-400">
          Academic Department VLAN Matrix
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="px-4 py-2.5">VLAN</th>
                <th className="px-4 py-2.5">Department</th>
                <th className="px-4 py-2.5">Subnet</th>
                <th className="px-4 py-2.5">Gateway</th>
                <th className="px-4 py-2.5 text-right">Endpoints</th>
                <th className="px-4 py-2.5 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-200">
              {vlans.map((v) => (
                <tr key={v.id} className="hover:bg-slate-800/40">
                  <td className="px-4 py-2.5 font-bold text-cyan-400">VLAN {v.vlan_id}</td>
                  <td className="px-4 py-2.5">{v.department || v.name}</td>
                  <td className="px-4 py-2.5">{v.subnet}</td>
                  <td className="px-4 py-2.5 text-cyan-300">{v.gateway_ip}</td>
                  <td className="px-4 py-2.5 text-right font-bold">{getEndpointCount(v.vlan_id)}</td>
                  <td className="px-4 py-2.5 text-right">
                    <Badge variant={v.status === 'active' ? 'success' : 'neutral'}>{v.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {loading ? (
        <div className="text-xs font-mono text-slate-400">Loading VLAN audit...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {vlans.map((v) => {
            const trunkAudit = getTrunkHealth(v.vlan_id);
            return (
              <div
                key={v.id}
                className={`bg-slate-900 border rounded-lg p-5 flex flex-col justify-between ${
                  trunkAudit.variant === 'danger' ? 'border-rose-800/80' : 'border-slate-800'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-2">
                      <span className="text-lg font-bold font-mono text-cyan-400">VLAN {v.vlan_id}</span>
                      <Badge variant="purple">{v.name}</Badge>
                    </div>
                    <Badge variant={v.status === 'active' ? 'success' : 'neutral'}>{v.status}</Badge>
                  </div>

                  <div className="space-y-2 text-xs font-mono text-slate-300">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Department:</span>
                      <span>{v.department || v.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Subnet:</span>
                      <span>{v.subnet}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Default Gateway:</span>
                      <span className="text-cyan-400 font-bold">{v.gateway_ip}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Assigned Endpoints:</span>
                      <span className="text-emerald-400 font-bold">{getEndpointCount(v.vlan_id)}</span>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800 text-[11px] font-mono">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-slate-400">Trunk Audit:</span>
                    <Badge variant={trunkAudit.variant}>{trunkAudit.status}</Badge>
                  </div>
                  <div className={`text-[10px] mt-1 ${trunkAudit.variant === 'danger' ? 'text-rose-400 font-bold' : 'text-slate-400'}`}>
                    {trunkAudit.note}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
