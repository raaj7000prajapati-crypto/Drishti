import React, { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('drishti_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem('drishti_token'));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const handleTokenRefresh = () => setToken(localStorage.getItem('drishti_token'));
    const handleSessionExpired = () => {
      localStorage.removeItem('drishti_token');
      localStorage.removeItem('drishti_user');
      setToken(null);
      setUser(null);
    };
    window.addEventListener('drishti:token-refreshed', handleTokenRefresh);
    window.addEventListener('drishti:session-expired', handleSessionExpired);

    const verifyAuth = async () => {
      const savedToken = localStorage.getItem('drishti_token');
      if (savedToken) {
        try {
          const res = await authAPI.getMe();
          setUser(res.data);
          localStorage.setItem('drishti_user', JSON.stringify(res.data));
        } catch {
          handleSessionExpired();
        }
      }
      setLoading(false);
    };
    verifyAuth();
    return () => {
      window.removeEventListener('drishti:token-refreshed', handleTokenRefresh);
      window.removeEventListener('drishti:session-expired', handleSessionExpired);
    };
  }, []);

  const login = async (email, password) => {
    const res = await authAPI.login({ email, password });
    const { access_token, user: userData } = res.data;
    localStorage.setItem('drishti_token', access_token);
    localStorage.setItem('drishti_user', JSON.stringify(userData));
    setToken(access_token);
    setUser(userData);
    return userData;
  };

  const register = async (userData) => {
    const res = await authAPI.register(userData);
    return res.data;
  };

  const clearSession = () => {
    localStorage.removeItem('drishti_token');
    localStorage.removeItem('drishti_user');
    setToken(null);
    setUser(null);
  };

  const logout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error('Could not revoke the server refresh token during logout:', error);
    } finally {
      clearSession();
    }
  };

  const refreshUser = async () => {
    try {
      const res = await authAPI.getMe();
      setUser(res.data);
      localStorage.setItem('drishti_user', JSON.stringify(res.data));
    } catch (err) {
      console.error('Failed to refresh user:', err);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        role: user?.role,
        loading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
