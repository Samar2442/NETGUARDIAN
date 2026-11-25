import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../../store/useAppStore';
import { ThemeToggle } from '../design-system/ThemeToggle';
import { clsx } from 'clsx';
import {
  ShieldAlert,
  Wifi,
  WifiOff,
  Bell,
  User,
  Clock,
  ChevronDown,
  LogOut,
  Settings,
  UserCheck,
} from 'lucide-react';

export const Navbar: React.FC = () => {
  const { environment, setEnvironment, role, switchRole, username, wsConnected, logout } = useAppStore();
  const navigate = useNavigate();
  const [time, setTime] = useState<string>('');
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC');
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const roleColors = {
    admin: 'text-red-600 dark:text-red-400',
    network_engineer: 'text-blue-600 dark:text-blue-400',
    viewer: 'text-slate-600 dark:text-slate-400',
  };

  return (
    <header className="h-14 bg-white dark:bg-slate-900/95 border-b border-slate-200 dark:border-slate-800 px-4 flex items-center justify-between z-30 backdrop-blur-sm flex-shrink-0">
      {/* Left: Brand */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-cyan-700 flex items-center justify-center font-mono font-bold text-white text-sm shadow-md shadow-cyan-900/30">
            NG
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm tracking-tight text-text-primary">NETGUARDIAN</span>
              <span className="hidden md:inline text-[9px] uppercase font-mono px-1.5 py-0.5 rounded bg-cyan-100 dark:bg-cyan-950 text-cyan-600 dark:text-cyan-400 border border-cyan-200 dark:border-cyan-800">
                v1.0-L2/L3
              </span>
            </div>
            <div className="text-[9px] text-text-muted font-mono uppercase tracking-widest hidden md:block">
              Detect · Understand · Predict · Recover
            </div>
          </div>
        </div>

        {/* Environment Badge */}
        <div className="hidden lg:flex items-center gap-2 pl-4 border-l border-slate-200 dark:border-slate-800">
          <span className="text-xs text-text-muted font-mono">ENV:</span>
          <select
            value={environment}
            onChange={(e) => setEnvironment(e.target.value as any)}
            className="text-xs font-mono bg-slate-100 dark:bg-slate-950 border border-slate-300 dark:border-slate-700 text-cyan-600 dark:text-cyan-300 rounded px-2 py-1 focus:outline-none focus:border-cyan-500"
          >
            <option value="LAB-SIMULATION">SIMULATION (Packet Tracer)</option>
            <option value="CISCO-PROD">CISCO HARDWARE (SSH/SNMP)</option>
          </select>
        </div>
      </div>

      {/* Right: Controls */}
      <div className="flex items-center gap-2">
        {/* Connection Status */}
        <div className={clsx(
          'hidden sm:flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded-md border',
          wsConnected
            ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800/60 text-emerald-600 dark:text-emerald-400'
            : 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800/60 text-amber-600 dark:text-amber-400'
        )}>
          {wsConnected ? (
            <><span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /><span>LIVE</span></>
          ) : (
            <><span className="w-1.5 h-1.5 rounded-full bg-amber-500" /><span>POLLING</span></>
          )}
        </div>

        {/* Clock */}
        <div className="hidden lg:flex items-center gap-1.5 text-xs font-mono text-text-muted">
          <Clock className="w-3.5 h-3.5" />
          <span>{time}</span>
        </div>

        {/* Theme Toggle */}
        <ThemeToggle compact />

        {/* Notifications */}
        <button className="relative p-1.5 rounded-md text-text-muted hover:text-text-primary hover:bg-surface-tertiary dark:hover:bg-slate-800 transition-colors">
          <Bell className="w-4 h-4" />
        </button>

        {/* User Menu */}
        <div className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-md border border-slate-200 dark:border-slate-700 bg-surface dark:bg-slate-900 hover:bg-surface-tertiary dark:hover:bg-slate-800 transition-all"
          >
            <div className="w-5 h-5 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white text-[9px] font-bold uppercase">
              {username ? username[0] : 'U'}
            </div>
            <div className="hidden sm:block text-left">
              <div className="text-xs font-semibold text-text-primary leading-none">{username}</div>
              <div className={clsx('text-[10px] font-mono capitalize leading-none mt-0.5', roleColors[role as keyof typeof roleColors] || 'text-text-muted')}>{role}</div>
            </div>
            <ChevronDown className="w-3 h-3 text-text-muted" />
          </button>

          {userMenuOpen && (
            <div
              className="absolute right-0 top-full mt-1 w-52 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg shadow-xl shadow-black/10 dark:shadow-black/40 z-50 overflow-hidden"
              onMouseLeave={() => setUserMenuOpen(false)}
            >
              {/* User info */}
              <div className="px-3 py-2.5 border-b border-slate-200 dark:border-slate-800">
                <div className="text-xs font-semibold text-text-primary">{username}</div>
                <div className="text-[11px] text-text-muted font-mono mt-0.5">SaturnX Academy NOC</div>
              </div>

              {/* Role switcher */}
              <div className="px-3 py-2 border-b border-slate-200 dark:border-slate-800">
                <div className="text-[10px] text-text-muted font-mono uppercase mb-1.5">Switch Role</div>
                {(['admin', 'network_engineer', 'viewer'] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => { switchRole(r); setUserMenuOpen(false); }}
                    className={clsx(
                      'w-full text-left px-2 py-1 rounded text-xs transition-colors capitalize mb-0.5',
                      role === r
                        ? 'bg-cyan-50 dark:bg-cyan-950/40 text-cyan-600 dark:text-cyan-400 font-medium'
                        : 'text-text-secondary hover:bg-surface-tertiary dark:hover:bg-slate-800'
                    )}
                  >
                    {r === 'network_engineer' ? 'Network Engineer' : r.charAt(0).toUpperCase() + r.slice(1)}
                    {role === r && <span className="ml-1 text-[9px]">●</span>}
                  </button>
                ))}
              </div>

              {/* Actions */}
              <div className="p-1.5">
                <button
                  onClick={() => { navigate('/settings'); setUserMenuOpen(false); }}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded text-xs text-text-secondary hover:bg-surface-tertiary dark:hover:bg-slate-800 transition-colors"
                >
                  <Settings className="w-3.5 h-3.5" />
                  Settings
                </button>
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
