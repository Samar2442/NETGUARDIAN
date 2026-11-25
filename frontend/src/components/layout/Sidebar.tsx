import React, { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAppStore } from '../../store/useAppStore';
import { clsx } from 'clsx';
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
  ChevronDown,
  ChevronRight,
  Shield,
  Zap,
} from 'lucide-react';

interface NavItem {
  name: string;
  path: string;
  icon: React.ElementType;
}

interface NavGroup {
  label: string;
  icon: React.ElementType;
  items: NavItem[];
  defaultOpen?: boolean;
}

const navGroups: NavGroup[] = [
  {
    label: 'Overview',
    icon: LayoutDashboard,
    defaultOpen: true,
    items: [
      { name: 'Dashboard', path: '/', icon: LayoutDashboard },
      { name: 'Campus Inventory', path: '/campus-inventory', icon: Users },
      { name: 'Analytics', path: '/analytics', icon: LineChart },
    ],
  },
  {
    label: 'Network Operations',
    icon: Network,
    defaultOpen: true,
    items: [
      { name: 'Network Topology', path: '/topology', icon: Network },
      { name: 'Devices', path: '/devices', icon: Server },
      { name: 'Interfaces', path: '/interfaces', icon: Cpu },
      { name: 'VLAN Management', path: '/vlans', icon: Layers },
      { name: 'Routing', path: '/routing', icon: GitBranch },
      { name: 'Monitoring', path: '/monitoring', icon: Activity },
    ],
  },
  {
    label: 'Incident Management',
    icon: AlertOctagon,
    defaultOpen: true,
    items: [
      { name: 'Incidents', path: '/incidents', icon: AlertOctagon },
      { name: 'Fault Simulation', path: '/fault-simulation', icon: Flame },
      { name: 'Services & SLA', path: '/services', icon: ShieldCheck },
    ],
  },
  {
    label: 'Intelligence',
    icon: SearchCode,
    defaultOpen: false,
    items: [
      { name: 'Root-Cause Analysis', path: '/diagnostics', icon: SearchCode },
      { name: 'Digital Twin', path: '/simulator', icon: Box },
      { name: 'Remediation', path: '/remediation', icon: Wrench },
    ],
  },
  {
    label: 'Security',
    icon: ShieldAlert,
    defaultOpen: false,
    items: [
      { name: 'Security Ops', path: '/security', icon: ShieldAlert },
    ],
  },
  {
    label: 'Administration',
    icon: Settings,
    defaultOpen: false,
    items: [
      { name: 'Integrations & Labs', path: '/integrations', icon: Plug },
      { name: 'Training Lab', path: '/training', icon: GraduationCap },
      { name: 'Audit Logs', path: '/audit', icon: FileText },
      { name: 'Settings', path: '/settings', icon: Settings },
    ],
  },
];

const NavGroupSection: React.FC<{ group: NavGroup }> = ({ group }) => {
  const [open, setOpen] = useState(group.defaultOpen ?? true);
  const GroupIcon = group.icon;

  return (
    <div className="mb-1">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-1.5 rounded text-[10px] font-semibold uppercase tracking-widest text-text-muted hover:text-text-secondary transition-colors"
      >
        <div className="flex items-center gap-1.5">
          <GroupIcon className="w-3 h-3" />
          {group.label}
        </div>
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
      </button>

      {open && (
        <div className="mt-0.5 space-y-0.5">
          {group.items.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === '/'}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-2.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all group',
                    isActive
                      ? 'bg-cyan-500/10 dark:bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20 dark:border-cyan-800/50'
                      : 'text-text-secondary hover:text-text-primary hover:bg-surface-tertiary dark:hover:bg-slate-800/50'
                  )
                }
              >
                <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </div>
      )}
    </div>
  );
};

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-56 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col flex-shrink-0 select-none">
      {/* Logo / Brand */}
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-gradient-to-br from-cyan-500 to-cyan-700 flex items-center justify-center font-mono font-bold text-white text-xs shadow-md">
            NG
          </div>
          <div>
            <div className="text-sm font-bold text-text-primary tracking-tight">NETGUARDIAN</div>
            <div className="text-[9px] font-mono text-text-muted uppercase tracking-wider">SaturnX Academy</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto space-y-1">
        {navGroups.map((group) => (
          <NavGroupSection key={group.label} group={group} />
        ))}
      </nav>

      {/* Footer */}
      <div className="px-3 py-2.5 border-t border-slate-200 dark:border-slate-800 bg-surface-tertiary dark:bg-slate-950/40">
        <div className="flex items-center justify-between text-[10px] font-mono">
          <span className="text-text-muted">v1.0-L2/L3</span>
          <span className="text-cyan-600 dark:text-cyan-500 font-semibold flex items-center gap-1">
            <Shield className="w-2.5 h-2.5" />
            CCNA Lab
          </span>
        </div>
        <div className="mt-1 text-[9px] text-text-muted font-mono uppercase tracking-wider">
          SIMULATION Environment
        </div>
      </div>
    </aside>
  );
};
