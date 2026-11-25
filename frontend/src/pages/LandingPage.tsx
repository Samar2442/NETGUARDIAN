import React, { lazy, Suspense } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAppStore } from '../store/useAppStore';
import { useWebGL, useReducedMotion } from '../hooks/use3D';
import { clsx } from 'clsx';
import {
  Shield,
  ShieldAlert,
  Network,
  Activity,
  Zap,
  Eye,
  Search,
  GitBranch,
  Server,
  Layers,
  BarChart3,
  Lock,
  Bell,
  ArrowRight,
  ChevronRight,
  Users,
  Globe,
  Wifi,
  CheckCircle,
  AlertTriangle,
  TrendingUp,
  Database,
  Cpu,
  Radio,
  Box,
} from 'lucide-react';
// Lazy-load only the heavy 3D scene
const HeroNetworkScene = lazy(() =>
  import('../components/3d/NetworkScene').then(m => ({ default: m.HeroNetworkScene }))
);

// Inline 2D fallback (no lazy needed — it's just SVG)
const Network2DFallback: React.FC = () => {
  const nodes = [
    { x: 50, y: 50, label: 'Core', color: '#0ea5e9' },
    { x: 20, y: 30, label: 'Dept A', color: '#6366f1' },
    { x: 80, y: 30, label: 'Dept B', color: '#8b5cf6' },
    { x: 50, y: 20, label: 'Dept C', color: '#06b6d4' },
    { x: 15, y: 60, label: 'AP-1', color: '#10b981' },
    { x: 85, y: 60, label: 'AP-2', color: '#10b981' },
  ];
  const links = [[0,1],[0,2],[0,3],[0,4],[0,5]];
  return (
    <svg viewBox="0 0 100 80" className="w-full h-full opacity-70">
      <defs>
        <filter id="glow2d">
          <feGaussianBlur stdDeviation="1" result="coloredBlur"/>
          <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
      </defs>
      {links.map(([s, e], i) => (
        <line key={i} x1={nodes[s].x} y1={nodes[s].y} x2={nodes[e].x} y2={nodes[e].y} stroke="#1e3a5f" strokeWidth="0.5" opacity="0.7" />
      ))}
      {nodes.map((n, i) => (
        <g key={i}>
          <circle cx={n.x} cy={n.y} r="3" fill={n.color} filter="url(#glow2d)" />
          <text x={n.x} y={n.y + 6} textAnchor="middle" fontSize="3" fill="#94a3b8">{n.label}</text>
        </g>
      ))}
    </svg>
  );
};

// ---- Section: Nav ----
const LandingNav: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAppStore();

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-16 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200/60 dark:border-slate-800/60">
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-cyan-700 flex items-center justify-center font-mono font-bold text-white text-sm shadow-lg shadow-cyan-900/40">
            NG
          </div>
          <div>
            <span className="font-bold text-base tracking-tight text-slate-900 dark:text-white">NETGUARDIAN</span>
            <span className="ml-2 text-[9px] font-mono px-1.5 py-0.5 rounded bg-cyan-100 dark:bg-cyan-950 text-cyan-600 dark:text-cyan-400 border border-cyan-200 dark:border-cyan-800 uppercase">SaturnX Academy</span>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-6 text-sm text-slate-600 dark:text-slate-400">
          <a href="#capabilities" className="hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors">Capabilities</a>
          <a href="#architecture" className="hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors">Architecture</a>
          <a href="#security" className="hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors">Security</a>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono px-2 py-1 rounded border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 uppercase">
            ⬡ Simulation
          </span>
          {isAuthenticated ? (
            <button
              onClick={() => navigate('/')}
              className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-semibold rounded-lg transition-all shadow-md shadow-cyan-900/30"
            >
              Go to NOC →
            </button>
          ) : (
            <Link
              to="/login"
              className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-semibold rounded-lg transition-all shadow-md shadow-cyan-900/30"
            >
              Sign In
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
};

// ---- Section: Hero ----
const HeroSection: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAppStore();
  const webGLSupported = useWebGL();
  const reducedMotion = useReducedMotion();

  return (
    <section className="relative min-h-screen pt-16 overflow-hidden bg-white dark:bg-slate-950">
      {/* Background grid */}
      <div className="absolute inset-0 grid-pattern opacity-60" />

      {/* Radial gradient glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[800px] rounded-full bg-gradient-radial from-cyan-500/10 via-blue-500/5 to-transparent pointer-events-none" />

      <div className="relative max-w-7xl mx-auto px-6 pt-20 pb-16">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Left: Text */}
          <div>
            <div className="inline-flex items-center gap-2 mb-6 px-3 py-1.5 rounded-full border border-cyan-200 dark:border-cyan-800/60 bg-cyan-50 dark:bg-cyan-950/40 text-cyan-700 dark:text-cyan-400 text-xs font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              SIMULATION ENVIRONMENT · SaturnX Academy University
            </div>

            <h1 className="text-4xl md:text-5xl font-extrabold text-slate-900 dark:text-white leading-tight mb-4">
              Enterprise Network{' '}
              <span className="bg-gradient-to-r from-cyan-500 to-blue-600 bg-clip-text text-transparent">
                Operations &amp; Security
              </span>{' '}
              Platform
            </h1>

            <p className="text-lg text-slate-600 dark:text-slate-400 mb-8 leading-relaxed">
              A university campus network operations center for the SaturnX Academy simulation environment. Monitor 274 devices across 3 academic departments, detect threats, correlate incidents, run root-cause analysis and execute approval-gated remediation — all in a realistic CCNA training lab.
            </p>

            <div className="flex flex-wrap gap-4 mb-10">
              {isAuthenticated ? (
                <button
                  onClick={() => navigate('/')}
                  className="flex items-center gap-2 px-6 py-3 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-cyan-900/30 hover:shadow-cyan-900/50"
                >
                  Open NOC Dashboard
                  <ArrowRight className="w-4 h-4" />
                </button>
              ) : (
                <>
                  <Link
                    to="/login"
                    className="flex items-center gap-2 px-6 py-3 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-cyan-900/30"
                  >
                    Access Platform
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                  <a
                    href="#capabilities"
                    className="flex items-center gap-2 px-6 py-3 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 font-semibold rounded-xl transition-all"
                  >
                    View Capabilities
                    <ChevronRight className="w-4 h-4" />
                  </a>
                </>
              )}
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: 'Simulated Devices', value: '274', icon: <Server className="w-4 h-4" /> },
                { label: 'Campus Students', value: '250', icon: <Users className="w-4 h-4" /> },
                { label: 'Academic VLANs', value: '3', icon: <Layers className="w-4 h-4" /> },
              ].map(stat => (
                <div key={stat.label} className="bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 text-center">
                  <div className="text-cyan-600 dark:text-cyan-400 flex justify-center mb-1">{stat.icon}</div>
                  <div className="text-2xl font-bold font-mono text-slate-900 dark:text-white">{stat.value}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Right: 3D Scene */}
          <div className="relative h-[460px] rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-950/60 shadow-2xl shadow-cyan-900/10">
            {/* Scene label */}
            <div className="absolute top-3 left-3 z-10 flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-black/40 backdrop-blur-sm border border-white/10 text-xs font-mono text-cyan-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              SaturnX Campus Topology · SIMULATION
            </div>
            <div className="absolute bottom-3 right-3 z-10 text-[9px] font-mono text-slate-500">
              {webGLSupported ? '3D · WebGL' : '2D · Fallback'}
            </div>

            {webGLSupported && !reducedMotion ? (
              <Suspense fallback={
                <div className="w-full h-full flex items-center justify-center">
                  <div className="text-xs font-mono text-slate-500 animate-pulse">Loading 3D scene…</div>
                </div>
              }>
                <HeroNetworkScene />
              </Suspense>
            ) : (
              <div className="w-full h-full p-8">
                <Network2DFallback />
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};

// ---- Section: Capabilities ----
const capabilities = [
  { icon: <Activity className="w-5 h-5" />, title: 'Real-Time Telemetry', description: 'Simulated CPU, memory, bandwidth and packet-loss metrics for every campus device, refreshed every 5 seconds.', category: 'NOC' },
  { icon: <Bell className="w-5 h-5" />, title: 'Incident Management', description: 'Full incident lifecycle — detection, acknowledgment, escalation and resolution with priority-based queuing.', category: 'NOC' },
  { icon: <Search className="w-5 h-5" />, title: 'Root-Cause Analysis', description: 'Automated RCA engine correlates telemetry anomalies, event streams and topology data to pinpoint failure origin.', category: 'Intelligence' },
  { icon: <Box className="w-5 h-5" />, title: 'Digital Twin', description: 'Live simulation of campus topology for change modeling, what-if analysis and pre-deployment validation.', category: 'Intelligence' },
  { icon: <GitBranch className="w-5 h-5" />, title: 'Blast-Radius Analysis', description: 'Visualize the cascade impact of a device failure across VLANs, services and dependent endpoints.', category: 'Intelligence' },
  { icon: <Zap className="w-5 h-5" />, title: 'Fault Injection', description: 'Engineer controlled failures — interface down, CPU spike, packet loss — to test resilience and runbooks.', category: 'NOC' },
  { icon: <Shield className="w-5 h-5" />, title: 'Security Operations', description: 'Security event monitoring, threat detection, compliance checking and evidence management in one pane.', category: 'Security' },
  { icon: <Lock className="w-5 h-5" />, title: 'Config Compliance', description: 'Drift detection against golden baseline, structured remediation with approval gates and full rollback.', category: 'Security' },
  { icon: <Network className="w-5 h-5" />, title: 'Campus Topology', description: '3-tier hierarchical network — core, distribution and access — across Engineering, Science and Arts.', category: 'Network' },
  { icon: <Layers className="w-5 h-5" />, title: 'VLAN Management', description: 'Three academic VLANs with inter-VLAN routing, ACL policy visibility and end-to-end path tracing.', category: 'Network' },
  { icon: <Users className="w-5 h-5" />, title: 'Campus Inventory', description: '250 synthetic student identities with device-to-user assignment, faculty and IT staff directory.', category: 'Network' },
  { icon: <BarChart3 className="w-5 h-5" />, title: 'Predictive Analytics', description: 'Trend analysis and anomaly scoring to surface performance degradation before incidents occur.', category: 'Intelligence' },
];

const categoryColors: Record<string, string> = {
  NOC: 'bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-800/60',
  Intelligence: 'bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400 border-purple-200 dark:border-purple-800/60',
  Security: 'bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 border-red-200 dark:border-red-800/60',
  Network: 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/60',
};

const CapabilitiesSection: React.FC = () => (
  <section id="capabilities" className="py-24 bg-slate-50 dark:bg-slate-900">
    <div className="max-w-7xl mx-auto px-6">
      <div className="text-center mb-14">
        <div className="text-xs font-mono uppercase tracking-widest text-cyan-600 dark:text-cyan-500 mb-3">Platform Capabilities</div>
        <h2 className="text-3xl font-extrabold text-slate-900 dark:text-white mb-4">
          Everything a Network Operations Center Needs
        </h2>
        <p className="text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
          NETGUARDIAN replicates the tooling of an enterprise NOC in the SaturnX Academy simulation environment.
          All functionality is clearly labeled as SIMULATION.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {capabilities.map((cap) => (
          <div
            key={cap.title}
            className="bg-white dark:bg-slate-800/60 rounded-xl border border-slate-200 dark:border-slate-700/60 p-5 hover:border-cyan-300 dark:hover:border-cyan-700/60 hover:shadow-md hover:shadow-cyan-500/5 transition-all group"
          >
            <div className="flex items-start justify-between mb-3">
              <div className="p-2 rounded-lg bg-cyan-50 dark:bg-cyan-950/40 text-cyan-600 dark:text-cyan-400 group-hover:bg-cyan-100 dark:group-hover:bg-cyan-950/60 transition-colors">
                {cap.icon}
              </div>
              <span className={clsx('text-[9px] font-mono font-semibold px-1.5 py-0.5 rounded border uppercase', categoryColors[cap.category])}>
                {cap.category}
              </span>
            </div>
            <h3 className="font-semibold text-sm text-slate-900 dark:text-white mb-1.5">{cap.title}</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">{cap.description}</p>
          </div>
        ))}
      </div>
    </div>
  </section>
);

// ---- Section: Workflow ----
const workflowSteps = [
  { step: '01', title: 'Telemetry Collection', description: 'Simulated device metrics stream from 274 campus devices every 5 seconds.', icon: <Radio className="w-5 h-5" /> },
  { step: '02', title: 'Event Correlation', description: 'Anomalies trigger correlated events grouped by device, VLAN and service impact.', icon: <Activity className="w-5 h-5" /> },
  { step: '03', title: 'Incident Generation', description: 'Correlated events auto-create prioritized incidents with severity classification.', icon: <Bell className="w-5 h-5" /> },
  { step: '04', title: 'Root-Cause Analysis', description: 'RCA engine traces the causal chain from symptom to root failure point.', icon: <Search className="w-5 h-5" /> },
  { step: '05', title: 'Blast-Radius Assessment', description: 'Digital Twin models downstream impact before any change is applied.', icon: <GitBranch className="w-5 h-5" /> },
  { step: '06', title: 'Remediation Planning', description: 'Structured remediation steps are drafted with rollback plans attached.', icon: <Zap className="w-5 h-5" /> },
  { step: '07', title: 'Approval Gate', description: 'Network engineers review and approve changes before execution.', icon: <CheckCircle className="w-5 h-5" /> },
  { step: '08', title: 'Audit & Evidence', description: 'Every action is logged with timestamps, actors and before/after state.', icon: <Database className="w-5 h-5" /> },
];

const WorkflowSection: React.FC = () => (
  <section className="py-24 bg-white dark:bg-slate-950">
    <div className="max-w-7xl mx-auto px-6">
      <div className="text-center mb-14">
        <div className="text-xs font-mono uppercase tracking-widest text-cyan-600 dark:text-cyan-500 mb-3">NOC Workflow</div>
        <h2 className="text-3xl font-extrabold text-slate-900 dark:text-white mb-4">
          From Alert to Resolution
        </h2>
        <p className="text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
          An 8-stage operational pipeline that mirrors enterprise NOC procedures — from raw telemetry to audited remediation.
        </p>
      </div>

      <div className="relative">
        {/* Connector line */}
        <div className="absolute left-8 top-6 bottom-6 w-px bg-gradient-to-b from-cyan-500/40 via-blue-500/40 to-transparent hidden md:block" />

        <div className="space-y-4">
          {workflowSteps.map((step, i) => (
            <div key={step.step} className="flex items-start gap-6">
              <div className="relative flex-shrink-0 w-16 flex flex-col items-center">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-600/20 border border-cyan-500/30 dark:border-cyan-700/50 flex items-center justify-center text-cyan-600 dark:text-cyan-400 relative z-10 bg-white dark:bg-slate-950">
                  {step.icon}
                </div>
              </div>
              <div className="flex-1 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 hover:border-cyan-300 dark:hover:border-cyan-800 transition-colors">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-[10px] font-mono text-cyan-600 dark:text-cyan-500 font-semibold mb-0.5">STEP {step.step}</div>
                    <h3 className="font-semibold text-sm text-slate-900 dark:text-white">{step.title}</h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{step.description}</p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  </section>
);

// ---- Section: Architecture ----
const ArchitectureSection: React.FC = () => (
  <section id="architecture" className="py-24 bg-slate-50 dark:bg-slate-900">
    <div className="max-w-7xl mx-auto px-6">
      <div className="text-center mb-14">
        <div className="text-xs font-mono uppercase tracking-widest text-cyan-600 dark:text-cyan-500 mb-3">System Architecture</div>
        <h2 className="text-3xl font-extrabold text-slate-900 dark:text-white mb-4">
          Campus Network Architecture
        </h2>
        <p className="text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
          3-tier hierarchical Cisco campus design with three academic departments and their associated VLANs.
          All devices are simulated within the SaturnX Academy lab environment.
        </p>
      </div>

      <div className="relative bg-white dark:bg-slate-800/40 rounded-2xl border border-slate-200 dark:border-slate-700/60 p-8 overflow-hidden">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Tier 1: Core */}
          <div className="md:col-span-3 mb-4">
            <div className="text-center mb-3 text-xs font-mono uppercase tracking-widest text-slate-500 dark:text-slate-400">Tier 1 — Core Layer</div>
            <div className="flex justify-center gap-6">
              {['Core Router 01', 'Core Router 02', 'Campus Firewall'].map(device => (
                <div key={device} className="text-center">
                  <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 mx-auto flex items-center justify-center mb-1.5 shadow-lg shadow-cyan-900/20">
                    <Server className="w-6 h-6 text-white" />
                  </div>
                  <div className="text-xs font-mono text-slate-700 dark:text-slate-300">{device}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Tier 2: Distribution */}
          {[
            { label: 'Engineering Dept', color: 'from-indigo-500 to-purple-600', vlan: 'VLAN 10', devices: 2 },
            { label: 'Science Dept', color: 'from-emerald-500 to-teal-600', vlan: 'VLAN 20', devices: 2 },
            { label: 'Arts Dept', color: 'from-amber-500 to-orange-600', vlan: 'VLAN 30', devices: 2 },
          ].map(dept => (
            <div key={dept.label} className="bg-slate-50 dark:bg-slate-900/60 rounded-xl border border-slate-200 dark:border-slate-700/60 p-4">
              <div className="text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-3">Tier 2 — Distribution</div>
              <div className={clsx('p-3 rounded-lg bg-gradient-to-br mb-3 text-white text-sm font-semibold text-center shadow-md', dept.color)}>
                {dept.label}
                <div className="text-[10px] font-mono opacity-80 mt-0.5">{dept.vlan}</div>
              </div>
              <div className="text-xs font-mono uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-2">Tier 3 — Access</div>
              <div className="grid grid-cols-2 gap-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700/60 p-2 flex items-center gap-1.5">
                    <Wifi className="w-3 h-3 text-slate-400" />
                    <span className="text-[10px] font-mono text-slate-500">AP-{i + 1}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 pt-6 border-t border-slate-200 dark:border-slate-700/60 flex flex-wrap gap-3 justify-center text-xs">
          <span className="font-mono px-2 py-1 rounded bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800/60 text-blue-600 dark:text-blue-400">⬡ SIMULATION · Packet Tracer / GNS3</span>
          <span className="font-mono px-2 py-1 rounded bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400">274 Total Devices</span>
          <span className="font-mono px-2 py-1 rounded bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400">3 Academic VLANs</span>
          <span className="font-mono px-2 py-1 rounded bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400">250 Student Endpoints</span>
        </div>
      </div>
    </div>
  </section>
);

// ---- Section: Security ----
const securityFeatures = [
  { icon: <ShieldAlert className="w-5 h-5" />, title: 'Threat Detection', description: 'Behavioral anomaly detection flags suspicious traffic patterns in the simulated campus network.' },
  { icon: <Lock className="w-5 h-5" />, title: 'Config Compliance', description: 'Golden baseline comparisons identify configuration drift across switches, routers and firewalls.' },
  { icon: <Eye className="w-5 h-5" />, title: 'Security Event Monitoring', description: 'Centralized security event stream with severity scoring and analyst assignment workflow.' },
  { icon: <Database className="w-5 h-5" />, title: 'Evidence Management', description: 'Structured evidence collection for security incidents with chain-of-custody audit log.' },
  { icon: <CheckCircle className="w-5 h-5" />, title: 'Approval-Gated Remediation', description: 'All network changes require explicit approval before execution — no unreviewed automation.' },
  { icon: <TrendingUp className="w-5 h-5" />, title: 'Security Analytics', description: 'Trending security event data with per-VLAN and per-device threat score visualizations.' },
];

const SecuritySection: React.FC = () => (
  <section id="security" className="py-24 bg-white dark:bg-slate-950">
    <div className="max-w-7xl mx-auto px-6">
      <div className="text-center mb-14">
        <div className="text-xs font-mono uppercase tracking-widest text-red-500 mb-3">Security Operations</div>
        <h2 className="text-3xl font-extrabold text-slate-900 dark:text-white mb-4">
          Defensive Network Security
        </h2>
        <p className="text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">
          Integrated security operations capabilities within the simulation environment. All threat data and security events are synthetically generated for training purposes.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {securityFeatures.map((feat) => (
          <div key={feat.title} className="flex gap-4 p-5 bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-red-300 dark:hover:border-red-800/60 transition-colors group">
            <div className="p-2.5 rounded-lg bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 flex-shrink-0 h-fit group-hover:bg-red-100 dark:group-hover:bg-red-950/60 transition-colors">
              {feat.icon}
            </div>
            <div>
              <h3 className="font-semibold text-sm text-slate-900 dark:text-white mb-1">{feat.title}</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">{feat.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  </section>
);

// ---- Footer ----
const Footer: React.FC = () => (
  <footer className="bg-slate-900 dark:bg-slate-950 border-t border-slate-800 py-10">
    <div className="max-w-7xl mx-auto px-6">
      <div className="flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-cyan-700 flex items-center justify-center font-mono font-bold text-white text-sm">
            NG
          </div>
          <div>
            <div className="text-sm font-bold text-white">NETGUARDIAN</div>
            <div className="text-[10px] font-mono text-slate-500">SaturnX Academy · Campus Network Simulation</div>
          </div>
        </div>

        <div className="flex flex-wrap gap-4 text-xs font-mono text-slate-500 justify-center">
          <span className="px-2 py-1 rounded border border-blue-800 bg-blue-950/40 text-blue-400">⬡ LAB-SIMULATION</span>
          <span>React + TypeScript + Vite</span>
          <span>FastAPI + SQLAlchemy</span>
          <span>SQLite · CCNA Training Lab</span>
        </div>

        <div className="text-xs text-slate-600 font-mono text-center md:text-right">
          <div>NETGUARDIAN v1.0-L2/L3</div>
          <div className="mt-0.5">© 2024 SaturnX Academy · All simulation data is synthetic</div>
        </div>
      </div>
    </div>
  </footer>
);

// ---- Main Landing Page ----
export const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950">
      <LandingNav />
      <HeroSection />
      <CapabilitiesSection />
      <WorkflowSection />
      <ArchitectureSection />
      <SecuritySection />
      <Footer />
    </div>
  );
};
