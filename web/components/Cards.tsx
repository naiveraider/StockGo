"use client";

import useSWR from "swr";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface Overview {
  ticker: string;
  last_price?: number;
  prev_close?: number;
  change?: number;
  change_percent?: number;
  market_cap?: number;
  pe_ratio?: number;
  forward_pe?: number;
  fifty_two_week_high?: number;
  fifty_two_week_low?: number;
  currency?: string;
}

interface AnalysisReport {
  bias: "UP" | "DOWN" | "NEUTRAL";
  confidence: number;
  summary: string;
  reasoning: string;
}

interface AnalysisResponse {
  status: string;
  report?: AnalysisReport;
  error?: string | null;
}

interface NewsItem {
  published_at?: string;
  source?: string | null;
  title: string;
  url: string;
  sentiment_label?: string | null;
}

interface NewsList {
  items: NewsItem[];
}

function formatNumber(n?: number, digits = 2) {
  if (n === undefined || n === null) return "-";
  return n.toFixed(digits);
}

function formatMarketCap(n?: number) {
  if (!n && n !== 0) return "-";
  const abs = Math.abs(n);
  if (abs >= 1e12) return (n / 1e12).toFixed(2) + "T";
  if (abs >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (abs >= 1e6) return (n / 1e6).toFixed(2) + "M";
  return n.toFixed(0);
}

export function StockOverviewCard({ ticker }: { ticker: string }) {
  const { data, error, isLoading } = useSWR<Overview>(
    `${API_BASE}/v1/stock/overview?ticker=${encodeURIComponent(ticker)}`,
    fetcher,
    { refreshInterval: 15_000 }
  );

  const changeColor =
    data?.change && data.change !== 0 ? (data.change > 0 ? "text-emerald-400" : "text-rose-400") : "text-slate-200";

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-slate-200">Real-time Price</h2>
        <span className="text-xs text-slate-500">{data?.currency || "USD"}</span>
      </div>
      {isLoading && <p className="text-xs text-slate-500">Loading price...</p>}
      {error && <p className="text-xs text-rose-400">Failed to load price.</p>}
      {data && (
        <div className="flex items-end justify-between">
          <div>
            <div className="text-2xl font-semibold text-slate-50">
              {data.last_price !== undefined ? formatNumber(data.last_price, 2) : "-"}
            </div>
            <div className={`mt-1 text-xs ${changeColor}`}>
              {data.change !== undefined && data.change_percent !== undefined ? (
                <>
                  {data.change > 0 ? "+" : ""}
                  {formatNumber(data.change, 2)} ({formatNumber(data.change_percent, 2)}%)
                </>
              ) : (
                "—"
              )}
            </div>
          </div>
          <div className="space-y-1 text-right text-[11px] text-slate-400">
            <div>
              Market Cap: <span className="text-slate-200">{formatMarketCap(data.market_cap)}</span>
            </div>
            <div>
              PE (TTM): <span className="text-slate-200">{formatNumber(data.pe_ratio, 2)}</span>
            </div>
            <div>
              Fwd PE: <span className="text-slate-200">{formatNumber(data.forward_pe, 2)}</span>
            </div>
            <div>
              52w Range:{" "}
              <span className="text-slate-200">
                {formatNumber(data.fifty_two_week_low, 0)} - {formatNumber(data.fifty_two_week_high, 0)}
              </span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export function PredictionCard({ ticker }: { ticker: string }) {
  const { data, error, isLoading } = useSWR<AnalysisResponse>(
    `${API_BASE}/v1/report/latest?ticker=${encodeURIComponent(ticker)}`,
    fetcher,
    { refreshInterval: 60_000 }
  );

  const bias = data?.report?.bias;
  const conf = data?.report?.confidence ?? 0;

  const biasColor =
    bias === "UP" ? "text-emerald-400" : bias === "DOWN" ? "text-rose-400" : bias === "NEUTRAL" ? "text-amber-300" : "text-slate-200";

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Short-term Bias (Model)</h2>
        <span className="text-[11px] text-slate-500">from FastAPI + GPT pipeline</span>
      </div>
      {isLoading && <p className="text-xs text-slate-500">Loading prediction...</p>}
      {error && <p className="text-xs text-rose-400">Failed to load prediction.</p>}
      {data?.report && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className={`text-lg font-semibold ${biasColor}`}>{bias}</div>
            <div className="text-xs text-slate-400">
              Confidence: <span className="text-slate-200">{Math.round(conf * 100)}%</span>
            </div>
          </div>
          <p className="text-xs whitespace-pre-line text-slate-200">{data.report.summary}</p>
          <p className="text-[11px] text-slate-400">{data.report.reasoning}</p>
        </div>
      )}
      {!isLoading && !error && !data?.report && (
        <p className="text-xs text-slate-500">No prediction yet. Trigger analysis in backend first.</p>
      )}
    </section>
  );
}

export function NewsListCard({ ticker }: { ticker: string }) {
  const { data, error, isLoading } = useSWR<NewsList>(
    `${API_BASE}/v1/stock/news?ticker=${encodeURIComponent(ticker)}&limit=10`,
    fetcher,
    { refreshInterval: 60_000 }
  );

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Latest Headlines</h2>
        <span className="text-[11px] text-slate-500">from Google News RSS (stored in DB)</span>
      </div>
      {isLoading && <p className="text-xs text-slate-500">Loading news...</p>}
      {error && <p className="text-xs text-rose-400">Failed to load news.</p>}
      {data && data.items.length === 0 && !isLoading && <p className="text-xs text-slate-500">No news in DB yet.</p>}
      <ul className="space-y-2 text-xs">
        {data?.items.map((n, idx) => {
          const date = n.published_at ? new Date(n.published_at) : null;
          const label =
            n.sentiment_label === "POS" ? "text-emerald-400" : n.sentiment_label === "NEG" ? "text-rose-400" : "text-slate-400";
          return (
            <li key={idx} className="border-b border-slate-800 pb-2 last:border-b-0 last:pb-0">
              <a
                href={n.url}
                target="_blank"
                rel="noreferrer"
                className="text-slate-100 hover:text-sky-300"
              >
                {n.title}
              </a>
              <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
                <span>{n.source}</span>
                <span className={label}>{n.sentiment_label || "NEU"}</span>
                <span>{date ? date.toLocaleString() : ""}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

