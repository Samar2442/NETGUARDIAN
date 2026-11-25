import React, { useEffect, useState, useMemo } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  applyNodeChanges,
  applyEdgeChanges,
  Node,
  Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { api } from '../services/api';
import { CiscoNode } from '../components/topology/CiscoNode';
import { Badge } from '../components/common/Badge';
import { Network, RefreshCw, Info, ShieldCheck, AlertTriangle } from 'lucide-react';

export const TopologyPage: React.FC = () => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [overview, setOverview] = useState<any | null>(null);
  const [validation, setValidation] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<any | null>(null);

  const nodeTypes = useMemo(() => ({ ciscoNode: CiscoNode }), []);

  const loadTopology = async () => {
    try {
      setLoading(true);
      const [data, ov, val] = await Promise.all([
        api.getTopology(false),
        api.getCampusOverview().catch(() => null),
        api.validateTopology().catch(() => null),
      ]);
      setNodes(data.nodes || []);
      setEdges(data.edges || []);
      if (ov) setOverview(ov);
      if (val) setValidation(val);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTopology();
  }, []);

  const onNodesChange = (changes: any) => setNodes((nds) => applyNodeChanges(changes, nds));
  const onEdgesChange = (changes: any) => setEdges((eds) => applyEdgeChanges(changes, eds));

  const onNodeClick = (_: any, node: Node) => {
    setSelectedNode(node.data);
  };

  const connectedLinks = useMemo(() => {
    if (!selectedNode) return [];
    return edges.filter((e) => e.source === selectedNode.id || e.target === selectedNode.id);
  }, [selectedNode, edges]);

  return (
    <div className="h-[calc(100vh-6.5rem)] flex flex-col space-y-3">
      {/* Topology Header Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900 border border-slate-800 rounded-lg px-5 py-3">
        <div className="flex items-center space-x-3">
          <Network className="w-5 h-5 text-cyan-400" />
          <div>
            <h1 className="text-base font-bold text-white">Campus 3-Tier Network Topology</h1>
            <p className="text-xs text-slate-400">
              Edge (Router/Firewall) → Core (SW-CORE-01) → Distribution → 6 Dept Access Switches → 6 APs & 250 Student Endpoints
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {validation && (
            <Badge variant={validation.valid ? 'success' : 'danger'}>
              {validation.valid
                ? `VALIDATED (${validation.summary?.devices_checked ?? 0} nodes)`
                : `${validation.summary?.critical_errors ?? 0} ERRORS`}
            </Badge>
          )}
          <div className="hidden xl:flex items-center space-x-2 text-xs font-mono text-slate-400 mr-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
            <span>Link Up</span>
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500 ml-2"></span>
            <span>802.1Q Trunk</span>
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 ml-2"></span>
            <span>Down</span>
          </div>

          <button
            onClick={loadTopology}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs font-mono border border-slate-700"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Campus Infrastructure Summary Strip */}
      {overview && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2 text-xs font-mono">
          <div className="bg-slate-900 border border-slate-800 rounded px-3 py-2">
            <span className="text-slate-400 block text-[10px]">TOTAL ASSETS</span>
            <span className="text-white font-bold">{overview.total_devices}</span>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded px-3 py-2">
            <span className="text-slate-400 block text-[10px]">EDGE / FW</span>
            <span className="text-cyan-400 font-bold">{overview.routers} RTR / {overview.firewalls} FW</span>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded px-3 py-2">
            <span className="text-slate-400 block text-[10px]">CORE / DIST</span>
            <span className="text-cyan-400 font-bold">{overview.core_switches} / {overview.distribution_switches}</span>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded px-3 py-2">
            <span className="text-slate-400 block text-[10px]">ACCESS SW</span>
            <span className="text-emerald-400 font-bold">{overview.access_switches}</span>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded px-3 py-2">
            <span className="text-slate-400 block text-[10px]">WIRELESS APs</span>
            <span className="text-indigo-400 font-bold">{overview.wireless_aps}</span>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded px-3 py-2">
            <span className="text-slate-400 block text-[10px]">SERVERS</span>
            <span className="text-amber-400 font-bold">{overview.servers}</span>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded px-3 py-2">
            <span className="text-slate-400 block text-[10px]">ENDPOINTS</span>
            <span className="text-white font-bold">{overview.student_endpoints}</span>
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded px-3 py-2">
            <span className="text-slate-400 block text-[10px]">HEALTHY / OFF</span>
            <span className="text-emerald-400 font-bold">{overview.online_devices} / {overview.offline_devices}</span>
          </div>
        </div>
      )}

      {/* Canvas Area */}
      <div className="flex-1 bg-slate-950 border border-slate-800 rounded-lg relative overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-full text-slate-400 font-mono text-xs">
            Loading Cisco campus topology model...
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            fitView
          >
            <Background color="#1e293b" gap={20} size={1} />
            <Controls className="!bg-slate-900 !border-slate-800 !text-slate-200" />
          </ReactFlow>
        )}

        {/* Selected Node Inspection Drawer */}
        {selectedNode && (
          <div className="absolute right-4 top-4 w-80 bg-slate-900/95 border border-slate-800 rounded-lg p-4 shadow-2xl backdrop-blur-md font-mono text-xs z-10 max-h-[85%] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
              <div className="flex items-center space-x-2">
                <Info className="w-4 h-4 text-cyan-400" />
                <span className="font-bold text-slate-100">{selectedNode.hostname}</span>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-slate-400 hover:text-slate-100 text-sm"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2 text-slate-300">
              <div className="flex justify-between">
                <span className="text-slate-400">Management IP:</span>
                <span className="text-cyan-400 font-bold">{selectedNode.ip}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Device Type:</span>
                <span className="uppercase">{selectedNode.device_type}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Department:</span>
                <span>{selectedNode.department || 'Campus Core'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">VLAN:</span>
                <span>{selectedNode.vlan_id ? `VLAN ${selectedNode.vlan_id}` : 'Trunk / Routed'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Model:</span>
                <span>{selectedNode.model}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Status:</span>
                <Badge variant={selectedNode.status === 'online' ? 'success' : 'warning'}>
                  {selectedNode.status}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">CPU / Memory:</span>
                <span>{selectedNode.cpu || 10}% / {selectedNode.memory || 28}%</span>
              </div>
            </div>

            {connectedLinks.length > 0 && (
              <div className="mt-3 pt-3 border-t border-slate-800">
                <span className="text-slate-400 block mb-1.5 font-bold">Connected Links ({connectedLinks.length}):</span>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {connectedLinks.map((lk) => (
                    <div key={lk.id} className="text-[10px] bg-slate-950 border border-slate-800 rounded px-2 py-1 flex justify-between">
                      <span className="truncate max-w-[175px]">{(lk.data as any)?.name || lk.label}</span>
                      <span className="text-emerald-400">{String((lk.data as any)?.status || 'up').toUpperCase()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
