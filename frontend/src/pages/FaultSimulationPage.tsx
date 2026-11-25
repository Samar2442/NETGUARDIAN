import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Badge } from '../components/common/Badge';
import { useAppStore } from '../store/useAppStore';
import { Flame, RotateCcw, AlertTriangle, ShieldAlert } from 'lucide-react';

export const FaultSimulationPage: React.FC = () => {
  const { role } = useAppStore();
  const [scenarios, setScenarios] = useState<any[]>([]);
  const [devices, setDevices] = useState<any[]>([]);
  const [faults, setFaults] = useState<any[]>([]);
  const [selectedDevice, setSelectedDevice] = useState('SW-CORE-01');
  const [selectedType, setSelectedType] = useState('HIGH_CPU');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadData = async () => {
    try {
      const [sc, devs, flts] = await Promise.all([
        api.getSimulationScenarios(),
        api.getDevices(),
        api.getSimulationFaults(),
      ]);
      setScenarios(sc);
      setDevices(devs.filter((d: any) => d.asset_category !== 'student_endpoint'));
      setFaults(flts);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleInject = async () => {
    setError(null);
    setLoading(true);
    try {
      await api.injectSimulationFault({
        scenario_type: selectedType,
        target_device_id: selectedDevice,
        severity: 'HIGH',
      });
      await loadData();
    } catch (e: any) {
      setError(e?.message || 'Fault injection requires Admin role.');
    } finally {
      setLoading(false);
    }
  };

  const handleRecover = async (faultId: string) => {
    setError(null);
    setLoading(true);
    try {
      await api.recoverSimulationFault(faultId);
      await loadData();
    } catch (e: any) {
      setError(e?.message || 'Recovery failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-amber-950/40 border border-amber-700/70 rounded-lg px-5 py-3 flex items-center space-x-3 text-amber-300 font-mono text-xs font-bold">
        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
        <span>SIMULATION MODE — NO REAL NETWORK DEVICE IS MODIFIED</span>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div className="flex items-center space-x-3 mb-4">
          <Flame className="w-5 h-5 text-rose-400" />
          <h1 className="text-lg font-bold text-white">Controlled Fault Simulation Console</h1>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
          <div>
            <label className="text-slate-400 block mb-1">Target Campus Device</label>
            <select
              value={selectedDevice}
              onChange={(e) => setSelectedDevice(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200"
            >
              {devices.map((d) => (
                <option key={d.id} value={d.hostname}>{d.hostname} ({d.device_type})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-slate-400 block mb-1">Fault Scenario Type</label>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200"
            >
              {scenarios.map((s) => (
                <option key={s.type} value={s.type}>{s.type} — {s.description}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={handleInject}
              disabled={loading || role !== 'admin'}
              className="w-full py-2 bg-rose-700 hover:bg-rose-600 disabled:opacity-50 text-white rounded font-bold"
            >
              {role !== 'admin' ? 'Admin Role Required' : loading ? 'Simulating...' : 'Inject Simulated Fault'}
            </button>
          </div>
        </div>
        {error && <div className="mt-3 text-xs font-mono text-rose-400">{error}</div>}
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-800 text-xs font-mono uppercase text-slate-400">
          Simulated Fault Scenarios
        </div>
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
            <tr>
              <th className="px-4 py-2.5">Scenario</th>
              <th className="px-4 py-2.5">Type</th>
              <th className="px-4 py-2.5">Status</th>
              <th className="px-4 py-2.5">Started</th>
              <th className="px-4 py-2.5">Source</th>
              <th className="px-4 py-2.5 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 text-slate-200">
            {faults.map((f) => (
              <tr key={f.id}>
                <td className="px-4 py-2.5 font-bold">{f.scenario_name}</td>
                <td className="px-4 py-2.5">{f.scenario_type}</td>
                <td className="px-4 py-2.5">
                  <Badge variant={f.status === 'ACTIVE' ? 'danger' : 'success'}>{f.status}</Badge>
                </td>
                <td className="px-4 py-2.5">{f.started_at ? new Date(f.started_at).toLocaleTimeString() : '-'}</td>
                <td className="px-4 py-2.5"><Badge variant="info">{f.telemetry_source}</Badge></td>
                <td className="px-4 py-2.5 text-right">
                  {f.status === 'ACTIVE' && (
                    <button
                      onClick={() => handleRecover(f.id)}
                      disabled={loading || role !== 'admin'}
                      className="px-3 py-1 bg-emerald-700 hover:bg-emerald-600 text-white rounded text-[11px] inline-flex items-center space-x-1"
                    >
                      <RotateCcw className="w-3 h-3" /><span>Recover</span>
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
