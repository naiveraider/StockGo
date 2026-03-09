"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

function resolveApiBase() {
  if (process.env.NEXT_PUBLIC_API_BASE) {
    return process.env.NEXT_PUBLIC_API_BASE;
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

interface AdminUser {
  id: number;
  email: string;
  full_name: string | null;
  role: string;
  created_at: string | null;
}

interface RoleItem {
  key: string;
  label: string;
}

export default function AdminPage() {
  const apiBase = useMemo(resolveApiBase, []);
  const [apiReachable, setApiReachable] = useState<boolean | null>(null);
  const [token, setToken] = useState<string>("");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("123");
  const [loginError, setLoginError] = useState("");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [savingUserId, setSavingUserId] = useState<number | null>(null);
  const [pageMessage, setPageMessage] = useState("");
  const [messageError, setMessageError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 2500);

    fetch(`${apiBase}/health`, { signal: controller.signal })
      .then((r) => setApiReachable(r.ok))
      .catch(() => setApiReachable(false))
      .finally(() => window.clearTimeout(timeout));

    return () => {
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [apiBase]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = sessionStorage.getItem("adminToken");
    if (saved) setToken(saved);
  }, []);

  useEffect(() => {
    if (!token) return;
    void loadAdminData(token);
  }, [token]);

  async function loadAdminData(authToken: string) {
    setLoadingUsers(true);
    setLoginError("");
    try {
      const headers = { Authorization: `Bearer ${authToken}` };
      const [usersResp, rolesResp] = await Promise.all([
        fetch(`${apiBase}/admin/users`, { headers }),
        fetch(`${apiBase}/admin/roles`, { headers }),
      ]);

      if (usersResp.status === 401 || usersResp.status === 403) {
        handleLogout();
        setLoginError("Your session expired. Please log in again.");
        return;
      }
      if (!usersResp.ok || !rolesResp.ok) {
        setLoginError("Failed to load admin data.");
        return;
      }

      const usersData = (await usersResp.json()) as AdminUser[];
      const rolesData = (await rolesResp.json()) as { roles: RoleItem[] };
      setUsers(usersData);
      setRoles(rolesData.roles || []);
    } catch {
      setLoginError("Network error while loading admin data.");
    } finally {
      setLoadingUsers(false);
    }
  }

  function handleLogout() {
    setToken("");
    setUsers([]);
    if (typeof window !== "undefined") {
      sessionStorage.removeItem("adminToken");
    }
  }

  async function handleLogin(e: FormEvent) {
    e.preventDefault();
    setLoginError("");
    try {
      const resp = await fetch(`${apiBase}/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setLoginError(data.detail || "Login failed.");
        return;
      }
      const nextToken = data.access_token as string;
      setToken(nextToken);
      if (typeof window !== "undefined") {
        sessionStorage.setItem("adminToken", nextToken);
      }
    } catch {
      setLoginError("Network error while logging in.");
    }
  }

  async function updateRole(userId: number, nextRole: string) {
    if (!token) return;
    setSavingUserId(userId);
    setPageMessage("");
    try {
      const resp = await fetch(`${apiBase}/admin/users/${userId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ role: nextRole }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setMessageError(true);
        setPageMessage(data.detail || "Failed to update role.");
        return;
      }
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role: data.role } : u)));
      setMessageError(false);
      setPageMessage("Role updated successfully.");
    } catch {
      setMessageError(true);
      setPageMessage("Request failed.");
    } finally {
      setSavingUserId(null);
    }
  }

  if (apiReachable === false) {
    return (
      <div className="mx-auto w-full max-w-3xl rounded-xl border border-amber-200 bg-amber-50 p-6 text-slate-800">
        <h2 className="text-lg font-semibold">Admin page requires the backend API.</h2>
        <p className="mt-2 text-sm text-slate-700">
          Unable to connect to <code>{apiBase}</code>. Start FastAPI and refresh this page.
        </p>
        <pre className="mt-4 overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-100">
{`cd /Users/james/python/StockGo
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`}
        </pre>
        <a
          href={`${apiBase}/admin`}
          target="_blank"
          rel="noreferrer"
          className="mt-4 inline-block rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          Open backend admin route
        </a>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="mx-auto w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">Admin Panel Login</h1>
        <p className="mt-2 text-sm text-slate-600">Use default credentials: username `admin`, password `123`.</p>
        <form className="mt-5 space-y-3" onSubmit={handleLogin}>
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">Username</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-yahooBlue focus:ring-2 focus:ring-blue-100"
              placeholder="admin"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-yahooBlue focus:ring-2 focus:ring-blue-100"
              placeholder="123"
            />
          </div>
          {loginError && <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{loginError}</div>}
          <button
            type="submit"
            className="w-full rounded-lg bg-yahooBlue px-3 py-2 text-sm font-medium text-white hover:opacity-95"
          >
            Sign in
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="w-full space-y-4">
      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">User Role Administration</h1>
          <p className="text-sm text-slate-600">Manage member, intermediate, advanced, and admin roles.</p>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          Logout
        </button>
      </div>

      {pageMessage && (
        <div
          className={`rounded-lg border px-4 py-2 text-sm ${
            messageError ? "border-rose-200 bg-rose-50 text-rose-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"
          }`}
        >
          {pageMessage}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-4 py-3 text-left font-medium">ID</th>
              <th className="px-4 py-3 text-left font-medium">Email</th>
              <th className="px-4 py-3 text-left font-medium">Name</th>
              <th className="px-4 py-3 text-left font-medium">Role</th>
              <th className="px-4 py-3 text-left font-medium">Created</th>
            </tr>
          </thead>
          <tbody>
            {loadingUsers && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                  Loading users...
                </td>
              </tr>
            )}

            {!loadingUsers && users.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                  No users found.
                </td>
              </tr>
            )}

            {!loadingUsers &&
              users.map((u) => (
                <tr key={u.id} className="border-t border-slate-100">
                  <td className="px-4 py-3 text-slate-700">{u.id}</td>
                  <td className="px-4 py-3 text-slate-900">{u.email}</td>
                  <td className="px-4 py-3 text-slate-700">{u.full_name || "-"}</td>
                  <td className="px-4 py-3">
                    <select
                      value={u.role}
                      disabled={savingUserId === u.id}
                      onChange={(e) => updateRole(u.id, e.target.value)}
                      className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-800 outline-none focus:border-yahooBlue"
                    >
                      {roles.map((r) => (
                        <option key={r.key} value={r.key}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3 text-slate-500">{u.created_at ? new Date(u.created_at).toLocaleString() : "-"}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
