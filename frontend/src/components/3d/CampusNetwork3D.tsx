import React, { useMemo, useRef, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Line } from '@react-three/drei';
import * as THREE from 'three';

export interface Node3DData {
  id: string;
  hostname: string;
  device_type?: string;
  status?: string;
  cpu_percent?: number;
  memory_percent?: number;
  location?: string;
  management_ip?: string;
  vlan?: number;
}

export interface Link3DData {
  id?: string;
  source_device_id: string;
  target_device_id: string;
  status?: string;
}

export type VisualizationMode = 'health' | 'vlan' | 'security' | 'incident' | 'remediation' | 'integration';

interface CampusNetwork3DProps {
  nodes: Node3DData[];
  links?: Link3DData[];
  mode?: VisualizationMode;
  highlightIds?: string[];
  onSelectNode?: (node: Node3DData) => void;
  autoRotate?: boolean;
}

function getNodeColor(node: Node3DData, mode: VisualizationMode, isHighlighted: boolean): string {
  if (isHighlighted) return '#ef4444'; // red highlight for incident/target/threat

  if (mode === 'health') {
    if (node.status === 'offline') return '#ef4444';
    if (node.status === 'degraded' || (node.cpu_percent && node.cpu_percent > 80)) return '#f59e0b';
    return '#10b981';
  }

  if (mode === 'vlan') {
    const loc = (node.location || '').toLowerCase();
    if (loc.includes('eng') || node.vlan === 10) return '#6366f1';
    if (loc.includes('sci') || node.vlan === 20) return '#10b981';
    if (loc.includes('art') || node.vlan === 30) return '#f59e0b';
    return '#06b6d4';
  }

  if (mode === 'security') {
    if (node.status === 'offline' || node.status === 'degraded') return '#f97316';
    return '#0ea5e9';
  }

  if (mode === 'incident' || mode === 'remediation') {
    if (node.status === 'offline') return '#ef4444';
    if (node.status === 'degraded') return '#f59e0b';
    return '#334155';
  }

  if (mode === 'integration') {
    if (node.device_type === 'router' || node.device_type === 'l3_switch') return '#06b6d4';
    if (node.status === 'online') return '#10b981';
    return '#64748b';
  }

  return '#0ea5e9';
}

const InteractiveNode: React.FC<{
  node: Node3DData;
  position: [number, number, number];
  color: string;
  isHighlighted: boolean;
  onHover: (node: Node3DData | null) => void;
  onSelect?: (node: Node3DData) => void;
}> = ({ node, position, color, isHighlighted, onHover, onSelect }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);

  const isCore = node.device_type === 'router' || node.device_type === 'l3_switch';
  const baseSize = isCore ? 0.34 : node.device_type === 'l2_switch' || node.device_type === 'access_switch' ? 0.24 : 0.16;

  useFrame((state) => {
    if (meshRef.current && isHighlighted) {
      const pulse = 1 + Math.sin(state.clock.elapsedTime * 4) * 0.15;
      meshRef.current.scale.setScalar(pulse);
    }
  });

  return (
    <mesh
      ref={meshRef}
      position={position}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
        onHover(node);
        document.body.style.cursor = 'pointer';
      }}
      onPointerOut={() => {
        setHovered(false);
        onHover(null);
        document.body.style.cursor = 'auto';
      }}
      onClick={(e) => {
        e.stopPropagation();
        onSelect?.(node);
      }}
    >
      {isCore ? (
        <octahedronGeometry args={[baseSize, 0]} />
      ) : (
        <boxGeometry args={[baseSize, baseSize, baseSize]} />
      )}
      <meshStandardMaterial
        color={hovered ? '#22d3ee' : color}
        emissive={hovered || isHighlighted ? color : '#000000'}
        emissiveIntensity={hovered ? 0.7 : isHighlighted ? 0.6 : 0.15}
        metalness={0.5}
        roughness={0.3}
      />
    </mesh>
  );
};

const SceneContent: React.FC<CampusNetwork3DProps & { onHover: (n: Node3DData | null) => void }> = ({
  nodes,
  links = [],
  mode = 'health',
  highlightIds = [],
  onSelectNode,
  onHover,
  autoRotate = true,
}) => {
  const highlightSet = useMemo(() => new Set(highlightIds), [highlightIds]);

  // Compute deterministic 3-tier 3D positions
  const { positionedNodes, posMap } = useMemo(() => {
    const capNodes = nodes.slice(0, 80); // keep 60fps smooth
    const core: Node3DData[] = [];
    const dist: Node3DData[] = [];
    const access: Node3DData[] = [];
    const other: Node3DData[] = [];

    capNodes.forEach((n) => {
      const t = (n.device_type || '').toLowerCase();
      if (t === 'router') core.push(n);
      else if (t === 'l3_switch') dist.push(n);
      else if (t === 'l2_switch' || t === 'access_switch') access.push(n);
      else other.push(n);
    });

    const map = new Map<string, [number, number, number]>();
    const out: Array<{ node: Node3DData; pos: [number, number, number] }> = [];

    const placeRing = (arr: Node3DData[], y: number, radius: number) => {
      arr.forEach((n, idx) => {
        const angle = (idx / Math.max(arr.length, 1)) * Math.PI * 2;
        const r = arr.length === 1 ? 0 : radius;
        const pos: [number, number, number] = [Math.cos(angle) * r, y, Math.sin(angle) * r];
        map.set(n.id, pos);
        out.push({ node: n, pos });
      });
    };

    placeRing(core, 2.2, 1.4);
    placeRing(dist, 0.7, 2.8);
    placeRing(access, -0.9, 4.2);
    placeRing(other, -2.3, 5.2);

    return { positionedNodes: out, posMap: map };
  }, [nodes]);

  const validLinks = useMemo(() => {
    const res: Array<{ start: [number, number, number]; end: [number, number, number]; status?: string }> = [];
    for (const l of links) {
      const start = posMap.get(l.source_device_id);
      const end = posMap.get(l.target_device_id);
      if (start && end) {
        res.push({ start, end, status: l.status });
        if (res.length >= 140) break;
      }
    }
    return res;
  }, [links, posMap]);

  return (
    <>
      <ambientLight intensity={0.55} />
      <pointLight position={[8, 8, 8]} intensity={1.2} color="#38bdf8" />
      <pointLight position={[-8, -6, -8]} intensity={0.6} color="#6366f1" />
      <directionalLight position={[0, 10, 4]} intensity={0.5} />

      {validLinks.map((l, idx) => (
        <Line
          key={idx}
          points={[new THREE.Vector3(...l.start), new THREE.Vector3(...l.end)]}
          color={l.status === 'down' ? '#ef4444' : l.status === 'degraded' ? '#f59e0b' : '#334155'}
          lineWidth={l.status === 'down' ? 1.5 : 1}
          transparent
          opacity={l.status === 'down' ? 0.8 : 0.35}
        />
      ))}

      {positionedNodes.map(({ node, pos }) => {
        const isHighlighted = highlightSet.has(node.id);
        const color = getNodeColor(node, mode, isHighlighted);
        return (
          <InteractiveNode
            key={node.id}
            node={node}
            position={pos}
            color={color}
            isHighlighted={isHighlighted}
            onHover={onHover}
            onSelect={onSelectNode}
          />
        );
      })}

      <OrbitControls
        enableDamping
        dampingFactor={0.08}
        autoRotate={autoRotate}
        autoRotateSpeed={0.5}
        minDistance={3}
        maxDistance={18}
      />
    </>
  );
};

export const CampusNetwork3D: React.FC<CampusNetwork3DProps> = (props) => {
  const [hoveredNode, setHoveredNode] = useState<Node3DData | null>(null);

  return (
    <div className="relative w-full h-full">
      <Canvas camera={{ position: [0, 4.5, 9.5], fov: 50 }} gl={{ antialias: true, alpha: true }}>
        <SceneContent {...props} onHover={setHoveredNode} />
      </Canvas>

      {hoveredNode && (
        <div className="absolute bottom-3 left-3 z-20 pointer-events-none bg-slate-900/95 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 shadow-xl">
          <div className="font-bold text-cyan-400">{hoveredNode.hostname}</div>
          <div className="text-[11px] text-slate-400">
            {hoveredNode.device_type || 'device'} · {hoveredNode.management_ip || 'N/A'}
          </div>
          <div className="text-[11px] mt-0.5 flex items-center gap-2">
            <span className={hoveredNode.status === 'online' ? 'text-emerald-400' : hoveredNode.status === 'degraded' ? 'text-amber-400' : 'text-red-400'}>
              ● {(hoveredNode.status || 'unknown').toUpperCase()}
            </span>
            {hoveredNode.cpu_percent !== undefined && (
              <span className="text-slate-300">CPU: {hoveredNode.cpu_percent}%</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
