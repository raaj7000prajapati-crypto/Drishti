import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { complaintsAPI, adminAPI } from '../services/api';
import {
  FileText,
  Search,
  Filter,
  ChevronRight,
  PlusCircle,
  Building2,
  Calendar
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

export default function ComplaintsList() {
  const { user } = useAuth();
  const [complaints, setComplaints] = useState([]);
  const [bureaus, setBureaus] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [bureauId, setBureauId] = useState('');
  const [status, setStatus] = useState('All');
  const [priority, setPriority] = useState('All');
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 25;

  const fetchBureaus = async () => {
    try {
      const res = await adminAPI.getBureaus();
      setBureaus(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchComplaints = async () => {
    setLoading(true);
    try {
      const res = await complaintsAPI.list({
        search: search || undefined,
        bureau_id: bureauId || undefined,
        status: status !== 'All' ? status : undefined,
        priority: priority !== 'All' ? priority : undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setComplaints(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBureaus();
  }, []);

  useEffect(() => {
    fetchComplaints();
  }, [bureauId, status, priority, page]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(0);
    fetchComplaints();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <span className="text-xs font-semibold text-amber-600 uppercase tracking-widest flex items-center gap-1.5">
            <FileText className="w-4 h-4" /> AICTE Central Grievance Registry
          </span>
          <h1 className="text-2xl font-extrabold text-slate-900 mt-1">
            All Institution Grievances
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Consolidated cross-bureau registry with live investigation statuses, assigned officials, and SLA tracking.
          </p>
        </div>

        <Link
          to="/file-complaint"
          className="px-4 py-2 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-slate-950 font-bold text-xs rounded-lg shadow-md transition flex items-center gap-1.5"
        >
          <PlusCircle className="w-4 h-4" /> Lodge New Complaint
        </Link>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center gap-3 text-xs">
        <form onSubmit={handleSearchSubmit} className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5 pointer-events-none" />
          <input
            type="text"
            placeholder="Search receipt, college, category..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500"
          />
        </form>

        <div className="flex flex-wrap items-center gap-2">
          {user?.role === 'ADMIN' && (
            <select
              value={bureauId}
              onChange={(e) => {
                setBureauId(e.target.value);
                setPage(0);
              }}
              className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-amber-500"
            >
              <option value="">All Bureaus</option>
              {bureaus.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} ({b.code})
                </option>
              ))}
            </select>
          )}

          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setPage(0);
            }}
            className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-amber-500"
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
            value={priority}
            onChange={(e) => {
              setPriority(e.target.value);
              setPage(0);
            }}
            className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-amber-500"
          >
            <option value="All">All Priorities</option>
            <option value="Urgent">Urgent</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-12 text-center text-xs text-slate-500">
              Loading complaints registry...
            </div>
          ) : complaints.length === 0 ? (
            <div className="p-12 text-center text-xs text-slate-500">
              No grievances found matching the filter criteria.
            </div>
          ) : (
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase border-b border-slate-200">
                  <th className="py-3 px-4">Receipt ID</th>
                  <th className="py-3 px-4">Institution & Subject</th>
                  <th className="py-3 px-4">Bureau</th>
                  <th className="py-3 px-4">Assigned Officer</th>
                  <th className="py-3 px-4">Priority</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">SLA Deadline</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {complaints.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50 transition">
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-900">
                      {c.receipt_id}
                    </td>
                    <td className="py-3.5 px-4 max-w-sm">
                      <p className="font-semibold text-slate-800 truncate">{c.subject}</p>
                      <p className="text-[11px] text-slate-500 truncate">
                        {c.institution_name} • {c.category}
                      </p>
                    </td>
                    <td className="py-3.5 px-4 text-slate-700">
                      {c.bureau_name || 'AICTE General'}
                    </td>
                    <td className="py-3.5 px-4 text-slate-700">
                      {c.assigned_official_name || <span className="text-slate-400 italic">Unassigned</span>}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded text-[11px] ${PRIORITY_BADGE_CLASSES[c.priority] || ''}`}>
                        {c.priority}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${STATUS_BADGE_CLASSES[c.status] || ''}`}>
                        {c.status}
                      </span>
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
                        className="inline-flex items-center gap-1 px-3 py-1 bg-slate-100 hover:bg-amber-500 hover:text-slate-950 text-slate-700 font-semibold rounded-md transition text-xs"
                      >
                        View <ChevronRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination Bar */}
        <div className="p-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          <span>Showing page {page + 1}</span>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-40"
            >
              Previous
            </button>
            <button
              disabled={complaints.length < PAGE_SIZE}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
