import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { analyticsAPI, adminAPI } from '../services/api';
import { PageState } from '../components/ui';
import {
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,
  XAxis, YAxis, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import {
  BarChart3,
  Filter,
  AlertTriangle,
  Clock,
  Sparkles,
  CheckCircle2,
  FileSpreadsheet,
  FileText,
  ChevronRight
} from 'lucide-react';

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [bureaus, setBureaus] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters
  const [bureauId, setBureauId] = useState('');
  const [priority, setPriority] = useState('All');
  const [status, setStatus] = useState('All');
  const [dateRangeDays, setDateRangeDays] = useState(180);

  const [exportingCSV, setExportingCSV] = useState(false);
  const [exportingPDF, setExportingPDF] = useState(false);

  const fetchBureaus = async () => {
    try {
      const res = await adminAPI.getBureaus();
      setBureaus(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchAnalytics = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await analyticsAPI.getDashboardStats({
        bureau_id: bureauId || undefined,
        priority: priority !== 'All' ? priority : undefined,
        status: status !== 'All' ? status : undefined,
        date_range_days: dateRangeDays,
      });
      setStats(res.data);
    } catch (err) {
      console.error('Error fetching analytics:', err);
      setError(err.response?.data?.detail || 'Dashboard analytics could not be loaded.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBureaus();
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [bureauId, priority, status, dateRangeDays]);

  const handleExportCSV = async () => {
    setExportingCSV(true);
    try {
      const res = await analyticsAPI.exportCSV({
        bureau_id: bureauId || undefined,
        status: status !== 'All' ? status : undefined,
        priority: priority !== 'All' ? priority : undefined,
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `drishti_grievances_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      alert('Could not generate CSV export');
    } finally {
      setExportingCSV(false);
    }
  };

  const handleExportPDF = async () => {
    setExportingPDF(true);
    try {
      const res = await analyticsAPI.exportPDF({
        bureau_id: bureauId || undefined,
        status: status !== 'All' ? status : undefined,
      });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `drishti_aicte_audit_${new Date().toISOString().slice(0, 10)}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      alert('Could not generate PDF report');
    } finally {
      setExportingPDF(false);
    }
  };

  if (loading && !stats) {
    return (
      <PageState
        type="loading"
        title="Loading dashboard"
        description="Aggregating the latest case metrics."
        className="min-h-64"
      />
    );
  }

  if (error && !stats) {
    return (
      <PageState
        type="error"
        title="Dashboard unavailable"
        description={error}
        actionLabel="Retry"
        onAction={fetchAnalytics}
        className="min-h-64"
      />
    );
  }

  const {
    impact_metrics,
    cases_by_department,
    status_distribution,
    timeline_last_6_months,
    similarity_distribution,
    pending_delayed_flags,
  } = stats || {};

  const BUCKET_COLORS = {
    High: '#EF4444',
    Medium: '#F59E0B',
    Low: '#3B82F6',
    Minimal: '#94A3B8',
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Top Header & Export Controls */}
      {error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-4 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-800"
        >
          <span>{error} Showing the last loaded data.</span>
          <button
            type="button"
            onClick={fetchAnalytics}
            className="font-semibold underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600"
          >
            Retry
          </button>
        </div>
      )}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <span className="text-xs font-semibold text-amber-600 uppercase tracking-widest flex items-center gap-1.5">
            <BarChart3 className="w-4 h-4" /> AICTE Central Intelligence
          </span>
          <h1 className="text-2xl font-extrabold text-slate-900 mt-1">
            Analytics & Success Metrics Dashboard
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Real-time quantitative tracking across 6 bureaus, SLA compliance monitoring, and AI similarity metrics.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleExportCSV}
            disabled={exportingCSV}
            className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-lg transition flex items-center gap-1.5 shadow-sm"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
            {exportingCSV ? 'Exporting...' : 'Export CSV'}
          </button>
          <button
            onClick={handleExportPDF}
            disabled={exportingPDF}
            className="px-3.5 py-2 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-slate-950 font-bold text-xs rounded-lg transition flex items-center gap-1.5 shadow-md"
          >
            <FileText className="w-3.5 h-3.5" />
            {exportingPDF ? 'Generating...' : 'Export PDF Report'}
          </button>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center gap-3 text-xs">
        <div className="flex items-center gap-1.5 text-slate-500 font-bold uppercase tracking-wider text-[11px]">
          <Filter className="w-3.5 h-3.5 text-amber-600" /> Filters:
        </div>

        <select
          value={dateRangeDays}
          onChange={(e) => setDateRangeDays(Number(e.target.value))}
          className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-amber-500"
        >
          <option value={30}>Last 30 Days</option>
          <option value={90}>Last 3 Months</option>
          <option value={180}>Last 6 Months</option>
          <option value={365}>Last 1 Year</option>
        </select>

        <select
          value={bureauId}
          onChange={(e) => setBureauId(e.target.value)}
          className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-amber-500"
        >
          <option value="">All Bureaus / Cells</option>
          {bureaus.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name} ({b.code})
            </option>
          ))}
        </select>

        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          className="px-3 py-1.5 rounded-lg border border-slate-300 bg-white font-medium focus:ring-2 focus:ring-amber-500"
        >
          <option value="All">All Priorities</option>
          <option value="Urgent">Urgent</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
        </select>

        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
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
      </div>

      {/* System Impact Metrics KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-blue-600" /> Avg Resolution Time
          </p>
          <p className="text-3xl font-black text-slate-900 mt-2">
            {impact_metrics?.avg_resolution_days ?? '—'} <span className="text-base font-normal text-slate-500">days</span>
          </p>
          <p className="text-[11px] text-emerald-600 font-medium mt-1">
            Target SLA compliance maintained
          </p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5 text-red-600" /> Overdue Ratio
          </p>
          <p className="text-3xl font-black text-red-600 mt-2">
            {impact_metrics?.overdue_percentage || 0}%
          </p>
          <p className="text-[11px] text-slate-500 mt-1">
            {impact_metrics?.total_overdue || 0} cases escalated to Head
          </p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" /> SLA Compliance
          </p>
          <p className="text-3xl font-black text-emerald-600 mt-2">
            {impact_metrics?.sla_compliance_rate ?? 0}%
          </p>
          <p className="text-[11px] text-slate-500 mt-1">
            {impact_metrics?.total_resolved || 0} resolved on schedule
          </p>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-amber-500" /> Duplicates Intercepted
          </p>
          <p className="text-3xl font-black text-amber-600 mt-2">
            {impact_metrics?.duplicates_intercepted || 0}
          </p>
          <p className="text-[11px] text-slate-500 mt-1">
            Cross-bureau duplicated labor avoided
          </p>
        </div>
      </div>

      {/* Main Charts Row 1: Cases by Department & Status Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Cases by Department (Bar Chart) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h2 className="font-bold text-sm text-slate-900">Cases by Department / Bureau</h2>
            <span className="text-[11px] text-slate-500">Live Case Load</span>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cases_by_department || []} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <XAxis dataKey="code" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                  formatter={(val, name, props) => [`${val} Cases`, props.payload.name]}
                  contentStyle={{ backgroundColor: '#0F2537', color: '#fff', borderRadius: '8px', fontSize: '11px' }}
                />
                <Bar dataKey="count" fill="#E87722" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Case Status Distribution (Donut with Total) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h2 className="font-bold text-sm text-slate-900">Case Status Distribution</h2>
            <span className="text-[11px] text-slate-500 font-semibold">
              Total: {impact_metrics?.total_complaints || 0}
            </span>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={status_distribution || []}
                  dataKey="count"
                  nameKey="status"
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={85}
                  paddingAngle={3}
                >
                  {(status_distribution || []).map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(val, name) => [`${val} Cases`, name]}
                  contentStyle={{ backgroundColor: '#0F2537', color: '#fff', borderRadius: '8px', fontSize: '11px' }}
                />
                <Legend iconSize={8} wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Charts Row 2: 6-Month Timeline & User Roles + AI Match Quality */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Timeline of cases last 6 months (2 Cols) */}
        <div className="lg:col-span-2 bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h2 className="font-bold text-sm text-slate-900">Timeline of Cases (Last 6 Months)</h2>
              <p className="text-[11px] text-slate-500">Volume Received vs Resolved per Month</p>
            </div>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={timeline_last_6_months || []} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0F2537', color: '#fff', borderRadius: '8px', fontSize: '11px' }}
                />
                <Legend iconSize={8} wrapperStyle={{ fontSize: '11px' }} />
                <Line type="monotone" dataKey="total_received" stroke="#3B82F6" strokeWidth={2.5} name="Lodged" />
                <Line type="monotone" dataKey="resolved_count" stroke="#10B981" strokeWidth={2.5} name="Resolved" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* AI Match Quality (Similarity Bucket Bars) */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h2 className="font-bold text-sm text-slate-900 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-amber-500" /> AI Match Quality
            </h2>
            <span className="text-[11px] text-slate-500">Similarity Buckets</span>
          </div>

          <div className="space-y-3 pt-2 text-xs">
            {similarity_distribution?.map((item) => (
              <div key={item.bucket} className="space-y-1">
                <div className="flex justify-between items-center text-[11px]">
                  <span className="font-bold text-slate-700">{item.bucket}</span>
                  <span className="text-slate-500 font-mono">
                    {item.count} links ({item.percentage}%)
                  </span>
                </div>
                <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${item.percentage}%`,
                      backgroundColor: BUCKET_COLORS[item.bucket] || '#E87722',
                    }}
                  ></div>
                </div>
              </div>
            ))}
          </div>

          <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 text-[11px] text-slate-600 mt-4 leading-relaxed">
            Semantic correlation engine embeds complaints using SBERT with automatic TF-IDF fallback to cluster cross-bureau sister grievances.
          </div>
        </div>
      </div>

      {/* Pending & Delayed Flags Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="font-bold text-sm text-slate-900 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-600" /> Pending & Delayed Escalation Flags
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              High-priority grievances approaching or exceeding resolution SLA deadlines.
            </p>
          </div>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-red-100 text-red-800 font-bold">
            {pending_delayed_flags?.length || 0} Flagged
          </span>
        </div>

        <div className="overflow-x-auto">
          {pending_delayed_flags?.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              Zero overdue or delayed grievances. Full SLA compliance.
            </div>
          ) : (
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-200">
                  <th className="py-3 px-4">Receipt ID</th>
                  <th className="py-3 px-4">Subject</th>
                  <th className="py-3 px-4">Bureau</th>
                  <th className="py-3 px-4">Officer</th>
                  <th className="py-3 px-4">Priority</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Days Open</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {pending_delayed_flags?.map((flag) => (
                  <tr key={flag.id} className="hover:bg-slate-50 transition">
                    <td className="py-3 px-4 font-mono font-bold text-slate-900">
                      {flag.receipt_id}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-800 max-w-xs truncate">
                      {flag.subject}
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      {flag.bureau_name}
                    </td>
                    <td className="py-3 px-4 text-slate-700">
                      {flag.assigned_official_name}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-orange-50 text-orange-800 font-bold text-[10px]">
                        {flag.priority}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          flag.is_overdue
                            ? 'bg-red-100 text-red-800 animate-pulse'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {flag.is_overdue ? 'OVERDUE' : flag.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-600 font-bold">
                      {flag.days_open}d
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        to={`/cases/${flag.id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-900 hover:bg-amber-500 hover:text-slate-950 text-white font-bold rounded text-[11px] transition shadow-sm"
                      >
                        Escalate <ChevronRight className="w-3 h-3" />
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
