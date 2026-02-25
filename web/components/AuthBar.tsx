"use client";

import { FormEvent, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

interface User {
  id: number;
  email: string;
  full_name?: string | null;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

type Mode = "login" | "register";

function getStoredToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("stockgo_token");
}

function setStoredToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) {
    window.localStorage.setItem("stockgo_token", token);
  } else {
    window.localStorage.removeItem("stockgo_token");
  }
}

export function AuthBar() {
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (!res.ok) return;
        const data = (await res.json()) as User;
        setUser(data);
      } catch {
        // ignore
      }
    })();
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
      const body: Record<string, string> = { email, password };
      if (mode === "register" && fullName) {
        body.full_name = fullName;
      }
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Request failed");
      }
      const data = (await res.json()) as TokenResponse;
      setStoredToken(data.access_token);
      setUser(data.user);
      setPassword("");
    } catch (err: any) {
      setError(err?.message || "Failed");
    } finally {
      setLoading(false);
    }
  }

  function handleLogout() {
    setStoredToken(null);
    setUser(null);
  }

  if (user) {
    return (
      <div className="flex items-center gap-3 text-xs">
        <span className="text-slate-700">Hi, {user.full_name || user.email}</span>
        <button
          onClick={handleLogout}
          className="rounded border border-slate-300 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-50"
        >
          Logout
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <form onSubmit={handleSubmit} className="flex items-center gap-2 text-xs">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="email"
          className="w-32 rounded border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-900 placeholder:text-slate-400 outline-none focus:border-yahooBlue"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="password"
          className="w-24 rounded border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-900 placeholder:text-slate-400 outline-none focus:border-yahooBlue"
        />
        {mode === "register" && (
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="name"
            className="w-24 rounded border border-slate-300 bg-white px-2 py-1 text-[11px] text-slate-900 placeholder:text-slate-400 outline-none focus:border-yahooBlue"
          />
        )}
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-yahooBlue px-3 py-1 text-[11px] font-medium text-white hover:opacity-95 disabled:opacity-60"
        >
          {loading ? "..." : mode === "login" ? "Login" : "Register"}
        </button>
      </form>
      <button
        type="button"
        onClick={() => {
          setMode(mode === "login" ? "register" : "login");
          setError(null);
        }}
        className="text-[11px] text-yahooBlue hover:opacity-80"
      >
        {mode === "login" ? "Need an account?" : "Have an account?"}
      </button>
      {error && <span className="text-[11px] text-rose-400">{error}</span>}
    </div>
  );
}

