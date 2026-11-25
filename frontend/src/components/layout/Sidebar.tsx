import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Network,
  Server,
  Cpu,
  GitBranch,
  Layers,
  Activity,
  AlertOctagon,
  SearchCode,
  Box,
  Wrench,
  GraduationCap,
  LineChart,
  FileText,
  Settings,
  Users,
  Flame,
  ShieldCheck,
  ShieldAlert,
  Plug,
} from 'lucide-react';

const navItems = [
  { name: 'Overview', path: '/', icon: LayoutDashboard },
  { name: 'Network Topology', path: '/topology', icon: Network },
  { name: 'Campus Inventory', path: '/campus-inventory', icon: Users },
  { name: 'Devices', path: '/devices', icon: Server },
  { name: 'Interfaces', path: '/interfaces', icon: Cpu },
  { name: 'VLAN Management', path: '/vlans', icon: Layers },
  { name: 'Routing', path: '/routing', icon: GitBranch },
  { name: 'Monitoring', path: '/monitoring', icon: Activity },
  { name: 'Fault Simulation', path: '/fault-simulation', icon: Flame },
  { name: 'Incidents', path: '/incidents', icon: AlertOctagon },
  { name: 'Services & SLA', path: '/services', icon: ShieldCheck },
  { name: 'Security Ops', path: '/security', icon: ShieldAlert },
  { name: 'Integrations & Labs', path: '/integrations', icon: Plug },
  { name: 'Root-Cause Analysis', path: '/diagnostics', icon: SearchCode },
  { name: 'Digital Twin', path: '/simulator', icon: Box },
  { name: 'Remediation', path: '/remediation', icon: Wrench },
  { name: 'Training Lab', path: '/training', icon: GraduationCap },
  { name: 'Analytics', path: '/analytics', icon: LineChart },
  { name: 'Audit Logs', path: '/audit', icon: FileText },
  { name: 'Settings', path: '/settings', icon: Settings },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-60 bg-slate-900 border-r border-slate-800 flex flex-col flex-shrink-0 select-none">
      <div className="p-3 text-[11px] font-mono uppercase tracking-wider text-slate-400 px-4 border-b border-slate-800/80">
        Operations Navigation
      </div>
      <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center space-x-3 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-cyan-600/15 text-cyan-400 border border-cyan-800/60 shadow-sm font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span>{item.name}</span>
            </NavLink>
          );
        })}
      </nav>
      <div className="p-3 border-t border-slate-800 bg-slate-950/40 text-[11px] font-mono text-slate-400 flex items-center justify-between">
        <span>SaturnX Academy</span>
        <span className="text-cyan-500 font-bold">CCNA Lab</span>
      </div>
    </aside>
  );
};
