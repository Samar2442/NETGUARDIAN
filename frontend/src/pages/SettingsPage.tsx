import React from 'react';
import { useAppStore } from '../store/useAppStore';
import { Badge } from '../components/common/Badge';
import { Settings as SettingsIcon, Shield, Sliders, Database, Server, Key } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { environment, setEnvironment, role, username } = useAppStore();

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div className="flex items-center space-x-3">
          <SettingsIcon className="w-5 h-5 text-cyan-400" />
          <h1 className="text-lg font-bold text-slate-900 dark:text-white">System Configuration & Security Settings</h1>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Configure telemetry collection intervals, environment mode, SSH credential vaults, and RBAC roles.
        </p>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 space-y-4 font-mono text-xs">
        <h3 className="font-bold uppercase text-slate-700 dark:text-slate-300 pb-2 border-b border-slate-200 dark:border-slate-800">
          Environment & Simulation Mode
        </h3>

        <div className="grid grid-cols-2 gap-4 items-center">
          <div>
            <div className="text-slate-800 dark:text-slate-200 font-bold">Active Operational Mode:</div>
            <div className="text-slate-500 dark:text-slate-400 text-[11px]">
              Demarcates between mock lab simulation and live hardware SSH connectivity.
            </div>
          </div>
          <div>
            <Badge variant="info">{environment}</Badge>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 items-center pt-2">
          <div>
            <div className="text-slate-800 dark:text-slate-200 font-bold">Telemetry Polling Interval:</div>
            <div className="text-slate-500 dark:text-slate-400 text-[11px]">Background scheduler cycle frequency.</div>
          </div>
          <div className="text-cyan-400 font-bold">10 Seconds</div>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 space-y-4 font-mono text-xs">
        <h3 className="font-bold uppercase text-slate-700 dark:text-slate-300 pb-2 border-b border-slate-200 dark:border-slate-800">
          Role-Based Access Control (RBAC)
        </h3>

        <div className="grid grid-cols-2 gap-4 items-center">
          <div>
            <div className="text-slate-800 dark:text-slate-200 font-bold">Current Operator:</div>
            <div className="text-slate-500 dark:text-slate-400 text-[11px]">Active authenticated session.</div>
          </div>
          <div className="text-cyan-400 font-bold">{username} (Role: {role})</div>
        </div>

        <div className="grid grid-cols-2 gap-4 items-center pt-2">
          <div>
            <div className="text-slate-800 dark:text-slate-200 font-bold">Remediation Approval Authority:</div>
            <div className="text-slate-500 dark:text-slate-400 text-[11px]">Requires Administrator or Network Engineer privilege.</div>
          </div>
          <div>
            <Badge variant={role === 'admin' || role === 'network_engineer' ? 'success' : 'danger'}>
              {role === 'admin' || role === 'network_engineer' ? 'AUTHORIZED' : 'RESTRICTED (VIEW ONLY)'}
            </Badge>
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 space-y-3 font-mono text-xs">
        <h3 className="font-bold uppercase text-slate-700 dark:text-slate-300 pb-2 border-b border-slate-200 dark:border-slate-800">
          Cisco Device Credential Vault (Production)
        </h3>
        <p className="text-slate-500 dark:text-slate-400 text-[11px]">
          Credentials are stored encrypted via environment variables and never exposed to client-side code.
        </p>
        <div className="p-3 rounded bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-[11px] text-slate-500 dark:text-slate-400">
          SSH Port: 22 | Key Exchange: diffie-hellman-group14-sha1, rsa-sha2-256 | Ciphers: aes256-ctr
        </div>
      </div>
    </div>
  );
};
