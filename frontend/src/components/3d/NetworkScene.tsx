import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Line } from '@react-three/drei';
import * as THREE from 'three';

// Individual animated node
const NetworkNode: React.FC<{
  position: [number, number, number];
  color: string;
  scale?: number;
}> = ({ position, color, scale = 1 }) => {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = state.clock.elapsedTime * 0.5;
      meshRef.current.position.y = position[1] + Math.sin(state.clock.elapsedTime + position[0]) * 0.05;
    }
  });

  return (
    <mesh ref={meshRef} position={position} scale={scale}>
      <boxGeometry args={[0.3, 0.3, 0.3]} />
      <meshStandardMaterial color={color} metalness={0.6} roughness={0.3} emissive={color} emissiveIntensity={0.2} />
    </mesh>
  );
};

// Animated data packet along a link
const DataPacket: React.FC<{
  start: [number, number, number];
  end: [number, number, number];
  speed?: number;
  offset?: number;
}> = ({ start, end, speed = 1, offset = 0 }) => {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (meshRef.current) {
      const t = ((state.clock.elapsedTime * speed + offset) % 1 + 1) % 1;
      meshRef.current.position.set(
        start[0] + (end[0] - start[0]) * t,
        start[1] + (end[1] - start[1]) * t,
        start[2] + (end[2] - start[2]) * t,
      );
    }
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[0.04, 8, 8]} />
      <meshStandardMaterial color="#22d3ee" emissive="#22d3ee" emissiveIntensity={1} />
    </mesh>
  );
};

// Network link
const NetworkLink: React.FC<{
  start: [number, number, number];
  end: [number, number, number];
  color?: string;
}> = ({ start, end, color = '#1e40af' }) => {
  const points = useMemo(() => [
    new THREE.Vector3(...start),
    new THREE.Vector3(...end),
  ], [start, end]);

  return (
    <Line points={points} color={color} lineWidth={1} opacity={0.4} transparent />
  );
};

// Full hero network scene
const HeroScene: React.FC = () => {
  // Core network layout: hub + spokes + departments
  const coreNodes: Array<{ pos: [number, number, number]; color: string; scale: number }> = [
    { pos: [0, 0, 0], color: '#0ea5e9', scale: 1.4 },      // Core router
    { pos: [-2.5, 0.5, -1], color: '#6366f1', scale: 1.0 }, // Dept A switch
    { pos: [2.5, 0.5, -1], color: '#8b5cf6', scale: 1.0 },  // Dept B switch
    { pos: [0, 0.5, -2.5], color: '#06b6d4', scale: 1.0 },  // Dept C switch
    { pos: [-1.5, -0.8, 0.5], color: '#10b981', scale: 0.7 }, // AP
    { pos: [1.5, -0.8, 0.5], color: '#10b981', scale: 0.7 },  // AP
    { pos: [-3.5, 0, -0.5], color: '#f59e0b', scale: 0.6 },   // endpoint
    { pos: [-2, 1.5, -1.5], color: '#f59e0b', scale: 0.6 },   // endpoint
    { pos: [3.5, 0, -0.5], color: '#f59e0b', scale: 0.6 },    // endpoint
    { pos: [2, 1.5, -1.5], color: '#f59e0b', scale: 0.6 },    // endpoint
    { pos: [0, 0, -3.5], color: '#ef4444', scale: 0.6 },      // firewall
    { pos: [-0.8, -1.5, -1], color: '#f59e0b', scale: 0.5 },  // endpoint
    { pos: [0.8, -1.5, -1], color: '#f59e0b', scale: 0.5 },   // endpoint
  ];

  const links: Array<{ start: [number, number, number]; end: [number, number, number] }> = [
    { start: [0,0,0], end: [-2.5, 0.5, -1] },
    { start: [0,0,0], end: [2.5, 0.5, -1] },
    { start: [0,0,0], end: [0, 0.5, -2.5] },
    { start: [0,0,0], end: [-1.5, -0.8, 0.5] },
    { start: [0,0,0], end: [1.5, -0.8, 0.5] },
    { start: [-2.5, 0.5, -1], end: [-3.5, 0, -0.5] },
    { start: [-2.5, 0.5, -1], end: [-2, 1.5, -1.5] },
    { start: [2.5, 0.5, -1], end: [3.5, 0, -0.5] },
    { start: [2.5, 0.5, -1], end: [2, 1.5, -1.5] },
    { start: [0, 0.5, -2.5], end: [0, 0, -3.5] },
    { start: [0, 0.5, -2.5], end: [-0.8, -1.5, -1] },
    { start: [0, 0.5, -2.5], end: [0.8, -1.5, -1] },
  ];

  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[5, 5, 5]} intensity={1.5} color="#0ea5e9" />
      <pointLight position={[-5, -5, -5]} intensity={0.8} color="#6366f1" />
      <directionalLight position={[0, 10, 5]} intensity={0.6} />

      {coreNodes.map((node, i) => (
        <NetworkNode key={i} position={node.pos} color={node.color} scale={node.scale} />
      ))}

      {links.map((link, i) => (
        <React.Fragment key={i}>
          <NetworkLink start={link.start} end={link.end} color="#1e40af" />
          <DataPacket start={link.start} end={link.end} speed={0.3 + i * 0.05} offset={i * 0.1} />
        </React.Fragment>
      ))}

      <OrbitControls
        enablePan={false}
        enableZoom={false}
        autoRotate
        autoRotateSpeed={0.8}
        minPolarAngle={Math.PI / 4}
        maxPolarAngle={Math.PI / 1.8}
      />
    </>
  );
};

export const HeroNetworkScene: React.FC = () => {
  return (
    <Canvas
      camera={{ position: [0, 3, 7], fov: 60 }}
      style={{ width: '100%', height: '100%' }}
      gl={{ antialias: true, alpha: true }}
    >
      <HeroScene />
    </Canvas>
  );
};

// 2D Fallback when WebGL is unavailable
export const NetworkScene2DFallback: React.FC = () => {
  const nodes = [
    { x: 50, y: 50, label: 'Core', color: '#0ea5e9' },
    { x: 20, y: 30, label: 'Dept A', color: '#6366f1' },
    { x: 80, y: 30, label: 'Dept B', color: '#8b5cf6' },
    { x: 50, y: 20, label: 'Dept C', color: '#06b6d4' },
    { x: 15, y: 60, label: 'AP-1', color: '#10b981' },
    { x: 85, y: 60, label: 'AP-2', color: '#10b981' },
  ];

  const links = [
    [0,1],[0,2],[0,3],[0,4],[0,5]
  ];

  return (
    <svg viewBox="0 0 100 80" className="w-full h-full opacity-70">
      <defs>
        <filter id="glow">
          <feGaussianBlur stdDeviation="1" result="coloredBlur"/>
          <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      {links.map(([s, e], i) => (
        <line
          key={i}
          x1={nodes[s].x} y1={nodes[s].y}
          x2={nodes[e].x} y2={nodes[e].y}
          stroke="#1e3a5f" strokeWidth="0.5" opacity="0.7"
        />
      ))}
      {nodes.map((n, i) => (
        <g key={i}>
          <circle cx={n.x} cy={n.y} r="3" fill={n.color} filter="url(#glow)" />
          <text x={n.x} y={n.y + 6} textAnchor="middle" fontSize="3" fill="#94a3b8">{n.label}</text>
        </g>
      ))}
    </svg>
  );
};
