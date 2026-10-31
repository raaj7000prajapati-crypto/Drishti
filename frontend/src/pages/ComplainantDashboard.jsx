import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { complaintsAPI } from '../services/api';
import {
  FileText,
  Clock,
  CheckCircle2,
  AlertCircle,
  PlusCircle,
  Search,
  ExternalLink,
  ChevronRight,
  Filter
} from 'lucide-react';

const STATUS_BADGE_CLASSES = {
  New: 'bg-blue-100 text-blue-800 border-blue-200',
  Assigned: 'bg-purple-100 text-purple-800 border-purple-200',
  'In Progress': 'bg-amber-100 text-amber-800 border-amber-200',
  'Awaiting Info': 'bg-cyan-100 text-cyan-800 border-cyan-200 animate-pulse',
  Overdue: 'bg-red-100 text-red-800 border-red-200',
  Closed: 'bg-emerald-100 text-emerald-800 border-emerald-200',
};

const PRIORITY_BADGE_CLASSES = {
  Low: 'text-slate-600 bg-slate-100',
  Medium: 'text-blue-700 bg-blue-50',
  High: 'text-orange-700 bg-orange-50 font-semibold',
  Urgent: 'text-red-700 bg-red-50 font-bold',
};

export default function ComplainantDashboard() {
  const { user } = useAuth();
  const [complaints, setComplaints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');

  const fetchComplaints = async () => {
    setLoading(true);
    try {
      const res = await complaintsAPI.list({
        search: search || undefined,
        status: statusFilter !== 'All' ? statusFilter : undefined,
      });
      setComplaints(res.data);
    } catch (err) {
      console.error('Error fetching complaints:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchComplaints();
  }, [statusFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchComplaints();
  };

  // Metrics
  const totalCount = complaints.length;
  const inProgressCount = complaints.filter((c) =>
    ['Assigned', 'In Progress'].includes(c.status)
  ).length;
  const awaitingInfoCount = complaints.filter((c) => c.status === 'Awaiting Info').length;
  const closedCount = complaints.filter((c) => c.status === 'Closed').length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div>
          <span className="text-xs font-semibold text-amber-600 uppercase tracking-widest">
            Citizen Grievance Workspace
          </span>
          <h1 className="text-2xl font-extrabold text-slate-900 mt-0.5">
            Welcome, {user?.full_name || 'Complainant'}
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Track real-time investigation stages, answer official clarifications, and view resolution determinations.
          </p>
        </div>
        <Link
          to="/file-complaint"
          className="px-5 py-2.5 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-slate-950 font-bold text-xs rounded-lg shadow-md transition flex items-center gap-1.5 flex-shrink-0"
        >
          <PlusCircle className="w-4 h-4" /> Lodge New Grievance
        </Link>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Total Lodged
          </p>
          <p className="text-2xl font-black text-slate-900 mt-1">{totalCount}</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-semibold text-amber-600 uppercase tracking-wider flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" /> Under Review
          </p>
          <p className="text-2xl font-black text-amber-600 mt-1">{inProgressCount}</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-semibold text-cyan-600 uppercase tracking-wider flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5" /> Action Required
          </p>
          <p className="text-2xl font-black text-cyan-700 mt-1">{awaitingInfoCount}</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-semibold text-emerald-600 uppercase tracking-wider flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" /> Resolved
          </p>
          <p className="text-2xl font-black text-emerald-600 mt-1">{closedCount}</p>
        </div>
      </div>

      {/* Grievances List & Filter Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 sm:p-6 border-b border-slate-100 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <form onSubmit={handleSearchSubmit} className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
            <input
              type="text"
              placeholder="Search by receipt ID, college, subject..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </form>

          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white font-medium focus:outline-none focus:ring-2 focus:ring-amber-500"
            >
              <option value="All">All Statuses</option>
              <option value="New">New</option>
              <option value="Assigned">Assigned</option>
              <option value="In Progress">In Progress</option>
              <option value="Awaiting Info">Awaiting Info</option>
              <option value="Overdue">Overdue</option>
              <option value="Closed">Closed</option>
            </select>
          </div>
        </div>

        {/* Complaints Table */}
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-12 text-center text-xs text-slate-500">
              Loading your grievances...
            </div>
          ) : complaints.length === 0 ? (
            <div className="p-12 text-center space-y-3">
              <FileText className="w-12 h-12 text-slate-300 mx-auto" />
              <p className="text-sm font-semibold text-slate-700">No grievances found</p>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                You haven't lodged any complaints matching this filter.
              </p>
              <Link
                to="/file-complaint"
                className="inline-block mt-2 px-4 py-2 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs rounded-lg transition"
              >
                Lodge Grievance Now
              </Link>
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-200">
                  <th className="py-3 px-4">Receipt ID</th>
                  <th className="py-3 px-4">Institution & Subject</th>
                  <th className="py-3 px-4">Bureau</th>
                  <th className="py-3 px-4">Priority</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">SLA Deadline</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {complaints.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/80 transition">
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-900">
                      {c.receipt_id}
                    </td>
                    <td className="py-3.5 px-4 max-w-xs">
                      <p className="font-semibold text-slate-800 truncate">{c.subject}</p>
                      <p className="text-[11px] text-slate-500 truncate">
                        {c.institution_name} • {c.category}
                      </p>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium text-[11px]">
                        {c.bureau_name || 'AICTE General'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] ${
                          PRIORITY_BADGE_CLASSES[c.priority] || ''
                        }`}
                      >
                        {c.priority}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${
                          STATUS_BADGE_CLASSES[c.status] || 'bg-slate-100 text-slate-800'
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 text-[11px]">
                      {c.sla_due_at
                        ? new Date(c.sla_due_at).toLocaleDateString([], {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })
                        : '—'}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        to={`/cases/${c.id}`}
                        className="inline-flex items-center gap-1 px-3 py-1 bg-slate-100 hover:bg-amber-500 hover:text-slate-950 text-slate-700 font-semibold rounded-md transition text-xs"
                      >
                        Track <ChevronRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
