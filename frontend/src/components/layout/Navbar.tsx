import React, { useState, useEffect } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { 
  ShieldAlert, Activity, Wifi, WifiOff, Bell, User, Clock, Search, ChevronDown, CheckCircle2 
} from 'lucide-react';

export const Navbar: React.FC = () => {
  const { environment, setEnvironment, role, switchRole, username, wsConnected } = useAppStore();
  const [time, setTime] = useState<string>('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC');
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-14 bg-slate-900/90 border-b border-slate-800 px-6 flex items-center justify-between z-20 backdrop-blur sticky top-0">
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded bg-cyan-600 flex items-center justify-center font-mono font-bold text-white shadow-md shadow-cyan-900/50">
            NG
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-base tracking-tight text-white">NETGUARDIAN</span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">
                v1.0-L2/L3
              </span>
            </div>
            <div className="text-[10px] text-slate-400 tracking-wide font-medium">
              DETECT. UNDERSTAND. PREDICT. RECOVER.
            </div>
          </div>
        </div>

        {/* Environment Badge & Switcher */}
        <div className="flex items-center space-x-2 pl-4 border-l border-slate-800">
          <span className="text-xs text-slate-400 font-mono">ENV:</span>
          <select
            value={environment}
            onChange={(e) => setEnvironment(e.target.value as any)}
            className="text-xs font-mono bg-slate-950 border border-slate-700 text-cyan-300 rounded px-2.5 py-1 focus:outline-none focus:border-cyan-500"
          >
            <option value="LAB-SIMULATION">DEMO: LAB-SIMULATION (Packet Tracer)</option>
            <option value="CISCO-PROD">LIVE: CISCO HARDWARE (SSH/SNMP)</option>
          </select>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        {/* Connection status */}
        <div className="flex items-center space-x-1.5 text-xs font-mono px-2 py-1 rounded bg-slate-950 border border-slate-800">
          {wsConnected ? (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span className="text-emerald-400">TELEMETRY LIVE</span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-amber-400"></span>
              <span className="text-amber-400">POLLING ACTIVE</span>
            </>
          )}
        </div>

        {/* System Time */}
        <div className="hidden lg:flex items-center space-x-1.5 text-xs font-mono text-slate-400">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span>{time}</span>
        </div>

        {/* Role Switcher */}
        <div className="flex items-center space-x-2 bg-slate-950 px-2.5 py-1 rounded border border-slate-800">
          <User className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-xs font-mono text-slate-200">{username}</span>
          <select
            value={role}
            onChange={(e) => switchRole(e.target.value as any)}
            className="text-[11px] font-mono bg-transparent text-slate-400 border-0 focus:outline-none cursor-pointer"
          >
            <option value="admin">Role: Admin</option>
            <option value="network_engineer">Role: Net Engineer</option>
            <option value="viewer">Role: Viewer</option>
          </select>
        </div>
      </div>
    </header>
  );
};
