import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { AuditLog } from '../types';
import { Badge } from '../components/common/Badge';
import { FileText, Search, ShieldCheck } from 'lucide-react';

export const AuditLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const loadLogs = async () => {
    try {
      setLoading(true);
      const data = await api.getAuditLogs(100);
      setLogs(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  const filtered = logs.filter(
    (l) =>
      l.action.toLowerCase().includes(search.toLowerCase()) ||
      l.username.toLowerCase().includes(search.toLowerCase()) ||
      l.resource_type.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <FileText className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-slate-900 dark:text-white">Immutable Administrative & Remediation Audit Logs</h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Tamper-evident record of all operator approvals, configuration mutations, CLI executions, and recovery verifications.
          </p>
        </div>

        <input
          type="text"
          placeholder="Filter audit actions..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs font-mono rounded px-3 py-2 text-slate-800 dark:text-slate-200 focus:outline-none focus:border-cyan-500 w-56"
        />
      </div>

      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 dark:text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="p-3.5">Timestamp</th>
                <th className="p-3.5">Operator</th>
                <th className="p-3.5">Action</th>
                <th className="p-3.5">Resource</th>
                <th className="p-3.5">Details</th>
                <th className="p-3.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filtered.map((l) => (
                <tr key={l.id} className="hover:bg-slate-850/50">
                  <td className="p-3.5 text-slate-500 dark:text-slate-400">
                    {new Date(l.timestamp).toLocaleTimeString()}
                  </td>
                  <td className="p-3.5 font-bold text-cyan-400">{l.username}</td>
                  <td className="p-3.5 text-slate-800 dark:text-slate-200 font-bold">{l.action}</td>
                  <td className="p-3.5 text-slate-700 dark:text-slate-300 uppercase">{l.resource_type}</td>
                  <td className="p-3.5 text-slate-500 dark:text-slate-400 max-w-xs truncate">
                    {JSON.stringify(l.details)}
                  </td>
                  <td className="p-3.5">
                    <Badge variant={l.status === 'SUCCESS' ? 'success' : 'danger'}>
                      {l.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
