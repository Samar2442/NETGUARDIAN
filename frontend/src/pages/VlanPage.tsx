import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { VLAN, NetworkInterface, Device } from '../types';
import { Badge } from '../components/common/Badge';
import { Layers, Plus, Search, AlertCircle, CheckCircle } from 'lucide-react';

export const VlanPage: React.FC = () => {
  const [vlans, setVlans] = useState<VLAN[]>([]);
  const [interfaces, setInterfaces] = useState<NetworkInterface[]>([]);
  const [devices, setDevices] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      setLoading(true);
      const [v, ifaces, devs] = await Promise.all([
        api.getVlans(),
        api.getInterfaces(),
        api.getDevices(),
      ]);
      setVlans(v);
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

  // Analyze trunk health for each VLAN
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

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <Layers className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-white">VLAN Inventory & 802.1Q Trunk Audit</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Subnet mappings, SVI default gateways, and automated detection of pruned/missing trunk VLANs.
          </p>
        </div>
      </div>

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
                    <span className="text-slate-400">Subnet:</span>
                    <span>{v.subnet}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Default Gateway:</span>
                    <span className="text-cyan-400 font-bold">{v.gateway_ip}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Description:</span>
                    <span className="text-slate-300 truncate max-w-[180px]">{v.description || 'N/A'}</span>
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
    </div>
  );
};
