import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Event, HealthOverview } from '../types';
import { Badge } from '../components/common/Badge';
import { Activity, Play, Bell, Shield, Filter, RefreshCw } from 'lucide-react';

export const MonitoringPage: React.FC = () => {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);

  const loadEvents = async () => {
    try {
      setLoading(true);
      const data = await api.getEvents(50);
      setEvents(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, []);

  const triggerPoll = async () => {
    try {
      setPolling(true);
      await api.pollMetrics();
      await loadEvents();
    } catch (e) {
      console.error(e);
    } finally {
      setPolling(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <Activity className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-white">Live Monitoring & Telemetry Stream</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Raw event ingestion from ICMP probes, Cisco Syslog, SNMP traps, and interface status transitions.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={triggerPoll}
            disabled={polling}
            className="flex items-center space-x-2 px-3.5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold font-mono"
          >
            <Play className="w-3.5 h-3.5" />
            <span>{polling ? 'Polling Devices...' : 'Execute Manual Poll'}</span>
          </button>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <span className="text-xs font-mono uppercase text-slate-400">Ingested Telemetry Stream</span>
          <Badge variant="info">Total Events: {events.length}</Badge>
        </div>

        <div className="divide-y divide-slate-800/60 max-h-[600px] overflow-y-auto">
          {events.length === 0 ? (
            <div className="p-8 text-center text-slate-400 font-mono text-xs">
              No recent anomalies or syslog events logged.
            </div>
          ) : (
            events.map((ev) => (
              <div key={ev.id} className="p-4 hover:bg-slate-850/50 font-mono text-xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="text-slate-400 text-[10px]">
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </span>
                    <Badge variant={ev.severity === 'high' || ev.severity === 'critical' ? 'danger' : 'warning'}>
                      {ev.event_type}
                    </Badge>
                    <span className="font-bold text-slate-200">{ev.source_name}</span>
                  </div>
                  <span className="text-[10px] text-slate-400 uppercase">
                    Source: {ev.source_type}
                  </span>
                </div>
                <div className="text-slate-300 pl-4 border-l-2 border-cyan-800">
                  {ev.message}
                </div>
                {ev.raw_payload && (
                  <div className="bg-slate-950 p-2 rounded text-[11px] text-slate-400">
                    <span className="text-cyan-500">raw: </span>
                    {ev.raw_payload}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
