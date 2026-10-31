import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import Footer from './components/Footer';

// Pages
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import FileComplaint from './pages/FileComplaint';
import ComplainantDashboard from './pages/ComplainantDashboard';
import OfficialInbox from './pages/OfficialInbox';
import ComplaintsList from './pages/ComplaintsList';
import ComplaintDetail from './pages/ComplaintDetail';
import AdminDashboard from './pages/AdminDashboard';
import AdminManagement from './pages/AdminManagement';
import AuditLogViewer from './pages/AuditLogViewer';

// Protected Route Guard
const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user, isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center text-xs text-slate-500">
        Loading session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user?.role)) {
    // Redirect to their default dashboard
    if (user?.role === 'ADMIN') return <Navigate to="/admin/dashboard" replace />;
    if (user?.role === 'OFFICIAL') return <Navigate to="/official/inbox" replace />;
    return <Navigate to="/my-complaints" replace />;
  }

  return children;
};

function AppRoutes() {
  return (
    <div className="flex flex-col min-h-screen bg-slate-50 text-slate-900">
      <Navbar />
      <main className="flex-1">
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/file-complaint" element={<FileComplaint />} />

          {/* Complainant Routes */}
          <Route
            path="/my-complaints"
            element={
              <ProtectedRoute allowedRoles={['COMPLAINANT', 'ADMIN']}>
                <ComplainantDashboard />
              </ProtectedRoute>
            }
          />

          {/* Official Routes */}
          <Route
            path="/official/inbox"
            element={
              <ProtectedRoute allowedRoles={['OFFICIAL', 'ADMIN']}>
                <OfficialInbox />
              </ProtectedRoute>
            }
          />

          {/* Shared Case Examination */}
          <Route
            path="/complaints"
            element={
              <ProtectedRoute allowedRoles={['OFFICIAL', 'ADMIN']}>
                <ComplaintsList />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases/:id"
            element={
              <ProtectedRoute>
                <ComplaintDetail />
              </ProtectedRoute>
            }
          />

          {/* Admin Routes */}
          <Route
            path="/admin/dashboard"
            element={
              <ProtectedRoute allowedRoles={['ADMIN']}>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/manage"
            element={
              <ProtectedRoute allowedRoles={['ADMIN']}>
                <AdminManagement />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/audit"
            element={
              <ProtectedRoute allowedRoles={['ADMIN']}>
                <AuditLogViewer />
              </ProtectedRoute>
            }
          />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
