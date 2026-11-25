import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Badge } from '../components/common/Badge';
import { StatCard } from '../components/common/StatCard';
import { Users, GraduationCap, Shield, Laptop, Search, CheckCircle2, AlertTriangle, ChevronLeft, ChevronRight } from 'lucide-react';

type TabKey = 'overview' | 'students' | 'faculty' | 'it' | 'assignments';

export const CampusInventoryPage: React.FC = () => {
  const [tab, setTab] = useState<TabKey>('overview');
  const [overview, setOverview] = useState<any | null>(null);
  const [validation, setValidation] = useState<any | null>(null);
  const [students, setStudents] = useState<any[]>([]);
  const [faculty, setFaculty] = useState<any[]>([]);
  const [itStaff, setItStaff] = useState<any[]>([]);
  const [assignments, setAssignments] = useState<any[]>([]);
  const [deptFilter, setDeptFilter] = useState<string>('');
  const [search, setSearch] = useState<string>('');
  const [page, setPage] = useState<number>(0);
  const [selectedStudentNet, setSelectedStudentNet] = useState<any | null>(null);
  const [netError, setNetError] = useState<string | null>(null);
  const pageSize = 25;

  const loadOverview = async () => {
    try {
      const [ov, val] = await Promise.all([
        api.getCampusInventoryOverview(),
        api.validateCampusInventory(),
      ]);
      setOverview(ov);
      setValidation(val);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadOverview();
  }, []);

  useEffect(() => {
    if (tab === 'students') {
      api.getCampusStudents({ department: deptFilter || undefined, search: search || undefined, limit: pageSize, offset: page * pageSize })
        .then(setStudents)
        .catch(console.error);
    } else if (tab === 'faculty') {
      api.getCampusFaculty(deptFilter || undefined).then(setFaculty).catch(console.error);
    } else if (tab === 'it') {
      api.getCampusITPersonnel().then(setItStaff).catch(console.error);
    } else if (tab === 'assignments') {
      api.getCampusAssignments({ department: deptFilter || undefined, limit: pageSize, offset: page * pageSize })
        .then(setAssignments)
        .catch(console.error);
    }
  }, [tab, deptFilter, search, page]);

  const handleInspectStudent = async (studentId: string) => {
    setNetError(null);
    setSelectedStudentNet(null);
    try {
      const data = await api.getStudentNetwork(studentId);
      setSelectedStudentNet(data);
    } catch (e: any) {
      setNetError(e?.message || 'Network assignment details require Engineer or Admin role.');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
        <div>
          <div className="flex items-center space-x-3">
            <Users className="w-5 h-5 text-cyan-400" />
            <h1 className="text-lg font-bold text-slate-900 dark:text-white">Campus Inventory & Identity Management</h1>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Synthetic campus personnel records (250 Students, 16 Faculty, 6 IT Personnel) bound to 3-tier network endpoints.
          </p>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {([
            ['overview', 'Overview'],
            ['students', 'Students'],
            ['faculty', 'Faculty'],
            ['it', 'IT Personnel'],
            ['assignments', 'Asset Assignments'],
          ] as [TabKey, string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => { setTab(key); setPage(0); }}
              className={`px-3 py-1.5 rounded text-xs font-mono border transition-colors ${
                tab === key
                  ? 'bg-cyan-600/20 border-cyan-600 text-cyan-300 font-bold'
                  : 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:text-slate-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {tab === 'overview' && overview && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard title="Students" value={overview.total_students} subtitle="Synthetic enrolled records" icon={GraduationCap} color="cyan" />
            <StatCard title="Faculty" value={overview.total_faculty} subtitle="CSE / IT / ECE departments" icon={Users} color="indigo" />
            <StatCard title="IT Personnel" value={overview.total_it_personnel} subtitle="NOC & Network Engineering" icon={Shield} color="amber" />
            <StatCard
              title="Endpoint Coverage"
              value={`${overview.assignment_coverage_pct}%`}
              subtitle={`${overview.assigned_endpoints} / ${overview.total_students} Assigned`}
              icon={Laptop}
              color={overview.validation_valid ? 'emerald' : 'rose'}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
              <h2 className="text-xs font-mono uppercase text-slate-500 dark:text-slate-400 mb-3">Department Distribution</h2>
              <table className="w-full text-xs font-mono text-left">
                <thead className="text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                  <tr>
                    <th className="py-2">Department</th>
                    <th className="py-2 text-right">Students</th>
                    <th className="py-2 text-right">Faculty</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800 text-slate-800 dark:text-slate-200">
                  {['CSE', 'IT', 'ECE'].map((d) => (
                    <tr key={d}>
                      <td className="py-2 font-bold text-cyan-400">{d}</td>
                      <td className="py-2 text-right">{overview.students_by_department?.[d] ?? 0}</td>
                      <td className="py-2 text-right">{overview.faculty_by_department?.[d] ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {validation && (
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-5">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-xs font-mono uppercase text-slate-500 dark:text-slate-400">Inventory Validation Status</h2>
                  <Badge variant={validation.valid ? 'success' : 'danger'}>
                    {validation.valid ? 'VALIDATED' : `${validation.critical_errors} ERRORS`}
                  </Badge>
                </div>
                <div className="space-y-2 text-xs font-mono text-slate-700 dark:text-slate-300">
                  <div className="flex justify-between">
                    <span className="text-slate-500 dark:text-slate-400">Checks Passed:</span>
                    <span className="text-emerald-400 font-bold">{validation.passed_checks} / {validation.total_checks}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500 dark:text-slate-400">Unassigned Students:</span>
                    <span>{overview.unassigned_students}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500 dark:text-slate-400">Invalid Associations:</span>
                    <span>{overview.invalid_associations}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500 dark:text-slate-400">Inventory Health:</span>
                    <Badge variant={overview.inventory_health === 'HEALTHY' ? 'success' : 'warning'}>
                      {overview.inventory_health}
                    </Badge>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {(tab === 'students' || tab === 'assignments') && (
        <div className="flex flex-wrap items-center justify-between gap-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-3">
          <div className="flex items-center space-x-2">
            {tab === 'students' && (
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-500 dark:text-slate-400 absolute left-2.5 top-2.5" />
                <input
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setPage(0); }}
                  placeholder="Search ID or name..."
                  className="pl-8 pr-3 py-1.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded text-xs font-mono text-slate-800 dark:text-slate-200 focus:outline-none focus:border-cyan-600"
                />
              </div>
            )}
            <select
              value={deptFilter}
              onChange={(e) => { setDeptFilter(e.target.value); setPage(0); }}
              className="px-3 py-1.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded text-xs font-mono text-slate-800 dark:text-slate-200"
            >
              <option value="">All Departments</option>
              <option value="CSE">CSE (VLAN 10)</option>
              <option value="IT">IT (VLAN 20)</option>
              <option value="ECE">ECE (VLAN 30)</option>
            </select>
          </div>
          <div className="flex items-center space-x-2 text-xs font-mono text-slate-500 dark:text-slate-400">
            <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0} className="p-1.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded disabled:opacity-40">
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span>Page {page + 1}</span>
            <button onClick={() => setPage((p) => p + 1)} className="p-1.5 bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded">
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {tab === 'students' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
                <tr>
                  <th className="px-3 py-2.5">Student ID</th>
                  <th className="px-3 py-2.5">Name</th>
                  <th className="px-3 py-2.5">Dept</th>
                  <th className="px-3 py-2.5">Yr/Sem</th>
                  <th className="px-3 py-2.5">VLAN</th>
                  <th className="px-3 py-2.5">Device</th>
                  <th className="px-3 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-800 text-slate-800 dark:text-slate-200">
                {students.map((s) => (
                  <tr
                    key={s.id}
                    onClick={() => handleInspectStudent(s.student_id)}
                    className="hover:bg-slate-800/50 cursor-pointer"
                  >
                    <td className="px-3 py-2 font-bold text-cyan-400">{s.student_id}</td>
                    <td className="px-3 py-2">{s.full_name}</td>
                    <td className="px-3 py-2">{s.department}</td>
                    <td className="px-3 py-2">Y{s.academic_year}/S{s.semester}</td>
                    <td className="px-3 py-2">VLAN {s.assigned_vlan}</td>
                    <td className="px-3 py-2 text-emerald-400">{s.assigned_device || 'Unassigned'}</td>
                    <td className="px-3 py-2"><Badge variant="success">{s.enrollment_status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-4 font-mono text-xs h-fit">
            <h3 className="text-slate-500 dark:text-slate-400 uppercase mb-3 border-b border-slate-200 dark:border-slate-800 pb-2">Student Network Assignment</h3>
            {netError && <div className="text-amber-400">{netError}</div>}
            {!selectedStudentNet && !netError && (
              <div className="text-slate-500">Select a student row to inspect their endpoint, switch port, and VLAN mapping.</div>
            )}
            {selectedStudentNet && (
              <div className="space-y-2 text-slate-800 dark:text-slate-200">
                <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">Student:</span><span className="font-bold text-cyan-400">{selectedStudentNet.student_id}</span></div>
                <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">Endpoint:</span><span>{selectedStudentNet.endpoint_hostname}</span></div>
                <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">IPv4 Address:</span><span className="text-cyan-300">{selectedStudentNet.ip_address}</span></div>
                <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">MAC Address:</span><span>{selectedStudentNet.mac_address}</span></div>
                <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">Access Switch:</span><span className="text-emerald-400">{selectedStudentNet.connected_switch}</span></div>
                <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">Switch Port:</span><span>{selectedStudentNet.connected_interface}</span></div>
                <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">VLAN / Dept:</span><span>VLAN {selectedStudentNet.vlan_id} ({selectedStudentNet.department})</span></div>
                <div className="flex justify-between"><span className="text-slate-500 dark:text-slate-400">Status ({selectedStudentNet.status_source}):</span><Badge variant="success">{selectedStudentNet.operational_status}</Badge></div>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'faculty' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="px-4 py-2.5">Faculty ID</th>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Department</th>
                <th className="px-4 py-2.5">Designation</th>
                <th className="px-4 py-2.5">Office</th>
                <th className="px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800 text-slate-800 dark:text-slate-200">
              {faculty.map((f) => (
                <tr key={f.id}>
                  <td className="px-4 py-2.5 font-bold text-cyan-400">{f.faculty_id}</td>
                  <td className="px-4 py-2.5">{f.full_name}</td>
                  <td className="px-4 py-2.5">{f.department}</td>
                  <td className="px-4 py-2.5">{f.designation}</td>
                  <td className="px-4 py-2.5">{f.office_location}</td>
                  <td className="px-4 py-2.5"><Badge variant="success">{f.employment_status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'it' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="px-4 py-2.5">Employee ID</th>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Job Title</th>
                <th className="px-4 py-2.5">Team</th>
                <th className="px-4 py-2.5">Access Classification</th>
                <th className="px-4 py-2.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800 text-slate-800 dark:text-slate-200">
              {itStaff.map((e) => (
                <tr key={e.id}>
                  <td className="px-4 py-2.5 font-bold text-cyan-400">{e.employee_id}</td>
                  <td className="px-4 py-2.5">{e.full_name}</td>
                  <td className="px-4 py-2.5">{e.job_title}</td>
                  <td className="px-4 py-2.5">{e.team}</td>
                  <td className="px-4 py-2.5"><Badge variant="purple">{e.access_classification}</Badge></td>
                  <td className="px-4 py-2.5"><Badge variant="success">{e.employment_status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'assignments' && (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-50 dark:bg-slate-950 text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-800">
              <tr>
                <th className="px-4 py-2.5">Student</th>
                <th className="px-4 py-2.5">Endpoint</th>
                <th className="px-4 py-2.5">IP / MAC</th>
                <th className="px-4 py-2.5">Access Switch</th>
                <th className="px-4 py-2.5">Port</th>
                <th className="px-4 py-2.5">VLAN</th>
                <th className="px-4 py-2.5">Assignment</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800 text-slate-800 dark:text-slate-200">
              {assignments.map((a) => (
                <tr key={a.student_id}>
                  <td className="px-4 py-2.5"><span className="text-cyan-400 font-bold">{a.student_id}</span> ({a.student_name})</td>
                  <td className="px-4 py-2.5">{a.endpoint_hostname || 'N/A'}</td>
                  <td className="px-4 py-2.5">{a.ip_address} <span className="text-slate-500">{a.mac_address}</span></td>
                  <td className="px-4 py-2.5 text-emerald-400">{a.access_switch || 'N/A'}</td>
                  <td className="px-4 py-2.5">{a.switch_interface || 'N/A'}</td>
                  <td className="px-4 py-2.5">VLAN {a.vlan_id}</td>
                  <td className="px-4 py-2.5">
                    <Badge variant={a.assignment_status === 'ASSIGNED' ? 'success' : 'danger'}>
                      {a.assignment_status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
