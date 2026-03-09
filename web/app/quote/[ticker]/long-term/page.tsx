"use client";

import Link from "next/link";
import useSWR from "swr";
import { useEffect, useMemo, useState } from "react";
import { authedJson, fetchCurrentUser, getStoredToken, hasMinRole, type UserRole } from "../../../../lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type Report = {
  status: string;
  report?: { bias: "UP" | "DOWN" | "NEUTRAL"; confidence: number; summary: string; reasoning: string };
  error?: string | null;
};

export default function LongTermPage({ params }: { params: { ticker: string } }) {
  const ticker = useMemo(() => (params.ticker || "TSLA").toUpperCase(), [params.ticker]);
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
      if (!hasMinRole(me.role, "intermediate" as UserRole)) {
        setAccess("forbidden");
        return;
      }
      setToken(t);
      setAccess("ok");
    };
    void init();
  }, []);

  const { data, error, isLoading } = useSWR<Report>(
    access === "ok" && token ? `${API_BASE}/v1/report/long-term?ticker=${encodeURIComponent(ticker)}&years=5` : null,
    (url: string) => authedJson<Report>(url, token as string)
  );

  const bias = data?.report?.bias;
  const conf = data?.report?.confidence ?? 0;
  const biasColor =
    bias === "UP"
      ? "text-emerald-600"
      : bias === "DOWN"
        ? "text-rose-600"
        : bias === "NEUTRAL"
          ? "text-amber-600"
          : "text-slate-900";

  if (access === "checking") {
    return <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">Checking access...</div>;
  }

  if (access === "need-login") {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-slate-700">
        Please <Link className="text-yahooBlue hover:underline" href="/login">login</Link> to access Long-term bias.
      </div>
    );
  }

  if (access === "forbidden") {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
        Long-term bias requires at least the Intermediate role.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-xs text-slate-500">Long-term bias</div>
            <h2 className="text-2xl font-semibold text-slate-900">{ticker}</h2>
            <p className="mt-1 text-sm text-slate-500">Horizon: 5 years (daily technicals, news ignored).</p>
          </div>
          <Link className="text-yahooBlue hover:underline" href={`/quote/${ticker}`}>
            ← Back to quote
          </Link>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        {isLoading && <p className="text-sm text-slate-500">Computing long-term report…</p>}
        {error && <p className="text-sm text-rose-600">Failed to load long-term report.</p>}
        {data?.error && <p className="text-sm text-rose-600">{data.error}</p>}
        {data?.report && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className={`text-xl font-semibold ${biasColor}`}>{bias}</div>
              <div className="text-sm text-slate-600">
                Confidence: <span className="font-medium text-slate-900">{Math.round(conf * 100)}%</span>
              </div>
            </div>
            <div className="rounded border border-slate-200 bg-slate-50 p-3">
              <div className="text-xs font-semibold text-slate-600 mb-1">Summary</div>
              <p className="text-sm whitespace-pre-line text-slate-900">{data.report.summary}</p>
            </div>
            <div className="text-sm text-slate-700">{data.report.reasoning}</div>
          </div>
        )}
      </div>
    </div>
  );
}

