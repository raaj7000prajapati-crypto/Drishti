import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Intercept requests to add JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('drishti_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Refresh once using the httpOnly cookie, then retry the original request.
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response && error.response.status === 401) {
      const originalRequest = error.config;
      const isAuthRequest = /\/auth\/(login|register|refresh|logout)/.test(originalRequest.url || '');
      if (!isAuthRequest && !originalRequest._retry) {
        originalRequest._retry = true;
        try {
          const refreshResponse = await api.post('/auth/refresh');
          const nextToken = refreshResponse.data.access_token;
          localStorage.setItem('drishti_token', nextToken);
          window.dispatchEvent(new Event('drishti:token-refreshed'));
          originalRequest.headers.Authorization = `Bearer ${nextToken}`;
          return api(originalRequest);
        } catch (refreshError) {
          localStorage.removeItem('drishti_token');
          localStorage.removeItem('drishti_user');
          window.dispatchEvent(new Event('drishti:session-expired'));
          return Promise.reject(refreshError);
        }
      }
    }
    return Promise.reject(error);
  }
);

// --- Auth APIs ---
export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  logout: () => api.post('/auth/logout'),
  register: (data) => api.post('/auth/register', data),
  getMe: () => api.get('/auth/me'),
};

// --- Complaints APIs ---
export const complaintsAPI = {
  list: (params) => api.get('/complaints/', { params }),
  get: (id) => api.get(`/complaints/${id}`),
  downloadAttachment: (complaintId, attachmentId) =>
    api.get(`/complaints/${complaintId}/attachments/${attachmentId}`, { responseType: 'blob' }),
  downloadAnnotationAttachment: (complaintId, annotationId) =>
    api.get(`/complaints/${complaintId}/annotations/${annotationId}/attachment`, { responseType: 'blob' }),
  checkDuplicates: (subject, description) =>
    api.post('/complaints/check-duplicates', null, { params: { subject, description } }),
  fileComplaint: (formData) =>
    api.post('/complaints/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  respondInfo: (id, data, requestId) =>
    api.post(`/complaints/${id}/info-respond`, data, { params: { request_id: requestId } }),
  submitFeedback: (id, data) => api.post(`/complaints/${id}/feedback`, data),
};

// --- Officials APIs ---
export const officialsAPI = {
  updateStatus: (id, data) => api.post(`/officials/cases/${id}/status`, data),
  requestInfo: (id, data) => api.post(`/officials/cases/${id}/request-info`, data),
  addAnnotation: (id, formData) =>
    api.post(`/officials/cases/${id}/annotate`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  proposeDetermination: (id, data) => api.post(`/officials/cases/${id}/determination`, data),
  decideLink: (linkId, decision) =>
    api.post(`/officials/links/${linkId}/decide`, null, { params: { decision } }),
};

// --- Admin APIs ---
export const adminAPI = {
  getUsers: (params) => api.get('/admin/users', { params }),
  createUser: (data) => api.post('/admin/users', data),
  updateUser: (id, data) => api.put(`/admin/users/${id}`, data),
  getBureaus: () => api.get('/admin/bureaus'),
  createBureau: (data) => api.post('/admin/bureaus', data),
  getRules: () => api.get('/admin/rules'),
  createRule: (data) => api.post('/admin/rules', data),
  deleteRule: (id) => api.delete(`/admin/rules/${id}`),
  getSLA: () => api.get('/admin/sla'),
  updateSLA: (priority, data) => api.put(`/admin/sla/${priority}`, data),
  getSimilarityThresholds: () => api.get('/admin/similarity-thresholds'),
  updateSimilarityThresholds: (data) =>
    api.put('/admin/similarity-thresholds', data),
  reassignComplaint: (id, data) => api.post(`/admin/complaints/${id}/reassign`, data),
  getAuditLogs: (params) => api.get('/admin/audit-logs', { params }),
  verifyAuditLogChain: () => api.get('/admin/audit-logs/verify'),
};

// --- Analytics & Reports APIs ---
export const analyticsAPI = {
  getDashboardStats: (params) => api.get('/analytics/dashboard', { params }),
  exportCSV: (params) =>
    api.get('/reports/export/csv', { params, responseType: 'blob' }),
  exportPDF: (params) =>
    api.get('/reports/export/pdf', { params, responseType: 'blob' }),
};

// --- Notifications APIs ---
export const notificationsAPI = {
  getAll: () => api.get('/notifications/'),
  markRead: (id) => api.put(`/notifications/${id}/read`),
  markAllRead: () => api.put('/notifications/read-all'),
};

export default api;
