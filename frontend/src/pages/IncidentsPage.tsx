import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Incident } from '../types';
import { Badge } from '../components/common/Badge';
import { Link } from 'react-router-dom';
import { AlertOctagon, Search, ArrowRight, ShieldAlert, CheckCircle2, RefreshCw } from 'lucide-react';

export const IncidentsPage: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const loadIncidents = async () => {
    try {
      setLoading(true);
      const data = await api.getIncidents();
      setIncidents(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIncidents();
  }, []);

  const filtered = incidents.filter(
    (i) =>
      i.incident_number.toLowerCase().includes(search.toLowerCase()) ||
      i.title.toLowerCase().includes(search.toLowerCase()) ||
      (i.source_device_name || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <AlertOctagon className="w-5 h-5 text-rose-400" />
            <h1 className="text-lg font-bold text-white">Incident Lifecycle Management</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Complete incident progression: DETECTED → ROOT CAUSE IDENTIFIED → REMEDIATION PROPOSED → APPROVED → VERIFIED → RESOLVED.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <input
            type="text"
            placeholder="Search incident..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-slate-950 border border-slate-800 text-xs font-mono rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-cyan-500 w-56"
          />
          <button
            onClick={loadIncidents}
            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs font-mono border border-slate-700"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="p-3.5">Incident Number</th>
                <th className="p-3.5">Title & Description</th>
                <th className="p-3.5">Severity</th>
                <th className="p-3.5">Status</th>
                <th className="p-3.5">Source Device</th>
                <th className="p-3.5">Affected Endpoints</th>
                <th className="p-3.5">Created At</th>
                <th className="p-3.5">Diagnostics</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">
                    No active or historical incidents found.
                  </td>
                </tr>
              ) : (
                filtered.map((inc) => (
                  <tr key={inc.id} className="hover:bg-slate-850/50">
                    <td className="p-3.5 font-bold text-cyan-400">{inc.incident_number}</td>
                    <td className="p-3.5 max-w-xs">
                      <div className="font-bold text-slate-200 truncate">{inc.title}</div>
                      <div className="text-[10px] text-slate-400 truncate">{inc.description}</div>
                    </td>
                    <td className="p-3.5">
                      <Badge variant={inc.severity === 'critical' || inc.severity === 'high' ? 'danger' : 'warning'}>
                        {inc.severity.toUpperCase()}
                      </Badge>
                    </td>
                    <td className="p-3.5">
                      <Badge variant={inc.status === 'RESOLVED' ? 'success' : 'purple'}>
                        {inc.status}
                      </Badge>
                    </td>
                    <td className="p-3.5 text-slate-300">{inc.source_device_name || 'N/A'}</td>
                    <td className="p-3.5 text-amber-400 font-bold">{inc.affected_endpoints_count || 1} devices</td>
                    <td className="p-3.5 text-slate-400">{new Date(inc.created_at).toLocaleTimeString()}</td>
                    <td className="p-3.5">
                      <Link
                        to={`/diagnostics?incident=${inc.id}`}
                        className="px-2.5 py-1 bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800 rounded text-[11px] inline-flex items-center space-x-1"
                      >
                        <span>Inspect RCA</span>
                        <ArrowRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
