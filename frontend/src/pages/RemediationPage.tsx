import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { RemediationProposal } from '../types';
import { Badge } from '../components/common/Badge';
import { useAppStore } from '../store/useAppStore';
import {
  Wrench,
  CheckCircle2,
  XCircle,
  Play,
  RotateCcw,
  ShieldCheck,
  Terminal,
  AlertTriangle,
  FileCode,
} from 'lucide-react';

export const RemediationPage: React.FC = () => {
  const { role, username } = useAppStore();
  const [proposals, setProposals] = useState<RemediationProposal[]>([]);
  const [selectedProposal, setSelectedProposal] = useState<RemediationProposal | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadProposals = async () => {
    try {
      const data = await api.getRemediations();
      setProposals(data);
      if (data.length > 0) {
        setSelectedProposal(data[0]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadProposals();
  }, []);

  const handleApprove = async () => {
    if (!selectedProposal) return;
    setActionLoading(true);
    try {
      const updated = await api.approveRemediation(selectedProposal.id, username);
      await loadProposals();
      setSelectedProposal(updated);
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedProposal) return;
    setActionLoading(true);
    try {
      const updated = await api.rejectRemediation(selectedProposal.id, username);
      await loadProposals();
      setSelectedProposal(updated);
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!selectedProposal) return;
    setActionLoading(true);
    try {
      const res = await api.executeRemediation(selectedProposal.id, username);
      await loadProposals();
      const updated = await api.getRemediations();
      const match = updated.find((p) => p.id === selectedProposal.id);
      if (match) setSelectedProposal(match);
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRollback = async () => {
    if (!selectedProposal) return;
    setActionLoading(true);
    try {
      await api.rollbackRemediation(selectedProposal.id, username);
      await loadProposals();
      const updated = await api.getRemediations();
      const match = updated.find((p) => p.id === selectedProposal.id);
      if (match) setSelectedProposal(match);
    } catch (e) {
      console.error(e);
    } finally {
      setActionLoading(false);
    }
  };

  const canApprove = role === 'admin';

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <Wrench className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-white">Explainable Self-Healing & Remediation Hub</h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Controlled remediation workflow: DIAGNOSE → PROPOSE FIX → RISK ASSESSMENT → HUMAN APPROVAL → BACKUP → EXECUTE → VERIFY.
          </p>
        </div>
      </div>

      {proposals.length === 0 ? (
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-12 text-center font-mono text-xs text-slate-400">
          <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
          No remediation proposals pending review or execution.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Remediation Proposals List */}
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 space-y-3">
            <h3 className="text-xs font-mono uppercase text-slate-400 px-1">Remediation Proposals</h3>
            <div className="space-y-2">
              {proposals.map((p) => (
                <div
                  key={p.id}
                  onClick={() => setSelectedProposal(p)}
                  className={`p-3 rounded-md border font-mono text-xs cursor-pointer transition-colors ${
                    selectedProposal?.id === p.id
                      ? 'bg-cyan-950/40 border-cyan-700/80 text-cyan-200'
                      : 'bg-slate-950 border-slate-800 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <Badge variant={p.status === 'VERIFIED' ? 'success' : p.status === 'APPROVED' ? 'info' : 'warning'}>
                      {p.status}
                    </Badge>
                    <span className="text-[10px] text-slate-400">{new Date(p.created_at).toLocaleTimeString()}</span>
                  </div>
                  <div className="font-bold text-slate-100 text-xs truncate mt-1">{p.title}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Workflow Execution & Terminal View */}
          <div className="lg:col-span-2 space-y-5">
            {selectedProposal && (
              <>
                {/* Proposal Overview Card */}
                <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                    <div>
                      <h2 className="text-base font-bold text-white">{selectedProposal.title}</h2>
                      <p className="text-xs text-slate-400 mt-0.5">
                        Target Interface: {selectedProposal.target_interface || 'N/A'}
                        {selectedProposal.operation ? ` • Operation: ${selectedProposal.operation}` : ''}
                        {selectedProposal.execution_mode ? ` • Mode: ${selectedProposal.execution_mode}` : ''}
                      </p>
                      {selectedProposal.approval_digest && (
                        <p className="text-[10px] font-mono text-cyan-400/90 mt-1">
                          Approval Digest: {selectedProposal.approval_digest.slice(0, 16)}...
                        </p>
                      )}
                    </div>
                    <Badge variant={selectedProposal.status === 'VERIFIED' ? 'success' : 'warning'}>
                      {selectedProposal.status}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-4 text-xs font-mono">
                    <div>
                      <span className="text-slate-400 block mb-1">Risk Assessment:</span>
                      <Badge variant="success">LOW RISK (INTERFACE CONFIG ONLY)</Badge>
                    </div>
                    <div>
                      <span className="text-slate-400 block mb-1">Expected Recovery Result:</span>
                      <span className="text-slate-300">{selectedProposal.expected_result}</span>
                    </div>
                  </div>

                  {/* Proposed Cisco Commands */}
                  <div className="mb-4">
                    <div className="flex items-center space-x-1.5 text-xs font-mono text-slate-400 mb-1">
                      <FileCode className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Vetted Cisco Remediation Commands:</span>
                    </div>
                    <pre className="p-3 bg-slate-950 rounded border border-slate-800 font-mono text-xs text-emerald-400 overflow-x-auto">
                      {selectedProposal.proposed_commands}
                    </pre>
                  </div>

                  {/* Rollback Plan */}
                  <div className="mb-4">
                    <div className="flex items-center space-x-1.5 text-xs font-mono text-slate-400 mb-1">
                      <RotateCcw className="w-3.5 h-3.5 text-amber-400" />
                      <span>Automated Rollback Commands (if verification fails):</span>
                    </div>
                    <pre className="p-2.5 bg-slate-950 rounded border border-slate-800 font-mono text-xs text-slate-400 overflow-x-auto">
                      {selectedProposal.rollback_commands}
                    </pre>
                  </div>

                  {/* Approval Actions */}
                  <div className="pt-3 border-t border-slate-800 flex items-center justify-between">
                    <div className="text-xs font-mono text-slate-400">
                      {selectedProposal.approved_by ? (
                        <span>Approved by: <strong className="text-cyan-400">{selectedProposal.approved_by}</strong></span>
                      ) : (
                        <span className="text-amber-400 font-bold">Requires human administrator approval</span>
                      )}
                    </div>

                    <div className="flex items-center space-x-3">
                      {selectedProposal.status === 'PENDING_APPROVAL' && (
                        <>
                          <button
                            onClick={handleReject}
                            disabled={actionLoading || !canApprove}
                            className="px-3 py-1.5 bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800 rounded text-xs font-mono"
                          >
                            Reject
                          </button>
                          <button
                            onClick={handleApprove}
                            disabled={actionLoading || !canApprove}
                            className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold font-mono flex items-center space-x-1.5"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Approve Remediation</span>
                          </button>
                        </>
                      )}

                      {selectedProposal.status === 'APPROVED' && (
                        <button
                          onClick={handleExecute}
                          disabled={actionLoading}
                          className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold font-mono flex items-center space-x-1.5 shadow-lg shadow-emerald-950"
                        >
                          <Play className="w-3.5 h-3.5" />
                          <span>{actionLoading ? 'Executing...' : 'Execute Remediation & Verify'}</span>
                        </button>
                      )}

                      {selectedProposal.status === 'VERIFIED' && (
                        <button
                          onClick={handleRollback}
                          disabled={actionLoading}
                          className="px-3.5 py-1.5 bg-amber-950/60 hover:bg-amber-900 text-amber-300 border border-amber-800 rounded text-xs font-mono flex items-center space-x-1.5"
                        >
                          <RotateCcw className="w-3.5 h-3.5" />
                          <span>Rollback Configuration</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Execution Session & Verification Console */}
                {selectedProposal.execution_log && (
                  <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
                    <div className="flex items-center space-x-2 mb-3 pb-2 border-b border-slate-800">
                      <Terminal className="w-4 h-4 text-cyan-400" />
                      <h3 className="text-xs font-mono uppercase text-slate-300">
                        Cisco IOS Execution & Verification Console
                      </h3>
                    </div>
                    <pre className="p-4 bg-slate-950 rounded border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto max-h-80 leading-relaxed whitespace-pre-wrap">
                      {selectedProposal.execution_log}
                    </pre>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
