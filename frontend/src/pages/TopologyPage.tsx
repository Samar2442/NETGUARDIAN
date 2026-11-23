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
import { Network, Server, Layers, Filter, RefreshCw, Info } from 'lucide-react';

export const TopologyPage: React.FC = () => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<any | null>(null);

  const nodeTypes = useMemo(() => ({ ciscoNode: CiscoNode }), []);

  const loadTopology = async () => {
    try {
      setLoading(true);
      const data = await api.getTopology();
      setNodes(data.nodes || []);
      setEdges(data.edges || []);
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

  return (
    <div className="h-[calc(100vh-6.5rem)] flex flex-col space-y-4">
      {/* Topology Header Controls */}
      <div className="flex items-center justify-between bg-slate-900 border border-slate-800 rounded-lg px-5 py-3">
        <div className="flex items-center space-x-3">
          <Network className="w-5 h-5 text-cyan-400" />
          <div>
            <h1 className="text-base font-bold text-white">Interactive Cisco Network Topology</h1>
            <p className="text-xs text-slate-400">3-Tier Enterprise Architecture: Core Router, L3 Core, Distribution, Access IDF & Servers</p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2 text-xs font-mono text-slate-400 mr-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
            <span>Online</span>
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 ml-2"></span>
            <span>Degraded</span>
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500 ml-2"></span>
            <span>Trunk Link</span>
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

      {/* Canvas Area */}
      <div className="flex-1 bg-slate-950 border border-slate-800 rounded-lg relative overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-full text-slate-400 font-mono text-xs">
            Loading Cisco topology model...
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
          <div className="absolute right-4 top-4 w-80 bg-slate-900/95 border border-slate-800 rounded-lg p-4 shadow-2xl backdrop-blur-md font-mono text-xs z-10">
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
                <span className="text-slate-400">Model:</span>
                <span>{selectedNode.model}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Operational Status:</span>
                <Badge variant={selectedNode.status === 'online' ? 'success' : 'warning'}>
                  {selectedNode.status}
                </Badge>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">CPU Utilization:</span>
                <span>{selectedNode.cpu || 14}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Memory Utilization:</span>
                <span>{selectedNode.memory || 38}%</span>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800 flex justify-end">
              <a
                href={`/devices`}
                className="text-cyan-400 hover:underline text-[11px]"
              >
                View Full Device Configuration →
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
