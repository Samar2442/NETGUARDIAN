import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Badge } from '../components/common/Badge';
import { Network3DCard } from '../components/3d/Network3DCard';
import { useAppStore } from '../store/useAppStore';
import { AlertOctagon, MessageSquare, Clock, UserCheck } from 'lucide-react';

export const IncidentsPage: React.FC = () => {
  const { role } = useAppStore();
  const [incidents, setIncidents] = useState<any[]>([]);
  const [selected, setSelected] = useState<any | null>(null);
  const [notes, setNotes] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [noteInput, setNoteInput] = useState('');
  const [assignee, setAssignee] = useState('neteng');
  const [search, setSearch] = useState('');
  const [sevFilter, setSevFilter] = useState('');
  const [stateFilter, setStateFilter] = useState('');
  const [devices, setDevices] = useState<any[]>([]);
  const [links, setLinks] = useState<any[]>([]);

  const loadIncidents = async () => {
    try {
      const [data, devs, lks] = await Promise.all([
        api.getIncidents(),
        api.getDevices().catch(() => []),
        api.getLinks().catch(() => []),
      ]);
      setIncidents(data);
      setDevices(devs || []);
      setLinks(lks || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadIncidents();
  }, []);

  const selectIncident = async (inc: any) => {
    setSelected(inc);
    try {
      const [n, t] = await Promise.all([
        api.getIncidentNotes(inc.id).catch(() => []),
        api.getIncidentTimeline(inc.id).catch(() => []),
      ]);
      setNotes(n);
      setTimeline(t);
    } catch {
      setNotes([]);
      setTimeline([]);
    }
  };

  const handleAssign = async () => {
    if (!selected) return;
    const updated = await api.assignIncident(selected.id, assignee);
    await loadIncidents();
    await selectIncident(updated);
  };

  const handleTransition = async (targetState: string) => {
    if (!selected) return;
    const updated = await api.transitionIncident(selected.id, targetState, `NOC workflow -> ${targetState}`);
    await loadIncidents();
    await selectIncident(updated);
  };

  const handleAddNote = async () => {
    if (!selected || !noteInput.trim()) return;
    await api.addIncidentNote(selected.id, noteInput.trim());
    setNoteInput('');
    await selectIncident(selected);
  };

  const filtered = incidents.filter((i) => {
    const matchesSearch =
      i.incident_number.toLowerCase().includes(search.toLowerCase()) ||
      i.title.toLowerCase().includes(search.toLowerCase()) ||
      (i.source_device_name || '').toLowerCase().includes(search.toLowerCase());
    const matchesSev = !sevFilter || (i.severity || '').toUpperCase() === sevFilter;
    const matchesState = !stateFilter || (i.lifecycle_state || 'NEW') === stateFilter;
    return matchesSearch && matchesSev && matchesState;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <AlertOctagon className="w-5 h-5 text-rose-400" />
            <h1 className="text-lg font-bold text-slate-900 dark:text-white">NOC Incident Operations Center</h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Enterprise lifecycle: NEW → ACKNOWLEDGED → IN_PROGRESS → MITIGATED → RESOLVED → CLOSED
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          <input
            type="text"
            placeholder="Search incident..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-3 py-1.5 text-slate-800 dark:text-slate-200 w-44"
          />
          <select value={sevFilter} onChange={(e) => setSevFilter(e.target.value)} className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-2.5 py-1.5 text-slate-800 dark:text-slate-200">
            <option value="">All Severities</option>
            <option value="CRITICAL">CRITICAL</option>
            <option value="HIGH">HIGH</option>
            <option value="MEDIUM">MEDIUM</option>
          </select>
          <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-2.5 py-1.5 text-slate-800 dark:text-slate-200">
            <option value="">All States</option>
            <option value="NEW">NEW</option>
            <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
            <option value="IN_PROGRESS">IN_PROGRESS</option>
            <option value="MITIGATED">MITIGATED</option>
            <option value="RESOLVED">RESOLVED</option>
            <option value="CLOSED">CLOSED</option>
          </select>
        </div>
      </div>

      <Network3DCard
        title="3D Affected Device Highlighting"
        subtitle={selected ? `Focusing incident: ${selected.incident_number} (${selected.source_device_name || 'N/A'})` : 'Select an incident to highlight affected device'}
        nodes={devices}
        links={links}
        mode="incident"
        highlightIds={selected?.source_device_id ? [selected.source_device_id] : []}
        heightClass="h-56"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 dark:text-slate-400 uppercase text-[10px] border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="p-3">Incident</th>
                <th className="p-3">Title</th>
                <th className="p-3">Priority / Sev</th>
                <th className="p-3">Lifecycle</th>
                <th className="p-3">Owner</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-800 dark:text-slate-200">
              {filtered.length === 0 ? (
                <tr><td colSpan={5} className="p-8 text-center text-slate-500 dark:text-slate-400">No incidents match filters.</td></tr>
              ) : (
                filtered.map((inc) => (
                  <tr
                    key={inc.id}
                    onClick={() => selectIncident(inc)}
                    className={`cursor-pointer hover:bg-slate-800/50 ${selected?.id === inc.id ? 'bg-cyan-950/30' : ''}`}
                  >
                    <td className="p-3 font-bold text-cyan-400">{inc.incident_number}</td>
                    <td className="p-3 truncate max-w-[220px]">{inc.title}</td>
                    <td className="p-3">
                      <Badge variant={(inc.severity || '').toLowerCase() === 'critical' ? 'danger' : 'warning'}>
                        {inc.priority || 'P2'} / {inc.severity}
                      </Badge>
                    </td>
                    <td className="p-3">
                      <Badge variant={inc.lifecycle_state === 'RESOLVED' || inc.lifecycle_state === 'CLOSED' ? 'success' : 'info'}>
                        {inc.lifecycle_state || inc.status}
                      </Badge>
                    </td>
                    <td className="p-3">{inc.assigned_to || 'Unassigned'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 font-mono text-xs space-y-4 h-fit">
          {!selected ? (
            <div className="text-slate-500">Select an incident to manage assignment, transitions, notes, and timeline.</div>
          ) : (
            <>
              <div className="border-b border-slate-200 dark:border-slate-800 pb-2">
                <div className="font-bold text-cyan-400">{selected.incident_number}</div>
                <div className="text-slate-900 dark:text-slate-100 font-semibold mt-0.5">{selected.title}</div>
                <div className="text-slate-500 dark:text-slate-400 text-[11px] mt-1">{selected.description}</div>
              </div>

              {(role === 'admin' || role === 'network_engineer') && (
                <div className="space-y-2 border-b border-slate-200 dark:border-slate-800 pb-3">
                  {role === 'admin' && (
                    <div className="flex gap-2">
                      <select value={assignee} onChange={(e) => setAssignee(e.target.value)} className="flex-1 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-2 py-1 text-slate-800 dark:text-slate-200">
                        <option value="neteng">neteng</option>
                        <option value="admin">admin</option>
                      </select>
                      <button onClick={handleAssign} className="px-3 py-1 bg-indigo-700 hover:bg-indigo-600 text-white rounded flex items-center space-x-1">
                        <UserCheck className="w-3 h-3" /><span>Assign</span>
                      </button>
                    </div>
                  )}

                  <div className="flex flex-wrap gap-1.5">
                    {['ACKNOWLEDGED', 'IN_PROGRESS', 'MITIGATED', 'RESOLVED', 'CLOSED'].map((st) => (
                      <button
                        key={st}
                        onClick={() => handleTransition(st).catch((e) => alert(e.message))}
                        className="px-2 py-1 bg-slate-100 dark:bg-slate-800 hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded text-[10px]"
                      >
                        → {st}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <div className="text-slate-500 dark:text-slate-400 uppercase mb-1.5 flex items-center space-x-1">
                  <MessageSquare className="w-3.5 h-3.5" /><span>Investigation Notes ({notes.length})</span>
                </div>
                <div className="space-y-1.5 max-h-28 overflow-y-auto mb-2">
                  {notes.map((n) => (
                    <div key={n.id} className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded p-2 text-[11px]">
                      <span className="text-cyan-400 font-bold">{n.author}:</span> {n.content}
                    </div>
                  ))}
                </div>
                {(role === 'admin' || role === 'network_engineer') && (
                  <div className="flex gap-1.5">
                    <input
                      value={noteInput}
                      onChange={(e) => setNoteInput(e.target.value)}
                      placeholder="Add investigation note..."
                      className="flex-1 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded px-2 py-1 text-slate-800 dark:text-slate-200"
                    />
                    <button onClick={handleAddNote} className="px-2.5 py-1 bg-cyan-700 hover:bg-cyan-600 text-white rounded">Add</button>
                  </div>
                )}
              </div>

              <div>
                <div className="text-slate-500 dark:text-slate-400 uppercase mb-1.5 flex items-center space-x-1">
                  <Clock className="w-3.5 h-3.5" /><span>Activity Timeline ({timeline.length})</span>
                </div>
                <div className="space-y-1 max-h-32 overflow-y-auto text-[10px]">
                  {timeline.map((t) => (
                    <div key={t.id} className="flex justify-between bg-slate-950/70 px-2 py-1 rounded">
                      <span><strong className="text-slate-800 dark:text-slate-200">{t.action}</strong> ({t.actor})</span>
                      <span className="text-slate-500">{new Date(t.timestamp).toLocaleTimeString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
