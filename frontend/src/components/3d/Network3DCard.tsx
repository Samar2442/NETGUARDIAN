import React, { lazy, Suspense, useState } from 'react';
import { useWebGL, useReducedMotion } from '../../hooks/use3D';
import type { Node3DData, Link3DData, VisualizationMode } from './CampusNetwork3D';
import { Box, Eye, EyeOff } from 'lucide-react';

const CampusNetwork3D = lazy(() =>
  import('./CampusNetwork3D').then((m) => ({ default: m.CampusNetwork3D }))
);

interface Network3DCardProps {
  title: string;
  subtitle?: string;
  nodes: Node3DData[];
  links?: Link3DData[];
  mode?: VisualizationMode;
  highlightIds?: string[];
  onSelectNode?: (node: Node3DData) => void;
  heightClass?: string;
  defaultExpanded?: boolean;
}

const Fallback2DSVG: React.FC<{ nodes: Node3DData[]; highlightIds?: string[] }> = ({ nodes, highlightIds = [] }) => {
  const hiSet = new Set(highlightIds);
  const sample = nodes.slice(0, 18);
  return (
    <div className="w-full h-full flex flex-col items-center justify-center p-4 bg-slate-950/60 rounded-lg">
      <svg viewBox="0 0 200 100" className="w-full h-full max-h-48">
        {sample.map((n, i) => {
          const x = 20 + (i % 6) * 32;
          const y = 20 + Math.floor(i / 6) * 30;
          const isHi = hiSet.has(n.id);
          const fill = isHi ? '#ef4444' : n.status === 'online' ? '#10b981' : n.status === 'degraded' ? '#f59e0b' : '#64748b';
          return (
            <g key={n.id}>
              <circle cx={x} cy={y} r={isHi ? 6 : 4.5} fill={fill} opacity={0.9} />
              <text x={x} y={y + 10} textAnchor="middle" fontSize="4.5" fill="#94a3b8">
                {n.hostname.slice(0, 10)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="text-[10px] font-mono text-slate-400 mt-1">
        2D Topology Fallback ({nodes.length} devices)
      </div>
    </div>
  );
};

export const Network3DCard: React.FC<Network3DCardProps> = ({
  title,
  subtitle,
  nodes,
  links = [],
  mode = 'health',
  highlightIds = [],
  onSelectNode,
  heightClass = 'h-72',
  defaultExpanded = true,
}) => {
  const webgl = useWebGL();
  const reducedMotion = useReducedMotion();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [force2D, setForce2D] = useState(false);

  const show3D = webgl && !reducedMotion && !force2D;

  return (
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden shadow-sm">
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded bg-cyan-50 dark:bg-cyan-950/60 text-cyan-600 dark:text-cyan-400 border border-cyan-200 dark:border-cyan-800/60">
            <Box className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800/60">
                {show3D ? '3D LIVE' : '2D VIEW'}
              </span>
            </div>
            {subtitle && <p className="text-xs text-slate-500 dark:text-slate-400">{subtitle}</p>}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {webgl && !reducedMotion && (
            <button
              onClick={() => setForce2D(!force2D)}
              className="px-2.5 py-1 rounded text-[11px] font-mono border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              {force2D ? 'Switch to 3D' : '2D Fallback'}
            </button>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 rounded border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors"
            title={expanded ? 'Collapse 3D view' : 'Expand 3D view'}
          >
            {expanded ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className={`relative w-full ${heightClass} bg-slate-950`}>
          {nodes.length === 0 ? (
            <div className="w-full h-full flex items-center justify-center text-xs font-mono text-slate-400">
              Loading network nodes…
            </div>
          ) : show3D ? (
            <Suspense
              fallback={
                <div className="w-full h-full flex items-center justify-center text-xs font-mono text-slate-400 animate-pulse">
                  Initializing 3D WebGL scene…
                </div>
              }
            >
              <CampusNetwork3D
                nodes={nodes}
                links={links}
                mode={mode}
                highlightIds={highlightIds}
                onSelectNode={onSelectNode}
              />
            </Suspense>
          ) : (
            <Fallback2DSVG nodes={nodes} highlightIds={highlightIds} />
          )}
        </div>
      )}
    </div>
  );
};
