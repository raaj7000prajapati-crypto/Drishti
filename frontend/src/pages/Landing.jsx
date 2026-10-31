import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ShieldCheck,
  Search,
  Sparkles,
  ArrowRight,
  Clock,
  GitBranch,
  Building,
  CheckCircle2,
  FileCheck2,
  Layers,
  Lock,
  ChevronRight
} from 'lucide-react';
import { complaintsAPI } from '../services/api';

export default function Landing() {
  const [trackReceipt, setTrackReceipt] = useState('');
  const [trackError, setTrackError] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const navigate = useNavigate();

  const handleTrackSubmit = async (e) => {
    e.preventDefault();
    if (!trackReceipt.trim()) return;
    setIsSearching(true);
    setTrackError('');
    try {
      const res = await complaintsAPI.list({ search: trackReceipt.trim() });
      if (res.data && res.data.length > 0) {
        navigate(`/cases/${res.data[0].id}`);
      } else {
        setTrackError('No grievance found with this receipt ID. Please check the number.');
      }
    } catch (err) {
      setTrackError('Please log in to track full grievance details.');
      navigate(`/login?redirect=${encodeURIComponent(trackReceipt.trim())}`);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-b from-slate-950 via-slate-900 to-slate-900 text-white pt-12 pb-24 px-4 sm:px-6 lg:px-8 border-b border-slate-800">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-amber-500/10 via-transparent to-transparent pointer-events-none"></div>
        <div className="max-w-5xl mx-auto text-center relative z-10 space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-semibold uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5" /> Next-Gen AICTE Grievance Monitoring Platform
          </div>

          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white leading-tight">
            Single-Window Redressal with <br className="hidden sm:block" />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 via-orange-400 to-amber-200">
              AI Cross-Bureau Correlation
            </span>
          </h1>

          <p className="max-w-2xl mx-auto text-base sm:text-lg text-slate-300 font-normal leading-relaxed">
            Drishti centralizes grievances across all AICTE bureaus and cells, eliminates duplicate investigations using semantic text correlation, enforces strict resolution SLAs, and maintains an immutable audit trail.
          </p>

          {/* Quick Track Search Box */}
          <div className="max-w-xl mx-auto mt-8">
            <form onSubmit={handleTrackSubmit} className="relative flex items-center">
              <input
                type="text"
                placeholder="Enter Receipt ID (e.g. DRI-2026-123456)..."
                value={trackReceipt}
                onChange={(e) => setTrackReceipt(e.target.value)}
                className="w-full px-4 py-3.5 pl-11 rounded-lg bg-slate-800/90 border border-slate-700 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500 text-sm shadow-inner"
              />
              <Search className="w-5 h-5 text-slate-400 absolute left-3.5 pointer-events-none" />
              <button
                type="submit"
                disabled={isSearching}
                className="absolute right-2 px-4 py-2 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs rounded-md transition shadow-md flex items-center gap-1.5"
              >
                {isSearching ? 'Checking...' : 'Track'} <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </form>
            {trackError && (
              <p className="text-xs text-red-400 mt-2 text-left">{trackError}</p>
            )}
          </div>

          {/* Action CTAs */}
          <div className="pt-4 flex flex-wrap justify-center gap-3">
            <Link
              to="/file-complaint"
              className="px-6 py-3 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-slate-950 font-bold text-sm rounded-lg shadow-lg shadow-amber-500/20 transition flex items-center gap-2"
            >
              <FileCheck2 className="w-4 h-4" /> Lodge New Grievance
            </Link>
            <Link
              to="/login"
              className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-white font-semibold text-sm rounded-lg border border-slate-700 transition flex items-center gap-2"
            >
              Sign In to Portal <ChevronRight className="w-4 h-4 text-slate-400" />
            </Link>
          </div>
        </div>
      </section>

      {/* Real-time KPI Overview Bar */}
      <section className="bg-white border-b border-slate-200 py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
            <div className="border-r border-slate-100 last:border-none">
              <p className="text-3xl font-extrabold text-slate-900">120+</p>
              <p className="text-xs font-medium text-slate-500 mt-1 uppercase tracking-wider">Indexed Grievances</p>
            </div>
            <div className="border-r border-slate-100 last:border-none">
              <p className="text-3xl font-extrabold text-emerald-600">6</p>
              <p className="text-xs font-medium text-slate-500 mt-1 uppercase tracking-wider">AICTE Bureaus Integrated</p>
            </div>
            <div className="border-r border-slate-100 last:border-none">
              <p className="text-3xl font-extrabold text-amber-600">4.2d</p>
              <p className="text-xs font-medium text-slate-500 mt-1 uppercase tracking-wider">Avg Resolution Time</p>
            </div>
            <div>
              <p className="text-3xl font-extrabold text-blue-600">100%</p>
              <p className="text-xs font-medium text-slate-500 mt-1 uppercase tracking-wider">Immutable Audit Trail</p>
            </div>
          </div>
        </div>
      </section>

      {/* Core 5-Stage Pipeline */}
      <section className="py-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-12">
          <h2 className="text-xs font-bold text-amber-600 uppercase tracking-widest">End-to-End Governance</h2>
          <p className="text-2xl sm:text-3xl font-bold text-slate-900 mt-1">
            The 5-Stage Drishti Resolution Pipeline
          </p>
          <p className="text-sm text-slate-500 mt-2">
            Every grievance moves through a transparent, monitored lifecycle from citizen intake to formal closure.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition">
            <div className="w-10 h-10 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-sm mb-3">
              1
            </div>
            <h3 className="font-bold text-sm text-slate-900 mb-1">Intake & Validation</h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Standardized intake with multi-file evidence upload, duplicate warning checks, and instant receipt generation (DRI-YYYY-XXXXXX).
            </p>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition">
            <div className="w-10 h-10 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center font-bold text-sm mb-3">
              2
            </div>
            <h3 className="font-bold text-sm text-slate-900 mb-1">Smart Auto-Routing</h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Keyword and category rule engine directs complaint to the right bureau and auto-assigns to the least-loaded officer.
            </p>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition">
            <div className="w-10 h-10 rounded-lg bg-purple-100 text-purple-700 flex items-center justify-center font-bold text-sm mb-3">
              3
            </div>
            <h3 className="font-bold text-sm text-slate-900 mb-1">Action & Clarification</h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Official examines evidence, requests citizen clarifications, adds internal notes, and reviews AI-suggested related cases.
            </p>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition">
            <div className="w-10 h-10 rounded-lg bg-red-100 text-red-700 flex items-center justify-center font-bold text-sm mb-3">
              4
            </div>
            <h3 className="font-bold text-sm text-slate-900 mb-1">SLA Monitoring</h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Automated background schedulers track deadlines per priority (1 to 14 days) and auto-escalate overdue cases to bureau heads.
            </p>
          </div>

          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition">
            <div className="w-10 h-10 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-sm mb-3">
              5
            </div>
            <h3 className="font-bold text-sm text-slate-900 mb-1">Resolution & Feedback</h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              Formal determination (Accept/Reject with reason), email notification to citizen, archived read-only record, and 5-star feedback.
            </p>
          </div>
        </div>
      </section>

      {/* AI Correlation Feature Highlight */}
      <section className="bg-slate-900 text-white py-16 border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            <div className="space-y-4">
              <span className="text-xs font-bold text-amber-400 uppercase tracking-widest flex items-center gap-1.5">
                <Sparkles className="w-4 h-4" /> Human-in-the-Loop Intelligence
              </span>
              <h2 className="text-2xl sm:text-3xl font-bold text-white">
                Cross-Bureau Semantic AI Correlation Engine
              </h2>
              <p className="text-sm text-slate-300 leading-relaxed">
                When a student lodges an extortion complaint with Technical Education and a parent lodges a ragging complaint with Student Cell against the same institution, traditional siloed portals miss the correlation.
              </p>
              <p className="text-sm text-slate-300 leading-relaxed">
                Drishti utilizes semantic embeddings (SBERT with automated TF-IDF fallback) to detect related complaints across all 6 bureaus in real time, computes cosine similarity, and presents officials with human-in-the-loop confirmation options.
              </p>
              <div className="pt-2 flex flex-col sm:flex-row gap-3">
                <div className="bg-slate-800/80 p-3 rounded-lg border border-slate-700">
                  <p className="text-xs font-bold text-amber-400">High (≥0.80)</p>
                  <p className="text-[11px] text-slate-400">Immediate duplicate warning & sister case clustering</p>
                </div>
                <div className="bg-slate-800/80 p-3 rounded-lg border border-slate-700">
                  <p className="text-xs font-bold text-purple-400">Medium (0.50 - 0.79)</p>
                  <p className="text-[11px] text-slate-400">Suggested related link with shared keyword reasons</p>
                </div>
              </div>
            </div>

            <div className="bg-slate-950 p-6 rounded-2xl border border-slate-800 shadow-2xl space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                <span className="text-xs font-semibold text-slate-400">AI Suggested Cross-Bureau Link Preview</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30">
                  94% Match Score
                </span>
              </div>
              <div className="space-y-2 text-xs">
                <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                  <p className="text-slate-400 font-medium">Source: Technical Education</p>
                  <p className="text-white font-semibold mt-0.5">
                    DRI-2026-485450: "Extortionate Capitation Fee Demanded for B.Tech CSE Admission"
                  </p>
                </div>
                <div className="p-3 bg-slate-900 rounded-lg border border-slate-800">
                  <p className="text-slate-400 font-medium">Target: Student Cell</p>
                  <p className="text-white font-semibold mt-0.5">
                    DRI-2026-322202: "Threat of Hostel Eviction for Non-Payment of Development Capitation Fee"
                  </p>
                </div>
                <div className="p-2.5 bg-amber-500/10 rounded-lg border border-amber-500/20">
                  <p className="text-[11px] text-amber-300">
                    <strong>Why Matched:</strong> Shared keywords: capitation, extortion, development, fee
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Demo Credentials Box */}
      <section className="py-12 bg-slate-100 border-t border-slate-200">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h3 className="text-lg font-bold text-slate-900 mb-2">Hackathon Evaluator Quick Access</h3>
          <p className="text-xs text-slate-600 mb-6">
            Click any demo role below to test the role-based dashboard, workflows, and permissions.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Link
              to="/login?email=admin@drishti.test"
              className="bg-white p-4 rounded-xl border border-slate-300 shadow-sm hover:border-amber-500 transition text-left"
            >
              <span className="text-xs font-bold px-2 py-0.5 rounded bg-purple-100 text-purple-800 uppercase">
                Administrator
              </span>
              <p className="text-xs font-semibold text-slate-900 mt-2">admin@drishti.test</p>
              <p className="text-[11px] text-slate-500 mt-1">Full access, KPI dashboards, rule engine, audit logs.</p>
            </Link>

            <Link
              to="/login?email=official.he@drishti.test"
              className="bg-white p-4 rounded-xl border border-slate-300 shadow-sm hover:border-amber-500 transition text-left"
            >
              <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800 uppercase">
                Bureau Official
              </span>
              <p className="text-xs font-semibold text-slate-900 mt-2">official.he@drishti.test</p>
              <p className="text-[11px] text-slate-500 mt-1">Review bureau queue, link AI cases, close grievances.</p>
            </Link>

            <Link
              to="/login?email=student@drishti.test"
              className="bg-white p-4 rounded-xl border border-slate-300 shadow-sm hover:border-amber-500 transition text-left"
            >
              <span className="text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 uppercase">
                Citizen / Student
              </span>
              <p className="text-xs font-semibold text-slate-900 mt-2">student@drishti.test</p>
              <p className="text-[11px] text-slate-500 mt-1">File complaint, upload evidence, track lifecycle timeline.</p>
            </Link>
          </div>
          <p className="text-[11px] text-slate-500 mt-3">Universal Demo Password: <strong>Drishti@2026</strong></p>
        </div>
      </section>
    </div>
  );
}
