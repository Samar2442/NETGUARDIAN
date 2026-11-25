import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { TrainingScenario } from '../types';
import { Badge } from '../components/common/Badge';
import { useAppStore } from '../store/useAppStore';
import {
  GraduationCap,
  Play,
  CheckCircle2,
  AlertTriangle,
  Award,
  Clock,
  ArrowRight,
  BookOpen,
} from 'lucide-react';

export const TrainingLabPage: React.FC = () => {
  const { username } = useAppStore();
  const [scenarios, setScenarios] = useState<TrainingScenario[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<TrainingScenario | null>(null);
  const [injecting, setInjecting] = useState(false);
  const [injectionSuccess, setInjectionSuccess] = useState<string | null>(null);
  const [studentDiagnosis, setStudentDiagnosis] = useState('');
  const [gradingResult, setGradingResult] = useState<any | null>(null);
  const [grading, setGrading] = useState(false);

  const loadScenarios = async () => {
    try {
      const data = await api.getTrainingScenarios();
      setScenarios(data);
      if (data.length > 0) {
        setSelectedScenario(data[0]);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadScenarios();
  }, []);

  const handleInjectFault = async () => {
    if (!selectedScenario) return;
    setInjecting(true);
    setInjectionSuccess(null);
    setGradingResult(null);
    try {
      const res = await api.injectFault(selectedScenario.scenario_key, username);
      setInjectionSuccess(res.message);
    } catch (e: any) {
      setInjectionSuccess(`Injection failed: ${e.message}`);
    } finally {
      setInjecting(false);
    }
  };

  const handleGrade = async () => {
    if (!selectedScenario || !studentDiagnosis) return;
    setGrading(true);
    try {
      const res = await api.gradeDiagnosis(selectedScenario.expected_root_cause, studentDiagnosis);
      setGradingResult(res);
    } catch (e) {
      console.error(e);
    } finally {
      setGrading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <GraduationCap className="w-5 h-5 text-indigo-400" />
            <h1 className="text-lg font-bold text-slate-900 dark:text-white">SaturnX CCNA Troubleshooting & Fault-Injection Lab</h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Simulate real-world Cisco network outages, observe telemetry, formulate diagnostic hypotheses, and benchmark troubleshooting speed.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Scenario Selection */}
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 space-y-3">
          <h3 className="text-xs font-mono uppercase text-slate-500 dark:text-slate-400 px-1">Curated Lab Scenarios</h3>
          <div className="space-y-2">
            {scenarios.map((sc) => (
              <div
                key={sc.id}
                onClick={() => {
                  setSelectedScenario(sc);
                  setInjectionSuccess(null);
                  setGradingResult(null);
                }}
                className={`p-3 rounded-md border font-mono text-xs cursor-pointer transition-colors ${
                  selectedScenario?.id === sc.id
                    ? 'bg-indigo-950/40 border-indigo-700/80 text-indigo-200'
                    : 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-bold text-xs">{sc.title}</span>
                  <Badge variant={sc.difficulty === 'Beginner' ? 'success' : sc.difficulty === 'Intermediate' ? 'warning' : 'danger'}>
                    {sc.difficulty}
                  </Badge>
                </div>
                <div className="text-[10px] text-slate-500 dark:text-slate-400">{sc.category}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Lab Exercise & Fault Injection Panel */}
        <div className="lg:col-span-2 space-y-5">
          {selectedScenario && (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5 space-y-5">
              <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
                <div>
                  <h2 className="text-base font-bold text-slate-900 dark:text-white">{selectedScenario.title}</h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Target: {selectedScenario.target_device} ({selectedScenario.target_component})</p>
                </div>
                <Badge variant="purple">{selectedScenario.difficulty}</Badge>
              </div>

              <div className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                {selectedScenario.description}
              </div>

              {/* Reported Symptoms */}
              <div className="bg-slate-50 dark:bg-slate-950 p-4 rounded border border-slate-200 dark:border-slate-800">
                <h4 className="text-xs font-mono uppercase text-slate-500 dark:text-slate-400 mb-2 font-bold flex items-center space-x-1.5">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span>Reported Network Symptoms & Telemetry</span>
                </h4>
                <ul className="space-y-1.5 text-xs font-mono text-slate-700 dark:text-slate-300">
                  {selectedScenario.symptoms?.map((s, idx) => (
                    <li key={idx} className="flex items-start space-x-2">
                      <span className="text-amber-500 font-bold">•</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Fault Injection Button */}
              <div className="p-4 rounded-lg bg-indigo-950/20 border border-indigo-900/60 flex items-center justify-between">
                <div>
                  <div className="text-xs font-bold font-mono text-indigo-300">Phase 1: Controlled Fault Injection</div>
                  <div className="text-[11px] text-slate-500 dark:text-slate-400">
                    Triggers the failure condition in the active simulation environment and generates telemetry events.
                  </div>
                </div>
                <button
                  onClick={handleInjectFault}
                  disabled={injecting}
                  className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded text-xs font-mono font-semibold flex items-center space-x-1.5 shadow-lg shadow-rose-950"
                >
                  <Play className="w-3.5 h-3.5" />
                  <span>{injecting ? 'Injecting...' : 'Inject Fault into Lab'}</span>
                </button>
              </div>

              {injectionSuccess && (
                <div className="p-3 bg-emerald-950/60 border border-emerald-800 rounded text-xs font-mono text-emerald-300 flex items-center justify-between">
                  <span>{injectionSuccess}</span>
                  <a href="/diagnostics" className="text-cyan-400 hover:underline">
                    Observe in RCA Engine →
                  </a>
                </div>
              )}

              {/* Student Troubleshooting Exercise */}
              <div className="space-y-3 pt-3 border-t border-slate-200 dark:border-slate-800">
                <h4 className="text-xs font-mono uppercase text-slate-700 dark:text-slate-300 font-bold">
                  Phase 2: Formulate Your Diagnosis
                </h4>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Based on the symptoms, explain the probable root cause and which Cisco configuration is defective:
                </p>

                <textarea
                  value={studentDiagnosis}
                  onChange={(e) => setStudentDiagnosis(e.target.value)}
                  placeholder="e.g. VLAN 30 is missing from trunk port GigabitEthernet0/1 on HQ-Access-SW-02..."
                  className="w-full bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded p-3 text-xs font-mono text-slate-800 dark:text-slate-200 focus:outline-none focus:border-cyan-500 h-24"
                />

                <div className="flex justify-end">
                  <button
                    onClick={handleGrade}
                    disabled={grading || !studentDiagnosis}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-mono font-semibold flex items-center space-x-1.5"
                  >
                    <Award className="w-3.5 h-3.5" />
                    <span>{grading ? 'Evaluating...' : 'Submit & Benchmark Diagnosis'}</span>
                  </button>
                </div>
              </div>

              {/* Benchmark Results */}
              {gradingResult && (
                <div className="p-4 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg space-y-2 font-mono text-xs">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-2">
                    <span className="text-slate-500 dark:text-slate-400">Troubleshooting Accuracy:</span>
                    <span className="text-base font-bold text-emerald-400">{gradingResult.score}%</span>
                  </div>
                  <div className="text-slate-700 dark:text-slate-300">
                    <span className="text-cyan-400 font-bold">Instructor Feedback: </span>
                    {gradingResult.feedback}
                  </div>
                  <div className="text-[11px] text-slate-500 dark:text-slate-400 pt-1">
                    Expected Root Cause: <span className="text-slate-800 dark:text-slate-200">{selectedScenario.expected_root_cause}</span>
                  </div>
                  <div className="text-[11px] text-slate-500 dark:text-slate-400">
                    Cisco Solution: <code className="text-emerald-400">{selectedScenario.recommended_commands}</code>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
