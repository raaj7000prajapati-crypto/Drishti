import React, { useState, useEffect } from 'react';
import { adminAPI } from '../services/api';
import { PageState } from '../components/ui';
import {
  Users,
  Building2,
  Route,
  Clock,
  Plus,
  Trash2,
  Edit2,
  Check,
  X,
  Sparkles
} from 'lucide-react';

export default function AdminManagement() {
  const [activeTab, setActiveTab] = useState('rules');

  // State
  const [users, setUsers] = useState([]);
  const [bureaus, setBureaus] = useState([]);
  const [rules, setRules] = useState([]);
  const [slaConfigs, setSLAConfigs] = useState([]);
  const [similarityThresholds, setSimilarityThresholds] = useState({
    high_threshold: 0.8,
    medium_threshold: 0.5,
    low_threshold: 0.3,
  });
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');

  // Forms
  const [showAddRuleModal, setShowAddRuleModal] = useState(false);
  const [newRuleKeywords, setNewRuleKeywords] = useState('');
  const [newRuleCategory, setNewRuleCategory] = useState('');
  const [newRuleBureauId, setNewRuleBureauId] = useState('');
  const [newRulePriority, setNewRulePriority] = useState(10);

  const [showAddUserModal, setShowAddUserModal] = useState(false);
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserName, setNewUserName] = useState('');
  const [newUserPhone, setNewUserPhone] = useState('');
  const [newUserRole, setNewUserRole] = useState('OFFICIAL');
  const [newUserBureauId, setNewUserBureauId] = useState('');

  const [editingSLA, setEditingSLA] = useState(null);
  const [slaHoursInput, setSLAHoursInput] = useState('');

  const loadData = async () => {
    setLoading(true);
    setLoadError('');
    try {
      const [uRes, bRes, rRes, sRes, tRes] = await Promise.all([
        adminAPI.getUsers(),
        adminAPI.getBureaus(),
        adminAPI.getRules(),
        adminAPI.getSLA(),
        adminAPI.getSimilarityThresholds(),
      ]);
      setUsers(uRes.data);
      setBureaus(bRes.data);
      setRules(rRes.data);
      setSLAConfigs(sRes.data);
      setSimilarityThresholds(tRes.data);
      if (bRes.data.length > 0) {
        setNewRuleBureauId(bRes.data[0].id);
        setNewUserBureauId(bRes.data[0].id);
      }
    } catch (err) {
      console.error('Error loading admin governance data:', err);
      setLoadError(err.response?.data?.detail || 'Governance settings could not be loaded.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateRule = async (e) => {
    e.preventDefault();
    if (!newRuleKeywords.trim()) return;
    try {
      await adminAPI.createRule({
        keywords: newRuleKeywords,
        category: newRuleCategory || null,
        target_bureau_id: Number(newRuleBureauId),
        priority: Number(newRulePriority),
        is_active: true,
      });
      setShowAddRuleModal(false);
      setNewRuleKeywords('');
      setNewRuleCategory('');
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create routing rule');
    }
  };

  const handleDeleteRule = async (id) => {
    if (!window.confirm('Delete this smart routing rule?')) return;
    try {
      await adminAPI.deleteRule(id);
      loadData();
    } catch (err) {
      alert('Could not delete rule');
    }
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    try {
      await adminAPI.createUser({
        email: newUserEmail,
        password: 'Drishti@2026',
        full_name: newUserName,
        phone: newUserPhone || null,
        role: newUserRole,
        bureau_id: newUserRole === 'OFFICIAL' ? Number(newUserBureauId) : null,
      });
      setShowAddUserModal(false);
      setNewUserEmail('');
      setNewUserName('');
      setNewUserPhone('');
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create user');
    }
  };

  const handleUpdateSLA = async (priority) => {
    try {
      await adminAPI.updateSLA(priority, { max_hours: Number(slaHoursInput) });
      setEditingSLA(null);
      loadData();
    } catch (err) {
      alert('Failed to update SLA configuration');
    }
  };

  const handleUpdateSimilarityThresholds = async (e) => {
    e.preventDefault();
    try {
      await adminAPI.updateSimilarityThresholds({
        high_threshold: Number(similarityThresholds.high_threshold),
        medium_threshold: Number(similarityThresholds.medium_threshold),
        low_threshold: Number(similarityThresholds.low_threshold),
      });
      loadData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update similarity thresholds');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {loading && users.length === 0 && bureaus.length === 0 && (
        <PageState
          type="loading"
          title="Loading governance settings"
          className="min-h-48 rounded-2xl border border-slate-200 bg-white"
        />
      )}
      {loadError && (
        <PageState
          type="error"
          title="Governance settings unavailable"
          description={loadError}
          actionLabel="Retry"
          onAction={loadData}
          className="rounded-2xl border border-slate-200 bg-white"
        />
      )}
      {/* Page Header */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <span className="text-xs font-semibold text-amber-600 uppercase tracking-widest flex items-center gap-1.5">
            <Building2 className="w-4 h-4" /> AICTE System Governance
          </span>
          <h1 className="text-2xl font-extrabold text-slate-900 mt-1">
            Rules, SLAs & User Governance
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Configure keyword-based smart routing rules, manage bureau officials, and configure SLA escalation thresholds.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 gap-2 text-xs font-bold">
        <button
          onClick={() => setActiveTab('rules')}
          className={`px-4 py-2.5 rounded-t-lg transition flex items-center gap-1.5 ${
            activeTab === 'rules'
              ? 'bg-white border-t border-x border-slate-200 text-amber-600 border-b-2 border-b-transparent -mb-[1px]'
              : 'text-slate-500 hover:text-slate-900'
          }`}
        >
          <Route className="w-4 h-4" /> Smart Routing Rules ({rules.length})
        </button>

        <button
          onClick={() => setActiveTab('users')}
          className={`px-4 py-2.5 rounded-t-lg transition flex items-center gap-1.5 ${
            activeTab === 'users'
              ? 'bg-white border-t border-x border-slate-200 text-amber-600 border-b-2 border-b-transparent -mb-[1px]'
              : 'text-slate-500 hover:text-slate-900'
          }`}
        >
          <Users className="w-4 h-4" /> Users & Officials ({users.length})
        </button>

        <button
          onClick={() => setActiveTab('bureaus')}
          className={`px-4 py-2.5 rounded-t-lg transition flex items-center gap-1.5 ${
            activeTab === 'bureaus'
              ? 'bg-white border-t border-x border-slate-200 text-amber-600 border-b-2 border-b-transparent -mb-[1px]'
              : 'text-slate-500 hover:text-slate-900'
          }`}
        >
          <Building2 className="w-4 h-4" /> Bureaus & Cells ({bureaus.length})
        </button>

        <button
          onClick={() => setActiveTab('sla')}
          className={`px-4 py-2.5 rounded-t-lg transition flex items-center gap-1.5 ${
            activeTab === 'sla'
              ? 'bg-white border-t border-x border-slate-200 text-amber-600 border-b-2 border-b-transparent -mb-[1px]'
              : 'text-slate-500 hover:text-slate-900'
          }`}
        >
          <Clock className="w-4 h-4" /> SLA Escalation Configs ({slaConfigs.length})
        </button>
        <button
          onClick={() => setActiveTab('similarity')}
          className={`px-4 py-2.5 rounded-t-lg transition flex items-center gap-1.5 ${
            activeTab === 'similarity'
              ? 'bg-white border-t border-x border-slate-200 text-amber-600 border-b-2 border-b-transparent -mb-[1px]'
              : 'text-slate-500 hover:text-slate-900'
          }`}
        >
          <Sparkles className="w-4 h-4" /> Similarity thresholds
        </button>
      </div>

      {/* Tab 1: Smart Routing Rules */}
      {activeTab === 'rules' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Intelligent Routing Keyword Rules</h2>
              <p className="text-xs text-slate-500">
                Incoming grievances are matched against these rules to automatically route to the right bureau.
              </p>
            </div>
            <button
              onClick={() => setShowAddRuleModal(true)}
              className="px-3.5 py-1.5 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs rounded-lg transition flex items-center gap-1 shadow-sm"
            >
              <Plus className="w-4 h-4" /> Add Routing Rule
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase border-b border-slate-200">
                  <th className="py-3 px-4">Priority</th>
                  <th className="py-3 px-4">Category (Optional)</th>
                  <th className="py-3 px-4">Trigger Keywords</th>
                  <th className="py-3 px-4">Target Bureau</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rules.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-mono font-bold text-amber-600">{r.priority}</td>
                    <td className="py-3 px-4 text-slate-700 font-semibold">{r.category || 'Any Category'}</td>
                    <td className="py-3 px-4 text-slate-800 max-w-md">
                      <div className="flex flex-wrap gap-1">
                        {r.keywords.split(',').map((kw, i) => (
                          <span key={i} className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[11px]">
                            {kw.trim()}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-3 px-4 font-bold text-slate-900">{r.target_bureau_name}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleDeleteRule(r.id)}
                        className="p-1 text-slate-400 hover:text-red-600 rounded transition"
                        title="Delete rule"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 2: Users Management */}
      {activeTab === 'users' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-900">Platform Users & Bureau Officers</h2>
              <p className="text-xs text-slate-500">
                Manage credentials, role assignments, and bureau authorizations.
              </p>
            </div>
            <button
              onClick={() => setShowAddUserModal(true)}
              className="px-3.5 py-1.5 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs rounded-lg transition flex items-center gap-1 shadow-sm"
            >
              <Plus className="w-4 h-4" /> Provision User
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase border-b border-slate-200">
                  <th className="py-3 px-4">Name</th>
                  <th className="py-3 px-4">Email</th>
                  <th className="py-3 px-4">Role</th>
                  <th className="py-3 px-4">Assigned Bureau</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-bold text-slate-900">{u.full_name}</td>
                    <td className="py-3 px-4 text-slate-600 font-mono">{u.email}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-100 text-slate-800">
                        {u.role}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-700">{u.bureau_name || '—'}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${u.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>
                        {u.is_active ? 'Active' : 'Deactivated'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Bureaus */}
      {activeTab === 'bureaus' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
          <h2 className="text-sm font-bold text-slate-900">AICTE Bureaus & Cells Registry</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
            {bureaus.map((b) => (
              <div key={b.id} className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-sm text-slate-900">{b.name}</span>
                  <span className="font-mono text-xs font-black px-2 py-0.5 rounded bg-amber-100 text-amber-900">
                    {b.code}
                  </span>
                </div>
                <p className="text-slate-600 line-clamp-2">{b.description}</p>
                <div className="pt-2 border-t border-slate-200 text-[11px] text-slate-500 flex justify-between">
                  <span>Officials: <strong>{b.official_count}</strong></span>
                  <span>Active Cases: <strong>{b.active_complaints_count}</strong></span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: SLA Configurations */}
      {activeTab === 'sla' && (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
          <h2 className="text-sm font-bold text-slate-900">SLA Thresholds & Escalation Hierarchy</h2>
          <p className="text-xs text-slate-500">
            Complaints exceeding these hours trigger background escalation alerts to Bureau Heads and Admins.
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase border-b border-slate-200">
                  <th className="py-3 px-4">Priority Tier</th>
                  <th className="py-3 px-4">Max Hours Allowed</th>
                  <th className="py-3 px-4">Equivalent Days</th>
                  <th className="py-3 px-4">Escalation Destination</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {slaConfigs.map((sla) => (
                  <tr key={sla.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-bold text-slate-900">{sla.priority}</td>
                    <td className="py-3 px-4 font-mono font-bold text-amber-600">
                      {editingSLA === sla.priority ? (
                        <input
                          type="number"
                          value={slaHoursInput}
                          onChange={(e) => setSLAHoursInput(e.target.value)}
                          className="w-20 p-1 border rounded text-xs"
                        />
                      ) : (
                        `${sla.max_hours} hrs`
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      {(sla.max_hours / 24).toFixed(1)} days
                    </td>
                    <td className="py-3 px-4 text-slate-700">{sla.escalation_level}</td>
                    <td className="py-3 px-4 text-right">
                      {editingSLA === sla.priority ? (
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => handleUpdateSLA(sla.priority)}
                            className="p-1 text-emerald-600 hover:bg-emerald-50 rounded"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => setEditingSLA(null)}
                            className="p-1 text-slate-400 hover:bg-slate-100 rounded"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            setEditingSLA(sla.priority);
                            setSLAHoursInput(String(sla.max_hours));
                          }}
                          className="p-1 text-slate-400 hover:text-amber-600 rounded"
                          title="Edit SLA hours"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'similarity' && (
        <form
          onSubmit={handleUpdateSimilarityThresholds}
          className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4"
        >
          <div>
            <h2 className="text-sm font-bold text-slate-900">Related-case match buckets</h2>
            <p className="text-xs text-slate-500">
              Set the minimum hybrid similarity score for High, Medium, and Low matches.
              Lower-scoring matches are labelled Minimal.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              ['high_threshold', 'High minimum'],
              ['medium_threshold', 'Medium minimum'],
              ['low_threshold', 'Low minimum'],
            ].map(([field, label]) => (
              <label key={field} className="text-xs font-semibold text-slate-700">
                {label}
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  required
                  value={similarityThresholds[field]}
                  onChange={(event) =>
                    setSimilarityThresholds((current) => ({
                      ...current,
                      [field]: event.target.value,
                    }))
                  }
                  className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm"
                  aria-label={label}
                />
              </label>
            ))}
          </div>
          <p className="text-xs text-slate-500">
            Values must be ordered Low &lt; Medium &lt; High. Changes are audit logged.
          </p>
          <button
            type="submit"
            className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs rounded-lg"
          >
            Save similarity thresholds
          </button>
        </form>
      )}

      {/* --- ADD RULE MODAL --- */}
      {showAddRuleModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="font-bold text-sm text-slate-900">Add Smart Routing Keyword Rule</h3>
            <form onSubmit={handleCreateRule} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  Trigger Keywords (Comma-separated) *
                </label>
                <input
                  type="text"
                  required
                  value={newRuleKeywords}
                  onChange={(e) => setNewRuleKeywords(e.target.value)}
                  placeholder="e.g. stipend, gate scholarship, delayed fellowship"
                  className="w-full p-2 border border-slate-300 rounded-lg"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  Category Match (Optional)
                </label>
                <input
                  type="text"
                  value={newRuleCategory}
                  onChange={(e) => setNewRuleCategory(e.target.value)}
                  placeholder="e.g. Student Welfare"
                  className="w-full p-2 border border-slate-300 rounded-lg"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  Target Bureau *
                </label>
                <select
                  value={newRuleBureauId}
                  onChange={(e) => setNewRuleBureauId(e.target.value)}
                  className="w-full p-2 border border-slate-300 rounded-lg bg-white"
                >
                  {bureaus.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name} ({b.code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">
                  Rule Priority Weight (Higher = First Check)
                </label>
                <input
                  type="number"
                  value={newRulePriority}
                  onChange={(e) => setNewRulePriority(e.target.value)}
                  className="w-full p-2 border border-slate-300 rounded-lg"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddRuleModal(false)}
                  className="px-3 py-1.5 text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold rounded-lg"
                >
                  Save Rule
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- ADD USER MODAL --- */}
      {showAddUserModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="font-bold text-sm text-slate-900">Provision Bureau Official / Admin</h3>
            <form onSubmit={handleCreateUser} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Full Name *</label>
                <input
                  type="text"
                  required
                  value={newUserName}
                  onChange={(e) => setNewUserName(e.target.value)}
                  placeholder="e.g. Dr. K. Ramanathan"
                  className="w-full p-2 border border-slate-300 rounded-lg"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Official Email *</label>
                <input
                  type="email"
                  required
                  value={newUserEmail}
                  onChange={(e) => setNewUserEmail(e.target.value)}
                  placeholder="official.name@drishti.aicte.gov.in"
                  className="w-full p-2 border border-slate-300 rounded-lg"
                />
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Role *</label>
                <select
                  value={newUserRole}
                  onChange={(e) => setNewUserRole(e.target.value)}
                  className="w-full p-2 border border-slate-300 rounded-lg bg-white"
                >
                  <option value="OFFICIAL">Bureau Official</option>
                  <option value="ADMIN">Council Administrator</option>
                </select>
              </div>

              {newUserRole === 'OFFICIAL' && (
                <div>
                  <label className="block text-slate-700 font-semibold mb-1">Bureau Allocation *</label>
                  <select
                    value={newUserBureauId}
                    onChange={(e) => setNewUserBureauId(e.target.value)}
                    className="w-full p-2 border border-slate-300 rounded-lg bg-white"
                  >
                    {bureaus.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name} ({b.code})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <p className="text-[11px] text-slate-500 italic">
                Initial password will be set to: <strong>Drishti@2026</strong>
              </p>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddUserModal(false)}
                  className="px-3 py-1.5 text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold rounded-lg"
                >
                  Create User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
