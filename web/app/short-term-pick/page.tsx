"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { authedJson, fetchCurrentUser, getStoredToken, hasMinRole, type UserRole } from "../../lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

type ShortTermRow = {
  ticker: string;
  name?: string | null;
  bias: "UP" | "DOWN" | "NEUTRAL";
  confidence: number;
  updated_at: string;
};

type PicksPage = {
  items: ShortTermRow[];
  total: number;
};

const PAGE_SIZE = 20;

export default function ShortTermPickPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(0);
  const [token, setToken] = useState<string | null>(null);
  const [access, setAccess] = useState<"checking" | "need-login" | "forbidden" | "ok">("checking");

  useEffect(() => {
    const init = async () => {
      const t = getStoredToken();
      if (!t) {
        setAccess("need-login");
        return;
      }
      const me = await fetchCurrentUser(API_BASE, t);
      if (!me) {
        setAccess("need-login");
        return;
      }
      if (!hasMinRole(me.role, "advanced" as UserRole)) {
        setAccess("forbidden");
        return;
      }
      setToken(t);
      setAccess("ok");
    };
    void init();
  }, []);

  const q = searchQuery.trim();
  const { data, error, isLoading } = useSWR<PicksPage>(
    access === "ok" && token
      ? `${API_BASE}/v1/screener/short-term-picks?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}${q ? `&q=${encodeURIComponent(q)}` : ""}`
      : null,
    (url: string) => authedJson<PicksPage>(url, token as string)
  );

  const picks = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentItems = picks;
  const from = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const to = Math.min((page + 1) * PAGE_SIZE, total);

  if (access === "checking") {
    return <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">Checking access...</div>;
  }

  if (access === "need-login") {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-slate-700">
        Please <Link className="text-yahooBlue hover:underline" href="/login">login</Link> to access Short-term pick.
      </div>
    );
  }

  if (access === "forbidden") {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
        Short-term pick requires at least the Advanced role.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Short-term pick</h2>
            <p className="text-sm text-slate-500">
              Pick list: UP bias with confidence at least 65%.
            </p>
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(0);
            }}
            placeholder="Filter by name or symbol"
            className="rounded border border-slate-300 px-3 py-2 text-sm w-52 outline-none focus:border-yahooBlue"
          />
        </div>
        {error && <p className="mt-2 text-sm text-rose-600">Failed to load short-term picks.</p>}
        {isLoading && <p className="mt-2 text-sm text-slate-500">Loading...</p>}
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500">
            <tr>
              <th className="px-4 py-3">Symbol</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Bias</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3">Updated</th>
            </tr>
          </thead>
          <tbody>
            {currentItems.map((it) => (
              <tr key={it.ticker} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-900">
                  <Link className="text-yahooBlue hover:underline" href={`/quote/${it.ticker}`}>
                    {it.ticker}
                  </Link>
                </td>
                <td className="px-4 py-3 text-slate-700">{it.name || "-"}</td>
                <td className="px-4 py-3 font-semibold text-emerald-600">{it.bias}</td>
                <td className="px-4 py-3 text-slate-700">{Math.round(it.confidence * 100)}%</td>
                <td className="px-4 py-3 text-slate-500">{new Date(it.updated_at).toLocaleString()}</td>
              </tr>
            ))}
            {currentItems.length === 0 && !isLoading && (
              <tr>
                <td className="px-4 py-6 text-slate-500" colSpan={5}>
                  No short-term picks found with the current filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-slate-600">
          Showing {from}-{to} of {total}
          {totalPages > 1 && ` · Page ${page + 1} of ${totalPages}`}
        </div>
        <div className="flex items-center gap-2">
          <button
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            className="rounded border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50 hover:bg-slate-50"
          >
            Previous
          </button>
          <button
            disabled={page + 1 >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50 hover:bg-slate-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
