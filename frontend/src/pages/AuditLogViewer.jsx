import React, { useState, useEffect } from 'react';
import { adminAPI } from '../services/api';
import {
  History,
  ShieldCheck,
  Search,
  Filter,
  Eye,
  X,
  FileCode,
  Lock,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';

export default function AuditLogViewer() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('');
  const [entityFilter, setEntityFilter] = useState('');
  const [selectedLog, setSelectedLog] = useState(null);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 25;

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const res = await adminAPI.getAuditLogs({
        action: actionFilter || undefined,
        entity_type: entityFilter || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setLogs(res.data);
    } catch (err) {
      console.error('Error fetching audit logs:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [page, actionFilter, entityFilter]);

  const parseJSON = (str) => {
    if (!str) return null;
    try {
      return JSON.stringify(JSON.parse(str), null, 2);
    } catch (e) {
      return str;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Page Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-emerald-700 uppercase tracking-widest">
            <ShieldCheck className="w-4 h-4 text-emerald-600" /> Cryptographic Integrity & Legal Compliance
          </div>
          <h1 className="text-2xl font-extrabold text-slate-900 mt-1">
            Immutable Append-Only Audit Trail
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Enforced at the database trigger layer. Records who, what, when, IP address, and before/after states for all actions.
          </p>
        </div>

        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs font-bold text-emerald-800">
          <Lock className="w-3.5 h-3.5 text-emerald-600" />
          <span>UPDATE / DELETE Revoked</span>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center gap-3 text-xs">
        <div className="flex items-center gap-1.5 text-slate-500 font-bold uppercase tracking-wider text-[11px]">
          <Filter className="w-3.5 h-3.5 text-amber-600" /> Search Logs:
        </div>

        <input
          type="text"
          placeholder="Filter by Action (e.g. COMPLAINT_FILED)..."
          value={actionFilter}
          onChange={(e) => {
            setActionFilter(e.target.value);
            setPage(0);
          }}
          className="px-3 py-1.5 rounded-lg border border-slate-300 w-64 focus:ring-2 focus:ring-amber-500"
        />

        <input
          type="text"
          placeholder="Filter by Entity (e.g. Complaint, User)..."
          value={entityFilter}
          onChange={(e) => {
            setEntityFilter(e.target.value);
            setPage(0);
          }}
          className="px-3 py-1.5 rounded-lg border border-slate-300 w-64 focus:ring-2 focus:ring-amber-500"
        />
      </div>

      {/* Audit Logs Table */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-12 text-center text-xs text-slate-500">
              Querying immutable audit log records...
            </div>
          ) : logs.length === 0 ? (
            <div className="p-12 text-center text-xs text-slate-500">
              No audit records match the current filter.
            </div>
          ) : (
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase border-b border-slate-200">
                  <th className="py-3 px-4">Timestamp (UTC)</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Entity</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Client IP</th>
                  <th className="py-3 px-4 text-right">State Diff</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50 transition">
                    <td className="py-3 px-4 text-slate-500 whitespace-nowrap">
                      {new Date(log.created_at).toISOString().replace('T', ' ').slice(0, 19)}
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded text-[11px]">
                        {log.action}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-700">
                      {log.entity_type} {log.entity_id ? `(#${log.entity_id})` : ''}
                    </td>
                    <td className="py-3 px-4 text-slate-800">
                      {log.actor_email || 'System Engine'}
                    </td>
                    <td className="py-3 px-4 text-slate-500">
                      {log.ip_address || '127.0.0.1'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => setSelectedLog(log)}
                        className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded font-sans font-semibold text-[11px] transition"
                      >
                        <Eye className="w-3.5 h-3.5" /> Inspect
                      </button>
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
              disabled={logs.length < PAGE_SIZE}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 bg-slate-100 hover:bg-slate-200 rounded disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Inspection Modal */}
      {selectedLog && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <div>
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-bold">
                  Audit ID: {selectedLog.id}
                </span>
                <h3 className="font-bold text-base text-slate-900 mt-1">
                  Action: {selectedLog.action}
                </h3>
              </div>
              <button
                onClick={() => setSelectedLog(null)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs bg-slate-50 p-3 rounded-xl border border-slate-200">
              <div>
                <p className="text-slate-500">Target Entity:</p>
                <p className="font-bold text-slate-800">{selectedLog.entity_type} ({selectedLog.entity_id})</p>
              </div>
              <div>
                <p className="text-slate-500">Actor Account:</p>
                <p className="font-bold text-slate-800">{selectedLog.actor_email || 'System Automated'}</p>
              </div>
              <div>
                <p className="text-slate-500">Timestamp (UTC):</p>
                <p className="font-mono text-slate-800">{selectedLog.created_at}</p>
              </div>
              <div>
                <p className="text-slate-500">Origin IP:</p>
                <p className="font-mono text-slate-800">{selectedLog.ip_address || '127.0.0.1'}</p>
              </div>
            </div>

            {/* State Diffs */}
            <div className="space-y-3 text-xs">
              <div>
                <p className="font-bold text-slate-700 uppercase tracking-wider text-[11px] mb-1">
                  Before State:
                </p>
                <pre className="p-3 bg-slate-900 text-emerald-400 rounded-xl overflow-x-auto text-[11px] font-mono">
                  {parseJSON(selectedLog.before_state) || 'null (Initial record state)'}
                </pre>
              </div>

              <div>
                <p className="font-bold text-slate-700 uppercase tracking-wider text-[11px] mb-1">
                  After State:
                </p>
                <pre className="p-3 bg-slate-900 text-amber-400 rounded-xl overflow-x-auto text-[11px] font-mono">
                  {parseJSON(selectedLog.after_state) || 'null'}
                </pre>
              </div>
            </div>

            <div className="text-right pt-2">
              <button
                onClick={() => setSelectedLog(null)}
                className="px-4 py-1.5 bg-slate-900 text-white rounded-lg text-xs font-semibold"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
