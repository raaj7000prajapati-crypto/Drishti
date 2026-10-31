import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { complaintsAPI } from '../services/api';
import {
  Inbox,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Filter,
  Search,
  ExternalLink,
  ChevronRight,
  ShieldAlert,
  Building2
} from 'lucide-react';

const STATUS_BADGE_CLASSES = {
  New: 'bg-blue-100 text-blue-800 border-blue-200',
  Assigned: 'bg-purple-100 text-purple-800 border-purple-200',
  'In Progress': 'bg-amber-100 text-amber-800 border-amber-200',
  'Awaiting Info': 'bg-cyan-100 text-cyan-800 border-cyan-200 animate-pulse',
  Overdue: 'bg-red-100 text-red-800 border-red-200 font-bold',
  Closed: 'bg-emerald-100 text-emerald-800 border-emerald-200',
};

const PRIORITY_BADGE_CLASSES = {
  Low: 'text-slate-600 bg-slate-100',
  Medium: 'text-blue-700 bg-blue-50',
  High: 'text-orange-700 bg-orange-50 font-semibold',
  Urgent: 'text-red-700 bg-red-50 font-bold',
};

export default function OfficialInbox() {
  const { user } = useAuth();
  const [complaints, setComplaints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [priorityFilter, setPriorityFilter] = useState('All');

  const fetchComplaints = async () => {
    setLoading(true);
    try {
      const res = await complaintsAPI.list({
        search: search || undefined,
        status: statusFilter !== 'All' ? statusFilter : undefined,
        priority: priorityFilter !== 'All' ? priorityFilter : undefined,
      });
      setComplaints(res.data);
    } catch (err) {
      console.error('Error fetching bureau complaints:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchComplaints();
  }, [statusFilter, priorityFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchComplaints();
  };

  // Metrics
  const totalBureauCases = complaints.length;
  const myAssignedCases = complaints.filter((c) => c.assigned_official_id === user?.id).length;
  const overdueCases = complaints.filter((c) => c.is_overdue || c.status === 'Overdue').length;
  const awaitingInfoCases = complaints.filter((c) => c.status === 'Awaiting Info').length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header Banner */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-600 uppercase tracking-widest">
            <Building2 className="w-4 h-4" /> AICTE Official Workstation
          </div>
          <h1 className="text-2xl font-extrabold text-slate-900 mt-1">
            {user?.bureau_name || 'Bureau'} Grievance Queue
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Manage assigned complaints, verify evidence, correlate AI cross-bureau sister cases, and resolve grievances.
          </p>
        </div>

        <div className="text-right bg-slate-50 px-4 py-2.5 rounded-xl border border-slate-200 text-xs">
          <p className="font-bold text-slate-800">{user?.full_name}</p>
          <p className="text-slate-500">{user?.email}</p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Bureau Total Cases
          </p>
          <p className="text-2xl font-black text-slate-900 mt-1">{totalBureauCases}</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-semibold text-purple-600 uppercase tracking-wider flex items-center gap-1">
            <Inbox className="w-3.5 h-3.5" /> Assigned to Me
          </p>
          <p className="text-2xl font-black text-purple-600 mt-1">{myAssignedCases}</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-semibold text-red-600 uppercase tracking-wider flex items-center gap-1">
            <AlertTriangle className="w-3.5 h-3.5" /> Overdue SLA Breaches
          </p>
          <p className="text-2xl font-black text-red-600 mt-1">{overdueCases}</p>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
          <p className="text-xs font-semibold text-cyan-600 uppercase tracking-wider flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" /> Awaiting Clarification
          </p>
          <p className="text-2xl font-black text-cyan-600 mt-1">{awaitingInfoCases}</p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 sm:p-6 border-b border-slate-100 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          <form onSubmit={handleSearchSubmit} className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
            <input
              type="text"
              placeholder="Search receipt ID, college, subject..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500"
            />
          </form>

          <div className="flex flex-wrap items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-amber-500"
            >
              <option value="All">All Statuses</option>
              <option value="New">New</option>
              <option value="Assigned">Assigned</option>
              <option value="In Progress">In Progress</option>
              <option value="Awaiting Info">Awaiting Info</option>
              <option value="Overdue">Overdue</option>
              <option value="Closed">Closed</option>
            </select>

            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-amber-500"
            >
              <option value="All">All Priorities</option>
              <option value="Urgent">Urgent</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>
        </div>

        {/* Bureau Cases Table */}
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-12 text-center text-xs text-slate-500">
              Loading bureau queue...
            </div>
          ) : complaints.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-xs">
              No cases matching filter criteria.
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-200">
                  <th className="py-3 px-4">Receipt ID</th>
                  <th className="py-3 px-4">Institution & Subject</th>
                  <th className="py-3 px-4">Priority</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Assigned Officer</th>
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
                    <td className="py-3.5 px-4 max-w-sm">
                      <p className="font-semibold text-slate-800 truncate">{c.subject}</p>
                      <p className="text-[11px] text-slate-500 truncate">
                        {c.institution_name} • {c.category}
                      </p>
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
                          STATUS_BADGE_CLASSES[c.status] || ''
                        }`}
                      >
                        {c.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-700">
                      {c.assigned_official_name || (
                        <span className="text-slate-400 italic">Unassigned</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-600 text-[11px]">
                      {c.is_overdue ? (
                        <span className="text-red-600 font-bold">OVERDUE</span>
                      ) : c.sla_due_at ? (
                        new Date(c.sla_due_at).toLocaleDateString([], {
                          month: 'short',
                          day: 'numeric',
                        })
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        to={`/cases/${c.id}`}
                        className="inline-flex items-center gap-1 px-3 py-1 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold rounded-md transition text-xs shadow-sm"
                      >
                        Examine <ChevronRight className="w-3 h-3" />
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
