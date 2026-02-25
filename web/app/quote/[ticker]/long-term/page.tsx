"use client";

import Link from "next/link";
import useSWR from "swr";
import { useMemo } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

type Report = {
  status: string;
  report?: { bias: "UP" | "DOWN" | "NEUTRAL"; confidence: number; summary: string; reasoning: string };
  error?: string | null;
};

export default function LongTermPage({ params }: { params: { ticker: string } }) {
  const ticker = useMemo(() => (params.ticker || "TSLA").toUpperCase(), [params.ticker]);
  const { data, error, isLoading } = useSWR<Report>(
    `${API_BASE}/v1/report/long-term?ticker=${encodeURIComponent(ticker)}&years=5`,
    fetcher
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

