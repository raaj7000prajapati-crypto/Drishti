import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { complaintsAPI, officialsAPI } from '../services/api';
import CaseTimeline from '../components/CaseTimeline';
import { PageState, StatusBadge } from '../components/ui';
import {
  FileText,
  CheckCircle2,
  Upload,
  MessageSquare,
  Sparkles,
  ThumbsUp,
  ThumbsDown,
  Lock,
  Download,
  Send,
  Star,
  FileCheck2,
  ArrowLeft
} from 'lucide-react';

const BUCKET_COLORS = {
  High: 'bg-red-100 text-red-800 border-red-200',
  Medium: 'bg-amber-100 text-amber-800 border-amber-200',
  Low: 'bg-blue-100 text-blue-800 border-blue-200',
  Minimal: 'bg-slate-100 text-slate-800 border-slate-200',
};

export default function ComplaintDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [complaint, setComplaint] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Complainant responses
  const [infoResponse, setInfoResponse] = useState('');
  const [submittingInfoResp, setSubmittingInfoResp] = useState(false);

  // Complainant feedback
  const [feedbackRating, setFeedbackRating] = useState(5);
  const [feedbackComments, setFeedbackComments] = useState('');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);

  // Official Actions Modals / Forms
  const [showStatusModal, setShowStatusModal] = useState(false);
  const [newStatus, setNewStatus] = useState('');
  const [statusComment, setStatusComment] = useState('');

  const [showRequestInfoModal, setShowRequestInfoModal] = useState(false);
  const [infoQuestion, setInfoQuestion] = useState('');

  const [showDeterminationModal, setShowDeterminationModal] = useState(false);
  const [determinationType, setDeterminationType] = useState('Accepted');
  const [determinationReason, setDeterminationReason] = useState('');

  const [annotationNote, setAnnotationNote] = useState('');
  const [isInternalAnnotation, setIsInternalAnnotation] = useState(true);
  const [annotationFile, setAnnotationFile] = useState(null);
  const [submittingAnnotation, setSubmittingAnnotation] = useState(false);

  const fetchComplaint = async () => {
    setError('');
    try {
      const res = await complaintsAPI.get(id);
      setComplaint(res.data);
      setNewStatus(res.data.status);
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not load grievance record.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchComplaint();
  }, [id]);

  // Handlers for Complainant
  const handleSendInfoResponse = async (requestId) => {
    if (!infoResponse.trim()) return;
    setSubmittingInfoResp(true);
    try {
      await complaintsAPI.respondInfo(id, { response: infoResponse }, requestId);
      setInfoResponse('');
      fetchComplaint();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to submit response');
    } finally {
      setSubmittingInfoResp(false);
    }
  };

  const handleFeedbackSubmit = async (e) => {
    e.preventDefault();
    setSubmittingFeedback(true);
    try {
      await complaintsAPI.submitFeedback(id, {
        rating: feedbackRating,
        comments: feedbackComments,
      });
      fetchComplaint();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to submit feedback');
    } finally {
      setSubmittingFeedback(false);
    }
  };

  // Handlers for Officials
  const handleUpdateStatus = async () => {
    try {
      await officialsAPI.updateStatus(id, {
        status: newStatus,
        comment: statusComment,
      });
      setShowStatusModal(false);
      fetchComplaint();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update status');
    }
  };

  const handleRequestInfo = async () => {
    if (!infoQuestion.trim()) return;
    try {
      await officialsAPI.requestInfo(id, { question: infoQuestion });
      setInfoQuestion('');
      setShowRequestInfoModal(false);
      fetchComplaint();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to request clarification');
    }
  };

  const handleAddAnnotation = async (e) => {
    e.preventDefault();
    if (!annotationNote.trim()) return;
    setSubmittingAnnotation(true);
    try {
      const formData = new FormData();
      formData.append('note', annotationNote);
      formData.append('is_internal', isInternalAnnotation);
      if (annotationFile) {
        formData.append('file', annotationFile);
      }
      await officialsAPI.addAnnotation(id, formData);
      setAnnotationNote('');
      setAnnotationFile(null);
      fetchComplaint();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to add note');
    } finally {
      setSubmittingAnnotation(false);
    }
  };

  const handleProposeDetermination = async () => {
    if (!determinationReason.trim()) return;
    try {
      await officialsAPI.proposeDetermination(id, {
        determination: determinationType,
        reason: determinationReason,
      });
      setShowDeterminationModal(false);
      fetchComplaint();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to propose determination');
    }
  };

  const handleDecideLink = async (linkId, decision) => {
    try {
      await officialsAPI.decideLink(linkId, decision);
      fetchComplaint();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to record decision');
    }
  };

  const downloadFile = async (request, filename) => {
    try {
      const response = await request();
      const objectUrl = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch (err) {
      alert(err.response?.data?.detail || 'Could not download the attachment.');
    }
  };

  if (loading) {
    return (
      <PageState
        type="loading"
        title="Loading case details"
        description="Retrieving the case record, timeline, and related-case information."
        className="min-h-64"
      />
    );
  }

  if (error || !complaint) {
    return (
      <PageState
        type="error"
        title={error || 'Grievance not found'}
        description="Check the case link and try loading the record again."
        actionLabel="Retry"
        onAction={fetchComplaint}
        className="min-h-64"
      />
    );
  }

  const isOfficialOrAdmin = ['OFFICIAL', 'ADMIN'].includes(user?.role);
  const isComplainant = user?.role === 'COMPLAINANT' && user?.id === complaint.complainant_id;
  const isClosed = complaint.status === 'Closed';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
      {/* Back Button */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => window.history.back()}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Dashboard
        </button>

        {isClosed && (
          <span className="inline-flex items-center gap-1.5 text-xs px-3 py-1 bg-slate-100 text-slate-600 rounded-full font-medium border border-slate-200">
            <Lock className="w-3.5 h-3.5" /> Archived Case (Read-Only)
          </span>
        )}
      </div>

      {/* Case Header Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-lg font-black text-amber-600">
                {complaint.receipt_id}
              </span>
              <StatusBadge status={complaint.status} />
              {complaint.is_overdue && (
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-red-600 text-white animate-pulse">
                  SLA OVERDUE
                </span>
              )}
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900 mt-2">
              {complaint.subject}
            </h1>
          </div>

          {/* Official Quick Action Buttons */}
          {isOfficialOrAdmin && !isClosed && (
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setShowStatusModal(true)}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-lg transition"
              >
                Update Status
              </button>
              <button
                onClick={() => setShowRequestInfoModal(true)}
                className="px-3 py-1.5 bg-cyan-50 hover:bg-cyan-100 text-cyan-800 font-semibold text-xs rounded-lg transition border border-cyan-200"
              >
                Request Info
              </button>
              <button
                onClick={() => setShowDeterminationModal(true)}
                className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg transition shadow-sm"
              >
                Close & Determine
              </button>
            </div>
          )}
        </div>

        {/* Institution & Metadata Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs pt-1">
          <div>
            <p className="text-slate-400 font-medium">Institution</p>
            <p className="font-bold text-slate-800 mt-0.5">{complaint.institution_name}</p>
            <p className="text-slate-500 text-[11px]">{complaint.institution_city}, {complaint.institution_state}</p>
          </div>

          <div>
            <p className="text-slate-400 font-medium">Category & Priority</p>
            <p className="font-bold text-slate-800 mt-0.5">{complaint.category}</p>
            <p className="text-slate-500 text-[11px]">Priority: {complaint.priority}</p>
          </div>

          <div>
            <p className="text-slate-400 font-medium">Allocated Bureau</p>
            <p className="font-bold text-slate-800 mt-0.5">{complaint.bureau_name || 'AICTE General'}</p>
            <p className="text-slate-500 text-[11px]">
              Officer: {complaint.assigned_official_name || 'Unassigned'}
            </p>
          </div>

          <div>
            <p className="text-slate-400 font-medium">SLA Resolution Target</p>
            <p className="font-bold text-slate-800 mt-0.5">
              {complaint.sla_due_at
                ? new Date(complaint.sla_due_at).toLocaleDateString([], {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric',
                  })
                : 'Standard'}
            </p>
            <p className="text-slate-500 text-[11px]">
              Lodged: {new Date(complaint.created_at).toLocaleDateString()}
            </p>
          </div>
        </div>

        {/* Full Description */}
        <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 text-xs text-slate-800 leading-relaxed whitespace-pre-wrap">
          <p className="font-bold text-slate-600 mb-1 uppercase tracking-wider text-[10px]">
            Grievance Description:
          </p>
          {complaint.description}
        </div>

        {/* Evidence Attachments */}
        {complaint.attachments && complaint.attachments.length > 0 && (
          <div className="pt-2">
            <p className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
              Attached Evidence ({complaint.attachments.length})
            </p>
            <div className="flex flex-wrap gap-2">
              {complaint.attachments.map((att) => (
                <button
                  key={att.id}
                  type="button"
                  onClick={() => downloadFile(
                    () => complaintsAPI.downloadAttachment(complaint.id, att.id),
                    att.file_name
                  )}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 hover:border-amber-500 rounded-lg text-xs font-medium text-slate-700 hover:text-amber-700 transition shadow-sm"
                >
                  <FileText className="w-3.5 h-3.5 text-slate-400" />
                  <span className="truncate max-w-xs">{att.file_name}</span>
                  <Download className="w-3 h-3 text-slate-400 ml-1" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Determination Alert (If closed) */}
      {isClosed && complaint.determination !== 'None' && (
        <div className="bg-emerald-50 border border-emerald-300 rounded-2xl p-6 text-xs text-emerald-950 space-y-2 shadow-sm">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            <h3 className="font-extrabold text-sm text-emerald-900">
              Official Determination: {complaint.determination}
            </h3>
          </div>
          <p className="text-emerald-800 leading-relaxed pl-7">
            {complaint.determination_reason}
          </p>
          {complaint.closed_at && (
            <p className="text-[11px] text-emerald-700 pl-7">
              Closed on: {new Date(complaint.closed_at).toLocaleDateString([], { dateStyle: 'full' })}
            </p>
          )}
        </div>
      )}

      {/* Main Workspace Grid: Timeline (Left) & Actions/AI Panels (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column (2 Cols): Visual Timeline */}
        <div className="lg:col-span-2 space-y-6">
          <CaseTimeline events={complaint.events} />

          {/* Citizen Clarifications Section */}
          {complaint.information_requests && complaint.information_requests.length > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-4">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-cyan-600" /> Official Clarification Requests
              </h3>

              <div className="space-y-4 text-xs">
                {complaint.information_requests.map((ir) => (
                  <div key={ir.id} className="p-4 bg-cyan-50/50 rounded-xl border border-cyan-200 space-y-3">
                    <div>
                      <p className="font-bold text-cyan-950 flex items-center justify-between">
                        <span>Question from {ir.official_name}:</span>
                        <span className="text-[10px] text-cyan-700 font-normal">
                          {new Date(ir.requested_at).toLocaleDateString()}
                        </span>
                      </p>
                      <p className="mt-1 text-slate-800">{ir.question}</p>
                    </div>

                    {ir.status === 'RESPONDED' ? (
                      <div className="bg-white p-3 rounded-lg border border-cyan-100">
                        <p className="font-semibold text-emerald-700 text-[11px]">
                          Complainant Response (Submitted {new Date(ir.responded_at).toLocaleDateString()}):
                        </p>
                        <p className="mt-0.5 text-slate-700">{ir.complainant_response}</p>
                      </div>
                    ) : isComplainant ? (
                      <div className="space-y-2 pt-2 border-t border-cyan-200">
                        <textarea
                          rows={2}
                          placeholder="Type your response to the official's question..."
                          value={infoResponse}
                          onChange={(e) => setInfoResponse(e.target.value)}
                          className="w-full p-2 bg-white rounded-lg border border-cyan-300 text-xs focus:ring-2 focus:ring-cyan-500"
                        ></textarea>
                        <button
                          onClick={() => handleSendInfoResponse(ir.id)}
                          disabled={submittingInfoResp}
                          className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-700 text-white font-bold rounded-md shadow-sm transition flex items-center gap-1.5"
                        >
                          <Send className="w-3 h-3" /> Submit Response
                        </button>
                      </div>
                    ) : (
                      <span className="text-[11px] text-amber-700 font-semibold">
                        Awaiting response from complainant...
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Citizen Post-Closure Feedback Card */}
          {isClosed && isComplainant && !complaint.feedback && (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-3">
              <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                Citizen Satisfaction Feedback
              </h3>
              <p className="text-xs text-slate-500">
                Please rate your satisfaction with the AICTE grievance resolution process.
              </p>
              <form onSubmit={handleFeedbackSubmit} className="space-y-3">
                <div className="flex items-center gap-2">
                  {[1, 2, 3, 4, 5].map((star) => (
                    <button
                      key={star}
                      type="button"
                      onClick={() => setFeedbackRating(star)}
                      className="p-1 hover:scale-110 transition"
                    >
                      <Star
                        className={`w-6 h-6 ${
                          star <= feedbackRating
                            ? 'text-amber-400 fill-amber-400'
                            : 'text-slate-300'
                        }`}
                      />
                    </button>
                  ))}
                  <span className="text-xs font-bold text-slate-700 ml-2">
                    {feedbackRating} of 5 Stars
                  </span>
                </div>
                <textarea
                  rows={2}
                  placeholder="Additional comments or observations regarding the resolution..."
                  value={feedbackComments}
                  onChange={(e) => setFeedbackComments(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-slate-300 text-xs focus:ring-2 focus:ring-amber-500"
                ></textarea>
                <button
                  type="submit"
                  disabled={submittingFeedback}
                  className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs rounded-lg shadow transition"
                >
                  Submit Feedback
                </button>
              </form>
            </div>
          )}

          {complaint.feedback && (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-2">
              <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Complainant Feedback
              </h3>
              <div className="flex items-center gap-1">
                {[1, 2, 3, 4, 5].map((star) => (
                  <Star
                    key={star}
                    className={`w-4 h-4 ${
                      star <= complaint.feedback.rating
                        ? 'text-amber-400 fill-amber-400'
                        : 'text-slate-200'
                    }`}
                  />
                ))}
                <span className="text-xs font-bold text-slate-800 ml-2">
                  {complaint.feedback.rating}/5
                </span>
              </div>
              {complaint.feedback.comments && (
                <p className="text-xs text-slate-600 italic">
                  "{complaint.feedback.comments}"
                </p>
              )}
            </div>
          )}
        </div>

        {/* Right Column (1 Col): AI Correlation & Official Workspace */}
        <div className="space-y-6">
          {/* AI Suggested Related Cases Panel */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-500" /> AI Related Cases
              </h3>
              <span className="text-[11px] px-2 py-0.5 rounded bg-amber-50 text-amber-800 font-semibold border border-amber-200">
                {complaint.suggested_links?.length || 0} links
              </span>
            </div>

            {complaint.suggested_links?.length === 0 ? (
              <p className="text-xs text-slate-500 text-center py-4">
                No cross-bureau correlations detected above threshold.
              </p>
            ) : (
              <div className="space-y-3">
                {complaint.suggested_links?.map((link) => (
                  <div
                    key={link.id}
                    className={`p-3 rounded-xl border transition ${
                      link.status === 'CONFIRMED'
                        ? 'bg-emerald-50/70 border-emerald-300'
                        : link.status === 'REJECTED'
                        ? 'bg-slate-50 border-slate-200 opacity-60'
                        : 'bg-amber-50/50 border-amber-200'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs font-bold text-slate-800">
                        {link.target_receipt_id}
                      </span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                          BUCKET_COLORS[link.similarity_bucket] || ''
                        }`}
                      >
                        {Math.round(link.similarity_score * 100)}% Match
                      </span>
                    </div>

                    <p className="text-xs font-semibold text-slate-900 truncate">
                      {link.target_subject}
                    </p>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Bureau: <strong>{link.target_bureau_name}</strong>
                    </p>

                    <div
                      className="text-[11px] text-amber-900 mt-2 bg-white/70 p-2 rounded space-y-1"
                      aria-label="Why these cases matched"
                    >
                      <strong>Why matched</strong>
                      <p>
                        {link.similarity_bucket} match · {Math.round(link.similarity_score * 100)}% combined score
                      </p>
                      {link.shared_keywords && <p>Shared keywords: {link.shared_keywords}</p>}
                      {Object.keys(link.shared_metadata || {}).length > 0 && (
                        <p>
                          Shared details: {Object.entries(link.shared_metadata)
                            .map(([field, value]) => `${field}: ${value}`)
                            .join(', ')}
                        </p>
                      )}
                    </div>

                    {/* Human-in-the-Loop Decisions */}
                    {isOfficialOrAdmin && link.status === 'SUGGESTED' && (
                      <div className="flex items-center justify-end gap-2 mt-2 pt-2 border-t border-slate-200">
                        <button
                          onClick={() => handleDecideLink(link.id, 'REJECTED')}
                          className="px-2 py-1 bg-white hover:bg-red-50 text-red-600 rounded text-[11px] font-semibold border border-red-200 flex items-center gap-1"
                        >
                          <ThumbsDown className="w-3 h-3" /> Reject
                        </button>
                        <button
                          onClick={() => handleDecideLink(link.id, 'CONFIRMED')}
                          className="px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[11px] font-bold flex items-center gap-1 shadow-sm"
                        >
                          <ThumbsUp className="w-3 h-3" /> Confirm Link
                        </button>
                      </div>
                    )}

                    {link.status !== 'SUGGESTED' && (
                      <div className="mt-2 text-right">
                        <span
                          className={`text-[10px] font-bold uppercase tracking-wider ${
                            link.status === 'CONFIRMED'
                              ? 'text-emerald-700'
                              : 'text-slate-500 line-through'
                          }`}
                        >
                          Decision: {link.status}
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Official Annotations Panel */}
          {isOfficialOrAdmin && (
            <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5 space-y-4">
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                <FileCheck2 className="w-3.5 h-3.5 text-blue-600" /> Case Notes & Documents
              </h3>

              {/* Add Note Form */}
              <form onSubmit={handleAddAnnotation} className="space-y-2 text-xs">
                <textarea
                  rows={2}
                  required
                  placeholder="Record an official note or investigation finding..."
                  value={annotationNote}
                  onChange={(e) => setAnnotationNote(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-slate-300 focus:ring-2 focus:ring-amber-500"
                ></textarea>

                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-1.5 text-slate-600 text-[11px] cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isInternalAnnotation}
                      onChange={(e) => setIsInternalAnnotation(e.target.checked)}
                      className="rounded text-amber-600"
                    />
                    Internal Bureau Only
                  </label>
                  <label className="text-amber-600 hover:text-amber-700 text-[11px] font-semibold cursor-pointer flex items-center gap-1">
                    <Upload className="w-3 h-3" /> Attach File
                    <input
                      type="file"
                      onChange={(e) => setAnnotationFile(e.target.files[0])}
                      className="hidden"
                    />
                  </label>
                </div>
                {annotationFile && (
                  <p className="text-[10px] text-slate-500 truncate">
                    Attached: {annotationFile.name}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={submittingAnnotation}
                  className="w-full py-1.5 bg-slate-800 hover:bg-slate-900 text-white font-semibold rounded-lg transition"
                >
                  {submittingAnnotation ? 'Saving Note...' : 'Add Case Note'}
                </button>
              </form>

              {/* Notes List */}
              <div className="space-y-2 text-xs pt-2 divide-y divide-slate-100 max-h-64 overflow-y-auto">
                {complaint.annotations?.map((an) => (
                  <div key={an.id} className="pt-2">
                    <div className="flex justify-between items-center text-[10px] text-slate-400">
                      <span className="font-semibold text-slate-700">{an.author_name}</span>
                      <span>{new Date(an.created_at).toLocaleDateString()}</span>
                    </div>
                    <p className="text-slate-800 mt-1">{an.note}</p>
                    {an.has_attachment && (
                      <button
                        type="button"
                        onClick={() => downloadFile(
                          () => complaintsAPI.downloadAnnotationAttachment(complaint.id, an.id),
                          an.attachment_name || 'attachment'
                        )}
                        className="text-amber-600 underline text-[10px] block mt-1"
                      >
                        Download: {an.attachment_name}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* --- MODALS FOR OFFICIALS --- */}

      {/* Status Transition Modal */}
      {showStatusModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl space-y-4">
            <h3 className="font-bold text-sm text-slate-900">Update Case Status</h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-600 mb-1">New Status:</label>
                <select
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                  className="w-full p-2 border border-slate-300 rounded-lg bg-white"
                >
                  <option value="New">New</option>
                  <option value="Assigned">Assigned</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Awaiting Info">Awaiting Info</option>
                  <option value="Overdue">Overdue</option>
                </select>
              </div>
              <div>
                <label className="block text-slate-600 mb-1">Reason / Note:</label>
                <textarea
                  rows={2}
                  value={statusComment}
                  onChange={(e) => setStatusComment(e.target.value)}
                  placeholder="Optional status transition remark"
                  className="w-full p-2 border border-slate-300 rounded-lg"
                ></textarea>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowStatusModal(false)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateStatus}
                className="px-4 py-1.5 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-xs rounded-lg"
              >
                Apply Status
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Request Info Modal */}
      {showRequestInfoModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="font-bold text-sm text-slate-900">Request Information from Complainant</h3>
            <p className="text-xs text-slate-500">
              This will automatically set case status to "Awaiting Info" and send an alert & email to the complainant.
            </p>
            <textarea
              rows={3}
              value={infoQuestion}
              onChange={(e) => setInfoQuestion(e.target.value)}
              placeholder="Specify the documents or clarification needed from the complainant..."
              className="w-full p-2.5 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-cyan-500"
            ></textarea>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowRequestInfoModal(false)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleRequestInfo}
                className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-700 text-white font-bold text-xs rounded-lg shadow-sm"
              >
                Dispatch Request
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Propose Determination Modal */}
      {showDeterminationModal && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="font-bold text-sm text-slate-900">Final Determination & Case Closure</h3>
            <p className="text-xs text-slate-500">
              Closing this case will archive it as read-only, notify the citizen, and solicit resolution feedback.
            </p>
            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Determination:</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="det"
                      value="Accepted"
                      checked={determinationType === 'Accepted'}
                      onChange={() => setDeterminationType('Accepted')}
                    />
                    <span className="font-bold text-emerald-700">Accepted (Remedy / Action)</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="det"
                      value="Rejected"
                      checked={determinationType === 'Rejected'}
                      onChange={() => setDeterminationType('Rejected')}
                    />
                    <span className="font-bold text-red-700">Rejected (Unsubstantiated)</span>
                  </label>
                </div>
              </div>
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Formal Findings & Reason *</label>
                <textarea
                  rows={4}
                  required
                  value={determinationReason}
                  onChange={(e) => setDeterminationReason(e.target.value)}
                  placeholder="Detail the investigative findings, actions taken against institution, or reason for dismissal..."
                  className="w-full p-2.5 border border-slate-300 rounded-lg"
                ></textarea>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowDeterminationModal(false)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleProposeDetermination}
                className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg shadow-sm"
              >
                Confirm Closure & Notify
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
