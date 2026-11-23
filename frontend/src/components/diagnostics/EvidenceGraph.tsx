import React from 'react';
import { ArrowDown, AlertTriangle, CheckCircle2, ShieldAlert, Network, Layers } from 'lucide-react';

interface EvidenceGraphProps {
  evidenceGraph?: {
    nodes: Array<{ id: string; label: string; type: string; status?: string }>;
    edges: Array<{ source: string; target: string; label: string }>;
  };
  rootCause: string;
  confidence: number;
}

export const EvidenceGraph: React.FC<EvidenceGraphProps> = ({
  evidenceGraph,
  rootCause,
  confidence,
}) => {
  // If structured nodes exist, render sequential dependency graph
  const nodes = evidenceGraph?.nodes || [
    { id: 'client', label: 'PC-Student-01 (10.0.30.101)', type: 'endpoint', status: 'affected' },
    { id: 'vlan', label: 'VLAN 30 (Student-Lab)', type: 'vlan', status: 'affected' },
    { id: 'access_sw', label: 'HQ-Access-SW-02', type: 'switch', status: 'degraded' },
    { id: 'trunk', label: 'GigabitEthernet0/1 Trunk', type: 'interface', status: 'misconfigured' },
    { id: 'root_cause', label: 'VLAN 30 Missing from Trunk', type: 'root_cause', status: 'root_cause' },
    { id: 'gateway', label: 'Default Gateway (10.0.30.1)', type: 'gateway', status: 'unreachable' },
  ];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
        <div className="flex items-center space-x-2">
          <Network className="w-5 h-5 text-cyan-400" />
          <h3 className="text-sm font-semibold text-slate-100">Multi-Symptom Evidence Graph</h3>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-xs font-mono text-slate-400">Calculated Confidence:</span>
          <span className="text-sm font-bold font-mono text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded border border-emerald-800">
            {confidence}%
          </span>
        </div>
      </div>

      <div className="text-xs text-slate-400 mb-6">
        Correlation of client telemetry, 802.1Q trunk parameters, and upstream gateway reachability:
      </div>

      {/* Visual node flow chain */}
      <div className="flex flex-col items-center space-y-3 max-w-lg mx-auto py-2">
        {nodes.map((node, index) => {
          const isRoot = node.type === 'root_cause';
          const isAffected = node.status === 'affected' || node.status === 'unreachable';

          return (
            <React.Fragment key={node.id}>
              <div
                className={`w-full p-3.5 rounded-lg border flex items-center justify-between font-mono transition-all ${
                  isRoot
                    ? 'bg-rose-950/70 border-rose-600/80 text-rose-200 shadow-md shadow-rose-950'
                    : isAffected
                    ? 'bg-amber-950/40 border-amber-800/60 text-amber-200'
                    : 'bg-slate-950 border-slate-800 text-slate-300'
                }`}
              >
                <div className="flex items-center space-x-3">
                  {isRoot ? (
                    <ShieldAlert className="w-5 h-5 text-rose-400 flex-shrink-0 animate-bounce" />
                  ) : isAffected ? (
                    <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
                  ) : (
                    <Layers className="w-4 h-4 text-cyan-400 flex-shrink-0" />
                  )}
                  <div>
                    <div className="text-xs font-bold">{node.label}</div>
                    <div className="text-[10px] text-slate-400 uppercase tracking-wider">{node.type}</div>
                  </div>
                </div>
                <span
                  className={`text-[10px] px-2 py-0.5 rounded uppercase font-bold border ${
                    isRoot
                      ? 'bg-rose-900/60 text-rose-300 border-rose-700'
                      : isAffected
                      ? 'bg-amber-900/60 text-amber-300 border-amber-700'
                      : 'bg-slate-900 text-slate-400 border-slate-700'
                  }`}
                >
                  {node.status || 'OK'}
                </span>
              </div>

              {index < nodes.length - 1 && (
                <div className="flex flex-col items-center text-slate-600 my-0.5">
                  <ArrowDown className="w-4 h-4 text-cyan-500/70" />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};
