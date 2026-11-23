import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { api } from '../services/api';
import { Incident, Diagnosis } from '../types';
import { Badge } from '../components/common/Badge';
import { EvidenceGraph } from '../components/diagnostics/EvidenceGraph';
import {
  SearchCode,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Wrench,
  ArrowRight,
  HelpCircle,
  FileText,
} from 'lucide-react';

export const RcaPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const incidentParam = searchParams.get('incident');

  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [diagnosis, setDiagnosis] = useState<Diagnosis | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      setLoading(true);
      const incs = await api.getIncidents();
      setIncidents(incs);

      const target = incidentParam
        ? incs.find((i) => i.id === incidentParam) || incs[0]
        : incs[0];

      if (target) {
        setSelectedIncident(target);
        if (target.diagnosis) {
          setDiagnosis(target.diagnosis);
        } else {
          // Trigger diagnosis execution if missing
          const diag = await api.runDiagnostics(target.id);
          setDiagnosis(diag);
        }
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [incidentParam]);

  const selectIncident = async (inc: Incident) => {
    setSelectedIncident(inc);
    if (inc.diagnosis) {
      setDiagnosis(inc.diagnosis);
    } else {
      const diag = await api.runDiagnostics(inc.id);
      setDiagnosis(diag);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <SearchCode className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-white">Root-Cause Analysis & Evidence Engine</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Evidence-based diagnostic conclusions with weighted confidence, supporting facts, contradicting facts, and recommended Cisco CLI fixes.
          </p>
        </div>

        {selectedIncident && (
          <Link
            to="/remediation"
            className="flex items-center space-x-2 px-3.5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold"
          >
            <Wrench className="w-3.5 h-3.5" />
            <span>Open Remediation Workflow</span>
          </Link>
        )}
      </div>

      {incidents.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-12 text-center font-mono text-xs text-slate-400">
          <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
          No active incidents requiring root-cause analysis.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Incident Selector List */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
            <h3 className="text-xs font-mono uppercase text-slate-400 px-1">Correlated Incidents</h3>
            <div className="space-y-2">
              {incidents.map((inc) => (
                <div
                  key={inc.id}
                  onClick={() => selectIncident(inc)}
                  className={`p-3 rounded-md border font-mono text-xs cursor-pointer transition-colors ${
                    selectedIncident?.id === inc.id
                      ? 'bg-cyan-950/40 border-cyan-700/80 text-cyan-200'
                      : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold">{inc.incident_number}</span>
                    <Badge variant={inc.severity === 'high' || inc.severity === 'critical' ? 'danger' : 'warning'}>
                      {inc.severity}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-slate-300 truncate">{inc.title}</div>
                  <div className="text-[10px] text-slate-400 mt-1">
                    Status: <span className="text-slate-200">{inc.status}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Diagnosis & Evidence Display */}
          <div className="lg:col-span-2 space-y-6">
            {diagnosis ? (
              <>
                {/* Probable Root Cause Banner */}
                <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
                  <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-3">
                    <div className="flex items-center space-x-2">
                      <ShieldAlert className="w-5 h-5 text-rose-400" />
                      <span className="text-xs font-mono uppercase text-slate-400 tracking-wider">
                        Probable Root Cause Diagnosis
                      </span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-mono text-slate-400">Diagnostic Confidence:</span>
                      <span className="text-base font-mono font-bold text-emerald-400 bg-emerald-950 px-2 py-0.5 rounded border border-emerald-800">
                        {diagnosis.confidence}%
                      </span>
                    </div>
                  </div>

                  <h2 className="text-lg font-bold font-mono text-slate-100 mb-2">
                    {diagnosis.root_cause}
                  </h2>
                  <p className="text-xs text-slate-300 leading-relaxed font-sans mb-4">
                    {diagnosis.explanation}
                  </p>

                  <div className="bg-slate-950 p-3 rounded border border-slate-800 text-xs font-mono">
                    <span className="text-cyan-400 font-bold">RECOMMENDED CISCO ACTION: </span>
                    <span className="text-slate-200">{diagnosis.recommended_action}</span>
                  </div>
                </div>

                {/* Interactive Multi-Symptom Evidence Graph */}
                <EvidenceGraph
                  evidenceGraph={diagnosis.evidence_graph}
                  rootCause={diagnosis.root_cause}
                  confidence={diagnosis.confidence}
                />

                {/* Evidence Lists (Supporting & Contradicting) */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Supporting Evidence */}
                  <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                    <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-800">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <h4 className="text-xs font-mono font-bold uppercase text-emerald-400">
                        Supporting Evidence
                      </h4>
                    </div>
                    <ul className="space-y-2 text-xs font-mono text-slate-300">
                      {diagnosis.supporting_evidence.map((ev, idx) => (
                        <li key={idx} className="flex items-start space-x-2">
                          <span className="text-emerald-500 font-bold">•</span>
                          <span>{ev}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {/* Contradicting Evidence */}
                  <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                    <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-800">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      <h4 className="text-xs font-mono font-bold uppercase text-amber-400">
                        Contradicting / Ruled-Out Factors
                      </h4>
                    </div>
                    <ul className="space-y-2 text-xs font-mono text-slate-300">
                      {diagnosis.contradicting_evidence.length === 0 ? (
                        <li className="text-slate-500">None detected.</li>
                      ) : (
                        diagnosis.contradicting_evidence.map((ev, idx) => (
                          <li key={idx} className="flex items-start space-x-2">
                            <span className="text-amber-500 font-bold">•</span>
                            <span>{ev}</span>
                          </li>
                        ))
                      )}
                    </ul>
                  </div>
                </div>

                {/* Verification Procedure */}
                <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
                  <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-800">
                    <FileText className="w-4 h-4 text-cyan-400" />
                    <h4 className="text-xs font-mono font-bold uppercase text-cyan-400">
                      Standard Verification Procedure
                    </h4>
                  </div>
                  <div className="space-y-1.5 font-mono text-xs text-slate-300">
                    {diagnosis.verification_steps.map((st, idx) => (
                      <div key={idx} className="p-2 rounded bg-slate-950 border border-slate-800/80">
                        {st}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="p-8 text-center text-slate-400 font-mono text-xs">
                Select an incident to view root-cause analysis.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
