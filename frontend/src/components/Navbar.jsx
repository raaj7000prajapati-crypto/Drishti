import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import NotificationBell from './NotificationBell';
import {
  ShieldAlert,
  FileText,
  BarChart3,
  Users,
  History,
  LogOut,
  LogIn,
  PlusCircle,
  Menu,
  X,
  Building2,
  Inbox
} from 'lucide-react';

export default function Navbar() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path) => location.pathname === path;

  return (
    <header className="bg-slate-900 border-b border-slate-800 sticky top-0 z-40 text-white shadow-md">
      {/* Top Gov Banner */}
      <div className="bg-slate-950 px-4 py-1 border-b border-slate-800 text-[11px] text-slate-400 flex justify-between items-center">
        <div className="flex items-center space-x-2">
          <span className="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
          <span>GOVERNMENT OF INDIA • ALL INDIA COUNCIL FOR TECHNICAL EDUCATION</span>
        </div>
        <div className="hidden sm:flex items-center space-x-4">
          <span className="text-amber-400 font-medium">Smart India Hackathon 2026 Prototype</span>
          <span>AICTE Redressal Portal</span>
        </div>
      </div>

      {/* Main Nav */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <Link to="/" className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-500/20 text-white font-bold text-xl">
              दृ
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-extrabold text-xl tracking-tight text-white">DRISHTI</span>
                <span className="text-xs px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30 font-semibold">
                  AICTE
                </span>
              </div>
              <p className="text-[10px] text-slate-400 font-medium tracking-wide">
                INTEGRATED COMPLAINT MONITORING SYSTEM
              </p>
            </div>
          </Link>

          {/* Desktop Navigation Links */}
          <nav className="hidden md:flex items-center space-x-1">
            {isAuthenticated ? (
              <>
                {user?.role === 'COMPLAINANT' && (
                  <>
                    <Link
                      to="/my-complaints"
                      className={`px-3 py-2 rounded-md text-sm font-medium transition ${
                        isActive('/my-complaints')
                          ? 'bg-amber-500 text-slate-950 font-bold'
                          : 'text-slate-300 hover:text-white hover:bg-slate-800'
                      }`}
                    >
                      My Grievances
                    </Link>
                    <Link
                      to="/file-complaint"
                      className={`px-3 py-2 rounded-md text-sm font-medium flex items-center gap-1.5 transition ${
                        isActive('/file-complaint')
                          ? 'bg-amber-500 text-slate-950 font-bold'
                          : 'text-slate-300 hover:text-white hover:bg-slate-800'
                      }`}
                    >
                      <PlusCircle className="w-4 h-4" /> File Grievance
                    </Link>
                  </>
                )}

                {user?.role === 'OFFICIAL' && (
                  <>
                    <Link
                      to="/official/inbox"
                      className={`px-3 py-2 rounded-md text-sm font-medium flex items-center gap-1.5 transition ${
                        isActive('/official/inbox')
                          ? 'bg-amber-500 text-slate-950 font-bold'
                          : 'text-slate-300 hover:text-white hover:bg-slate-800'
                      }`}
                    >
                      <Inbox className="w-4 h-4" /> Bureau Inbox
                    </Link>
                    <Link
                      to="/complaints"
                      className={`px-3 py-2 rounded-md text-sm font-medium flex items-center gap-1.5 transition ${
                        isActive('/complaints')
                          ? 'bg-amber-500 text-slate-950 font-bold'
                          : 'text-slate-300 hover:text-white hover:bg-slate-800'
                      }`}
                    >
                      <FileText className="w-4 h-4" /> All Cases
                    </Link>
                  </>
                )}

                {user?.role === 'ADMIN' && (
                  <>
                    <Link
                      to="/admin/dashboard"
                      className={`px-3 py-2 rounded-md text-sm font-medium flex items-center gap-1.5 transition ${
                        isActive('/admin/dashboard')
                          ? 'bg-amber-500 text-slate-950 font-bold'
                          : 'text-slate-300 hover:text-white hover:bg-slate-800'
                      }`}
                    >
                      <BarChart3 className="w-4 h-4" /> Analytics
                    </Link>
                    <Link
                      to="/complaints"
                      className={`px-3 py-2 rounded-md text-sm font-medium flex items-center gap-1.5 transition ${
                        isActive('/complaints')
                          ? 'bg-amber-500 text-slate-950 font-bold'
                          : 'text-slate-300 hover:text-white hover:bg-slate-800'
                      }`}
                    >
                      <FileText className="w-4 h-4" /> Grievances
                    </Link>
                    <Link
                      to="/admin/manage"
                      className={`px-3 py-2 rounded-md text-sm font-medium flex items-center gap-1.5 transition ${
                        isActive('/admin/manage')
                          ? 'bg-amber-500 text-slate-950 font-bold'
                          : 'text-slate-300 hover:text-white hover:bg-slate-800'
                      }`}
                    >
                      <Building2 className="w-4 h-4" /> Governance
                    </Link>
                    <Link
                      to="/admin/audit"
                      className={`px-3 py-2 rounded-md text-sm font-medium flex items-center gap-1.5 transition ${
                        isActive('/admin/audit')
                          ? 'bg-amber-500 text-slate-950 font-bold'
                          : 'text-slate-300 hover:text-white hover:bg-slate-800'
                      }`}
                    >
                      <History className="w-4 h-4" /> Audit Logs
                    </Link>
                  </>
                )}
              </>
            ) : (
              <>
                <Link
                  to="/"
                  className={`px-3 py-2 rounded-md text-sm font-medium transition ${
                    isActive('/') ? 'text-amber-400 font-bold' : 'text-slate-300 hover:text-white'
                  }`}
                >
                  Home
                </Link>
                <Link
                  to="/file-complaint"
                  className="px-3 py-2 rounded-md text-sm font-medium text-slate-300 hover:text-white"
                >
                  File Grievance
                </Link>
                <Link
                  to="/login"
                  className="px-3 py-2 rounded-md text-sm font-medium text-slate-300 hover:text-white"
                >
                  Track Grievance
                </Link>
              </>
            )}
          </nav>

          {/* Right Header: Notifications & Profile */}
          <div className="hidden md:flex items-center space-x-3">
            {isAuthenticated ? (
              <>
                <NotificationBell />
                <div className="flex items-center space-x-2 pl-3 border-l border-slate-700">
                  <div className="text-right">
                    <p className="text-xs font-semibold text-white leading-tight">
                      {user?.full_name}
                    </p>
                    <p className="text-[10px] text-amber-400 font-medium">
                      {user?.role === 'OFFICIAL' ? user?.bureau_name || 'Official' : user?.role}
                    </p>
                  </div>
                  <button
                    onClick={handleLogout}
                    title="Logout"
                    className="p-1.5 text-slate-400 hover:text-red-400 rounded-md hover:bg-slate-800 transition"
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              </>
            ) : (
              <div className="flex items-center space-x-2">
                <Link
                  to="/login"
                  className="px-3 py-1.5 text-xs font-medium text-slate-200 hover:text-white hover:bg-slate-800 rounded-md transition"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  className="px-3 py-1.5 text-xs font-semibold bg-amber-500 hover:bg-amber-600 text-slate-950 rounded-md transition shadow-sm"
                >
                  Register
                </Link>
              </div>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="flex md:hidden items-center space-x-2">
            {isAuthenticated && <NotificationBell />}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 text-slate-400 hover:text-white focus:outline-none"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-slate-900 border-b border-slate-800 px-4 pt-2 pb-4 space-y-1">
          {isAuthenticated ? (
            <>
              <div className="pb-2 border-b border-slate-800 mb-2">
                <p className="text-sm font-semibold text-white">{user?.full_name}</p>
                <p className="text-xs text-amber-400">{user?.role} {user?.bureau_name ? `• ${user?.bureau_name}` : ''}</p>
              </div>
              {user?.role === 'COMPLAINANT' && (
                <>
                  <Link
                    to="/my-complaints"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 rounded-md text-sm text-slate-300 hover:bg-slate-800"
                  >
                    My Grievances
                  </Link>
                  <Link
                    to="/file-complaint"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 rounded-md text-sm text-slate-300 hover:bg-slate-800"
                  >
                    File Grievance
                  </Link>
                </>
              )}
              {user?.role === 'OFFICIAL' && (
                <>
                  <Link
                    to="/official/inbox"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 rounded-md text-sm text-slate-300 hover:bg-slate-800"
                  >
                    Bureau Inbox
                  </Link>
                  <Link
                    to="/complaints"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 rounded-md text-sm text-slate-300 hover:bg-slate-800"
                  >
                    All Cases
                  </Link>
                </>
              )}
              {user?.role === 'ADMIN' && (
                <>
                  <Link
                    to="/admin/dashboard"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 rounded-md text-sm text-slate-300 hover:bg-slate-800"
                  >
                    Analytics Dashboard
                  </Link>
                  <Link
                    to="/complaints"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 rounded-md text-sm text-slate-300 hover:bg-slate-800"
                  >
                    All Grievances
                  </Link>
                  <Link
                    to="/admin/manage"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 rounded-md text-sm text-slate-300 hover:bg-slate-800"
                  >
                    Governance & Rules
                  </Link>
                  <Link
                    to="/admin/audit"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 rounded-md text-sm text-slate-300 hover:bg-slate-800"
                  >
                    Audit Trail
                  </Link>
                </>
              )}
              <button
                onClick={() => {
                  setMobileMenuOpen(false);
                  handleLogout();
                }}
                className="w-full text-left px-3 py-2 text-sm text-red-400 hover:bg-slate-800 rounded-md"
              >
                Sign Out
              </button>
            </>
          ) : (
            <>
              <Link
                to="/"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-md text-sm text-slate-300 hover:bg-slate-800"
              >
                Home
              </Link>
              <Link
                to="/file-complaint"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-md text-sm text-slate-300 hover:bg-slate-800"
              >
                File Grievance
              </Link>
              <Link
                to="/login"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-md text-sm text-amber-400 hover:bg-slate-800 font-semibold"
              >
                Sign In
              </Link>
              <Link
                to="/register"
                onClick={() => setMobileMenuOpen(false)}
                className="block px-3 py-2 rounded-md text-sm text-slate-300 hover:bg-slate-800"
              >
                Register
              </Link>
            </>
          )}
        </div>
      )}
    </header>
  );
}
