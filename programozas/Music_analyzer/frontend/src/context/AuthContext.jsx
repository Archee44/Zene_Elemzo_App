import React, { createContext, useContext, useEffect, useState } from "react";
import axios from "axios";

const AuthContext = createContext(null);

const API_BASE = "http://127.0.0.1:5000/api/auth";
const TOKEN_KEY = "app_token";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Capture the token handed back by the OAuth redirect, or fall back to
  // whatever was saved from a previous visit.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");

    if (urlToken) {
      localStorage.setItem(TOKEN_KEY, urlToken);
      setToken(urlToken);
      const cleanPath = window.location.pathname || "/";
      window.history.replaceState({}, "", cleanPath);
    } else {
      const savedToken = localStorage.getItem(TOKEN_KEY);
      if (savedToken) setToken(savedToken);
    }
  }, []);

  const refreshUser = async (currentToken = token) => {
    if (!currentToken) {
      setUser(null);
      return;
    }
    try {
      const res = await axios.get(`${API_BASE}/me`, { headers: { Authorization: `Bearer ${currentToken}` } });
      setUser(res.data);
    } catch {
      // Stale/expired token - clean up rather than keep retrying with it.
      localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setUser(null);
    }
  };

  useEffect(() => {
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    refreshUser(token).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const login = () => {
    window.location.href = `${API_BASE}/login`;
  };

  const logout = () => {
    const current = token;
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    if (current) {
      axios
        .post(`${API_BASE}/logout`, null, { headers: { Authorization: `Bearer ${current}` } })
        .catch(() => {});
    }
  };

  // Returns { ok: true } on success, or { ok: false, error } so the caller
  // can show the message inline (e.g. "username already taken").
  const updateUsername = async (username) => {
    if (!token) return { ok: false, error: "Nincs bejelentkezve." };
    try {
      const res = await axios.patch(
        `${API_BASE}/me`,
        { username },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setUser(res.data);
      return { ok: true };
    } catch (err) {
      const message = err?.response?.data?.error || "Nem sikerült menteni a felhasználónevet.";
      return { ok: false, error: message };
    }
  };

  const connectYoutube = async () => {
    if (!token) return;
    try {
      const res = await axios.post(
        `${API_BASE}/youtube/connect-init`,
        null,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      window.location.href = res.data.authorize_url;
    } catch {
      // no-op - the user just stays on the page if this somehow fails
    }
  };

  const disconnectYoutube = async () => {
    if (!token) return;
    try {
      await axios.delete(`${API_BASE}/youtube/disconnect`, { headers: { Authorization: `Bearer ${token}` } });
      await refreshUser();
    } catch {
      // no-op
    }
  };

  return (
    <AuthContext.Provider
      value={{ user, token, loading, login, logout, updateUsername, refreshUser, connectYoutube, disconnectYoutube }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
