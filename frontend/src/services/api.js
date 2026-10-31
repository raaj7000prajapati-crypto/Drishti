import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
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

// Intercept 401 responses to auto-logout or refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response && error.response.status === 401) {
      // If unauthorized on a protected route, clear credentials
      const originalRequest = error.config;
      if (!originalRequest.url.includes('/auth/login') && !originalRequest.url.includes('/auth/register')) {
        localStorage.removeItem('drishti_token');
        localStorage.removeItem('drishti_refresh');
        localStorage.removeItem('drishti_user');
      }
    }
    return Promise.reject(error);
  }
);

// --- Auth APIs ---
export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  register: (data) => api.post('/auth/register', data),
  getMe: () => api.get('/auth/me'),
};

// --- Complaints APIs ---
export const complaintsAPI = {
  list: (params) => api.get('/complaints/', { params }),
  get: (id) => api.get(`/complaints/${id}`),
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
  reassignComplaint: (id, data) => api.post(`/admin/complaints/${id}/reassign`, data),
  getAuditLogs: (params) => api.get('/admin/audit-logs', { params }),
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
