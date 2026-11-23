import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { Router, Server, Laptop, Layers, ShieldCheck, Activity } from 'lucide-react';

interface CiscoNodeData {
  id: string;
  hostname: string;
  ip: string;
  device_type: string;
  model: string;
  status: 'online' | 'degraded' | 'offline';
  cpu?: number;
  memory?: number;
  interfaces_count?: number;
}

export const CiscoNode = memo(({ data }: { data: CiscoNodeData }) => {
  const getIcon = () => {
    switch (data.device_type) {
      case 'router':
        return <Router className="w-5 h-5 text-cyan-400" />;
      case 'l3_switch':
      case 'l2_switch':
      case 'access_switch':
        return <Layers className="w-5 h-5 text-blue-400" />;
      case 'server':
        return <Server className="w-5 h-5 text-indigo-400" />;
      default:
        return <Laptop className="w-5 h-5 text-emerald-400" />;
    }
  };

  const getStatusBorder = () => {
    if (data.status === 'offline') return 'border-rose-500 shadow-rose-950/50';
    if (data.status === 'degraded') return 'border-amber-500 shadow-amber-950/50';
    return 'border-slate-700 hover:border-cyan-500';
  };

  const getStatusColor = () => {
    if (data.status === 'offline') return 'bg-rose-500';
    if (data.status === 'degraded') return 'bg-amber-500 animate-pulse';
    return 'bg-emerald-500';
  };

  return (
    <div
      className={`bg-slate-900/95 border-2 ${getStatusBorder()} rounded-lg p-3 min-w-[190px] shadow-lg transition-all`}
    >
      <Handle type="target" position={Position.Top} className="!bg-cyan-500 !w-2.5 !h-2.5" />
      
      <div className="flex items-center space-x-2.5">
        <div className="p-1.5 rounded bg-slate-950 border border-slate-800">
          {getIcon()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-bold font-mono text-slate-100 truncate">
            {data.hostname}
          </div>
          <div className="text-[10px] font-mono text-cyan-400 truncate">
            {data.ip}
          </div>
        </div>
        <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
      </div>

      <div className="mt-2.5 pt-2 border-t border-slate-800/80 grid grid-cols-2 gap-1 text-[10px] font-mono text-slate-400">
        <div>
          <span>CPU: </span>
          <span className="text-slate-200">{data.cpu || 12}%</span>
        </div>
        <div>
          <span>MEM: </span>
          <span className="text-slate-200">{data.memory || 35}%</span>
        </div>
      </div>

      <div className="mt-1 text-[9px] font-mono text-slate-400 truncate">
        {data.model}
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-cyan-500 !w-2.5 !h-2.5" />
    </div>
  );
});
