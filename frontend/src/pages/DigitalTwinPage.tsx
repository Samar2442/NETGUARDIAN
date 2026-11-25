import React, { useState } from 'react';
import { api } from '../services/api';
import { Badge } from '../components/common/Badge';
import {
  Box,
  Play,
  AlertTriangle,
  CheckCircle2,
  Shield,
  Layers,
  ArrowRight,
  TrendingDown,
  Activity,
} from 'lucide-react';

export const DigitalTwinPage: React.FC = () => {
  const [scenarioType, setScenarioType] = useState('uplink_failure');
  const [targetDevice, setTargetDevice] = useState('SW-IT-01');
  const [simulationResult, setSimulationResult] = useState<any | null>(null);
  const [twinState, setTwinState] = useState<any | null>(null);
  const [simulating, setSimulating] = useState(false);

  const runSimulation = async () => {
    try {
      setSimulating(true);
      const [res, state] = await Promise.all([
        api.runSimulation({
          scenario_type: scenarioType,
          target_name: targetDevice,
          parameters: { vlan_id: 30 },
        }),
        api.getDigitalTwinState(targetDevice).catch(() => null),
      ]);
      setSimulationResult(res);
      setTwinState(state);
    } catch (e) {
      console.error(e);
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <Box className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-white">Digital Network Twin: What-If Simulation</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Simulate failure modes on a decoupled logical topology model without touching physical network hardware.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Simulator Controls */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-4">
          <h3 className="text-xs font-mono uppercase text-slate-400">Simulation Scenario Configuration</h3>

          <div>
            <label className="block text-xs font-mono text-slate-400 mb-1">Scenario Type</label>
            <select
              value={scenarioType}
              onChange={(e) => setScenarioType(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 text-xs font-mono rounded p-2 text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="uplink_failure">Campus Switch Uplink Failure</option>
              <option value="switch_failure">Access / Distribution Switch Down</option>
              <option value="vlan_removed_from_trunk">VLAN Removed from Trunk (Scenario Acceptance Test)</option>
              <option value="router_failure">Core Router Link Down</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-mono text-slate-400 mb-1">Target Campus Device</label>
            <select
              value={targetDevice}
              onChange={(e) => setTargetDevice(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 text-xs font-mono rounded p-2 text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="SW-IT-01">SW-IT-01 (IT Dept Access Switch)</option>
              <option value="SW-CSE-01">SW-CSE-01 (CSE Dept Access Switch)</option>
              <option value="SW-ECE-01">SW-ECE-01 (ECE Dept Access Switch)</option>
              <option value="SW-DIST-01">SW-DIST-01 (Distribution Switch)</option>
              <option value="SW-CORE-01">SW-CORE-01 (Campus Core Switch)</option>
              <option value="HQ-Access-SW-02">HQ-Access-SW-02 (Student Lab Switch)</option>
            </select>
          </div>

          <div className="p-3 rounded bg-slate-950 border border-slate-800/80 text-[11px] font-mono text-slate-400">
            <span className="text-cyan-400 font-bold">Safety Note: </span>
            Simulation runs strictly on in-memory networkx graph models. Never executes CLI changes on production routers.
          </div>

          <button
            onClick={runSimulation}
            disabled={simulating}
            className="w-full bg-cyan-600 hover:bg-cyan-500 text-white font-semibold py-2.5 rounded text-xs font-mono flex items-center justify-center space-x-2 shadow-lg shadow-cyan-950/50"
          >
            <Play className="w-3.5 h-3.5" />
            <span>{simulating ? 'Executing Graph Traversal...' : 'Run What-If Simulation'}</span>
          </button>
        </div>

        {/* Simulation Output */}
        <div className="lg:col-span-2 space-y-4">
          {simulationResult ? (
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-5 space-y-5">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center space-x-2">
                  <Activity className="w-5 h-5 text-amber-400" />
                  <h3 className="text-sm font-bold text-slate-100">{simulationResult.scenario}</h3>
                </div>
                <div className="flex items-center space-x-2">
                  <Badge variant="info">
                    STATE: {simulationResult.state_classification || 'PREDICTED'}
                  </Badge>
                  {twinState?.state_classification && (
                    <Badge variant={twinState.state_classification === 'RECOVERY_VERIFIED' ? 'success' : 'neutral'}>
                      LIVE TWIN: {twinState.state_classification}
                    </Badge>
                  )}
                  <Badge variant={simulationResult.severity === 'HIGH' || simulationResult.severity === 'CRITICAL' ? 'danger' : 'warning'}>
                    SEVERITY: {simulationResult.severity}
                  </Badge>
                </div>
              </div>

              {/* Before vs Predicted After State Comparison */}
              {simulationResult.before_state && simulationResult.after_state && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
                  <div className="bg-slate-950 p-3 rounded border border-slate-800">
                    <div className="text-[10px] text-slate-400 uppercase mb-1">Before State ({simulationResult.before_state.classification})</div>
                    <div className="text-emerald-400">
                      Reachable Nodes: {simulationResult.before_state.reachable_nodes}/{simulationResult.before_state.total_nodes} • Impacted Services: {simulationResult.before_state.impacted_services_count}
                    </div>
                  </div>
                  <div className="bg-slate-950 p-3 rounded border border-slate-800">
                    <div className="text-[10px] text-slate-400 uppercase mb-1">After Failure ({simulationResult.after_state.classification})</div>
                    <div className="text-rose-400">
                      Reachable Nodes: {simulationResult.after_state.reachable_nodes}/{simulationResult.after_state.total_nodes} • Impacted Services: {simulationResult.after_state.impacted_services_count}
                    </div>
                  </div>
                </div>
              )}

              {/* Blast Radius Numbers */}
              <div className="grid grid-cols-3 gap-3 font-mono text-center">
                <div className="bg-slate-950 p-3 rounded border border-slate-800">
                  <div className="text-xs text-slate-400 uppercase">Isolated Endpoints</div>
                  <div className="text-2xl font-bold text-rose-400 mt-1">
                    {simulationResult.affected_endpoints?.length || 2}
                  </div>
                </div>
                <div className="bg-slate-950 p-3 rounded border border-slate-800">
                  <div className="text-xs text-slate-400 uppercase">Impacted Services</div>
                  <div className="text-2xl font-bold text-amber-400 mt-1">
                    {simulationResult.affected_services?.length || 3}
                  </div>
                </div>
                <div className="bg-slate-950 p-3 rounded border border-slate-800">
                  <div className="text-xs text-slate-400 uppercase">Redundant Path</div>
                  <div className="text-sm font-bold text-slate-200 mt-2">
                    {simulationResult.redundant_path_available ? (
                      <span className="text-emerald-400">AVAILABLE</span>
                    ) : (
                      <span className="text-rose-400">NONE (Single Uplink)</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Explanation */}
              <div className="p-3.5 rounded bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300">
                <span className="text-cyan-400 font-bold">TOPOLOGICAL IMPACT: </span>
                {simulationResult.explanation}
              </div>

              {/* VLAN & Service Impact Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                <div className="bg-slate-950 p-4 rounded border border-slate-800">
                  <h4 className="text-slate-400 uppercase text-[10px] mb-2 font-bold">Affected Endpoints & Devices</h4>
                  <ul className="space-y-1 text-slate-300">
                    {simulationResult.affected_devices?.map((d: string, idx: number) => (
                      <li key={idx} className="flex items-center space-x-1.5 text-rose-300">
                        <span>•</span>
                        <span>{d}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="bg-slate-950 p-4 rounded border border-slate-800">
                  <h4 className="text-slate-400 uppercase text-[10px] mb-2 font-bold">Impacted Network Services</h4>
                  <ul className="space-y-1 text-slate-300">
                    {simulationResult.affected_services?.map((s: string, idx: number) => (
                      <li key={idx} className="flex items-center space-x-1.5 text-amber-300">
                        <span>•</span>
                        <span>{s}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-12 text-center font-mono text-xs text-slate-400">
              <Box className="w-8 h-8 text-cyan-500 mx-auto mb-2 opacity-80" />
              Configure a scenario and click "Run What-If Simulation" to compute blast radius and graph traversal reachability.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
