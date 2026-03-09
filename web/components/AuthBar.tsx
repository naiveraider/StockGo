"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AUTH_CHANGED_EVENT, fetchCurrentUser, getStoredToken, setStoredToken } from "../lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

interface User {
  id: number;
  email: string;
  full_name?: string | null;
}

export function AuthBar() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const syncUser = async () => {
      const token = getStoredToken();
      if (!token) {
        setUser(null);
        return;
      }
      const me = await fetchCurrentUser(API_BASE, token);
      setUser((me as User | null) ?? null);
    };

    void syncUser();
    window.addEventListener(AUTH_CHANGED_EVENT, syncUser);
    return () => {
      window.removeEventListener(AUTH_CHANGED_EVENT, syncUser);
    };
  }, []);

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
    <div className="flex items-center gap-2 text-xs">
      <Link
        href="/login"
        className="rounded bg-yahooBlue px-3 py-1.5 text-[11px] font-medium text-white hover:opacity-95"
      >
        Login
      </Link>
      <Link
        href="/login?mode=register"
        className="rounded border border-slate-300 px-3 py-1.5 text-[11px] text-slate-700 hover:bg-slate-50"
      >
        Register
      </Link>
    </div>
  );
}

