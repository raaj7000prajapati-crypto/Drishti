import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { complaintsAPI } from '../services/api';
import {
  FileText,
  Upload,
  AlertTriangle,
  CheckCircle2,
  X,
  File,
  ShieldAlert,
  ArrowRight,
  Printer,
  Sparkles
} from 'lucide-react';

const INDIAN_STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
  "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
  "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
  "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
  "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
  "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi"
];

const CATEGORIES = [
  "Admissions & Fees",
  "Student Welfare",
  "Infrastructure & Labs",
  "Faculty & Staff",
  "Institutional Approval",
  "Governance & Administration",
  "Curriculum & Examinations",
  "Others"
];

export default function FileComplaint() {
  const { user, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [institutionName, setInstitutionName] = useState('');
  const [institutionState, setInstitutionState] = useState('Maharashtra');
  const [institutionCity, setInstitutionCity] = useState('');
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [priority, setPriority] = useState('Medium');
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [files, setFiles] = useState([]);
  const [fileError, setFileError] = useState('');

  const [duplicateWarning, setDuplicateWarning] = useState(null);
  const [isCheckingDuplicates, setIsCheckingDuplicates] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(null);
  const [formError, setFormError] = useState('');

  // Debounced duplicate detection
  useEffect(() => {
    if (subject.trim().length < 8 || description.trim().length < 20) {
      setDuplicateWarning(null);
      return;
    }
    const timer = setTimeout(async () => {
      setIsCheckingDuplicates(true);
      try {
        const res = await complaintsAPI.checkDuplicates(subject, description);
        if (res.data.has_potential_duplicate) {
          setDuplicateWarning(res.data.message);
        } else {
          setDuplicateWarning(null);
        }
      } catch (err) {
        // Silently ignore check error
      } finally {
        setIsCheckingDuplicates(false);
      }
    }, 800);

    return () => clearTimeout(timer);
  }, [subject, description]);

  const handleFileChange = (e) => {
    setFileError('');
    const selectedFiles = Array.from(e.target.files);
    const validFiles = [];

    for (const f of selectedFiles) {
      if (f.size > 10 * 1024 * 1024) {
        setFileError(`File "${f.name}" exceeds 10MB limit.`);
        return;
      }
      validFiles.push(f);
    }
    setFiles((prev) => [...prev, ...validFiles]);
  };

  const removeFile = (idx) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isAuthenticated) {
      navigate('/login?redirect=file-complaint');
      return;
    }

    setFormError('');
    setSubmitting(true);

    try {
      const formData = new FormData();
      formData.append('institution_name', institutionName);
      formData.append('institution_state', institutionState);
      formData.append('institution_city', institutionCity);
      formData.append('category', category);
      formData.append('priority', priority);
      formData.append('subject', subject);
      formData.append('description', description);

      files.forEach((file) => {
        formData.append('files', file);
      });

      const res = await complaintsAPI.fileComplaint(formData);
      setSubmitSuccess(res.data);
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Failed to submit grievance. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-10 sm:px-6 lg:px-8">
      {/* Page Header */}
      <div className="mb-8 border-b border-slate-200 pb-5">
        <div className="flex items-center gap-2 text-xs font-semibold text-amber-600 uppercase tracking-widest">
          <ShieldAlert className="w-4 h-4" /> AICTE Centralized Grievance Redressal
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 mt-1">
          Lodge an Institution Grievance
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">
          Provide complete factual details and supporting evidence. Your complaint will be auto-routed to the designated AICTE bureau under strict SLA tracking.
        </p>
      </div>

      {formError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{formError}</span>
        </div>
      )}

      {/* Main Intake Form */}
      <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 sm:p-8 space-y-6">
        {/* Section 1: Institution Details */}
        <div>
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-3 pb-2 border-b border-slate-100 flex items-center gap-2">
            <span className="w-5 h-5 rounded-full bg-slate-900 text-white text-[11px] flex items-center justify-center font-bold">1</span>
            Target Educational Institution
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-3">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Institution / College Name *
              </label>
              <input
                type="text"
                required
                value={institutionName}
                onChange={(e) => setInstitutionName(e.target.value)}
                placeholder="e.g. Apex Institute of Technology & Engineering"
                className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                State / UT *
              </label>
              <select
                value={institutionState}
                onChange={(e) => setInstitutionState(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500 bg-white"
              >
                {INDIAN_STATES.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                City / District *
              </label>
              <input
                type="text"
                required
                value={institutionCity}
                onChange={(e) => setInstitutionCity(e.target.value)}
                placeholder="e.g. Pune"
                className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Grievance Details */}
        <div>
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-3 pb-2 border-b border-slate-100 flex items-center gap-2">
            <span className="w-5 h-5 rounded-full bg-slate-900 text-white text-[11px] flex items-center justify-center font-bold">2</span>
            Grievance Particulars
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Grievance Category *
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500 bg-white"
              >
                {CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Urgency Priority *
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500 bg-white font-medium"
              >
                <option value="Low">Low (Standard review • 14 days SLA)</option>
                <option value="Medium">Medium (Regular grievance • 7 days SLA)</option>
                <option value="High">High (Serious grievance • 3 days SLA)</option>
                <option value="Urgent">Urgent (Immediate threat / Ragging • 24 hours SLA)</option>
              </select>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Grievance Subject / Headline *
              </label>
              <input
                type="text"
                required
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Concise summary of the grievance issue"
                className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Comprehensive Description of Facts & Violation *
              </label>
              <textarea
                required
                rows={5}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Detail the complete chronological account of events, names of officials/departments involved, dates, and AICTE regulations violated..."
                className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-500 leading-relaxed"
              ></textarea>
            </div>
          </div>

          {/* AI Intake Duplicate Warning Banner */}
          {duplicateWarning && (
            <div className="mt-3 p-3.5 bg-amber-50 border border-amber-300 rounded-xl flex items-start gap-3 text-xs text-amber-900 animate-fadeIn">
              <Sparkles className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-amber-950 flex items-center gap-1.5">
                  AI Correlation Notice
                </p>
                <p className="mt-0.5 text-amber-800 leading-relaxed">
                  {duplicateWarning}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Section 3: Evidence Upload */}
        <div>
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-3 pb-2 border-b border-slate-100 flex items-center gap-2">
            <span className="w-5 h-5 rounded-full bg-slate-900 text-white text-[11px] flex items-center justify-center font-bold">3</span>
            Supporting Evidence Documents (Optional)
          </h2>
          <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 text-center hover:border-amber-500 transition bg-slate-50">
            <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
            <p className="text-xs font-semibold text-slate-700">
              Drag & drop files here, or <span className="text-amber-600 underline">browse</span>
            </p>
            <p className="text-[11px] text-slate-400 mt-1">
              Permitted formats: PDF, PNG, JPG, DOCX, TXT (Max 10MB per file)
            </p>
            <input
              type="file"
              multiple
              onChange={handleFileChange}
              accept=".pdf,.png,.jpg,.jpeg,.docx,.txt"
              className="hidden"
              id="file-upload-input"
            />
            <label
              htmlFor="file-upload-input"
              className="inline-block mt-3 px-4 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-md shadow-sm cursor-pointer transition"
            >
              Select Evidence Files
            </label>
          </div>

          {fileError && <p className="text-xs text-red-500 mt-2">{fileError}</p>}

          {/* Selected File List */}
          {files.length > 0 && (
            <div className="mt-3 space-y-1.5">
              {files.map((file, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between px-3 py-2 bg-slate-100 rounded-lg text-xs"
                >
                  <div className="flex items-center gap-2 truncate">
                    <File className="w-4 h-4 text-slate-500 flex-shrink-0" />
                    <span className="font-medium text-slate-800 truncate">{file.name}</span>
                    <span className="text-slate-400 text-[10px]">
                      ({(file.size / 1024).toFixed(1)} KB)
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeFile(idx)}
                    className="p-1 text-slate-400 hover:text-red-500 rounded"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Submit Button */}
        <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
          <p className="text-[11px] text-slate-500">
            By lodging this complaint, you declare under penalty of perjury that the facts stated are true.
          </p>
          <button
            type="submit"
            disabled={submitting}
            className="px-6 py-2.5 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-slate-950 font-bold text-sm rounded-lg shadow-md transition flex items-center gap-2 disabled:opacity-50"
          >
            {submitting ? 'Submitting...' : 'Lodge Grievance'} <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </form>

      {/* Submission Success Modal */}
      {submitSuccess && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fadeIn">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 sm:p-8 shadow-2xl border border-slate-200 text-center space-y-5">
            <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto shadow-inner">
              <CheckCircle2 className="w-10 h-10" />
            </div>

            <div>
              <h3 className="text-xl font-extrabold text-slate-900">
                Grievance Registered Successfully!
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                Your complaint has been acknowledged by AICTE Drishti.
              </p>
            </div>

            {/* Receipt Box */}
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-left space-y-2 text-xs">
              <div className="flex justify-between items-center pb-2 border-b border-slate-200">
                <span className="font-semibold text-slate-500">Receipt ID:</span>
                <span className="font-mono text-base font-bold text-amber-600">
                  {submitSuccess.receipt_id}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500">Allocated Bureau:</span>
                <span className="font-semibold text-slate-800">
                  {submitSuccess.bureau_name || 'AICTE Cell'}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500">Current Status:</span>
                <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-800 font-bold">
                  {submitSuccess.status}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500">SLA Resolution Target:</span>
                <span className="font-semibold text-slate-800">
                  {submitSuccess.sla_due_at
                    ? new Date(submitSuccess.sla_due_at).toLocaleDateString([], {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                      })
                    : 'Standard SLA'}
                </span>
              </div>
            </div>

            <p className="text-[11px] text-slate-400">
              An acknowledgement email with receipt details has been dispatched to your email address.
            </p>

            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={() => window.print()}
                className="flex-1 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition"
              >
                <Printer className="w-3.5 h-3.5" /> Print Receipt
              </button>
              <button
                onClick={() => navigate(`/cases/${submitSuccess.id}`)}
                className="flex-1 py-2 bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold rounded-lg transition"
              >
                View Live Case & Timeline
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
