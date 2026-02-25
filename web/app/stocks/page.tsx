"use client";

import useSWR from "swr";
import { useState, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

type ShortTermRow = {
  ticker: string;
  name?: string | null;
  bias: "UP" | "DOWN" | "NEUTRAL";
  confidence: number;
  updated_at: string;
};

type ShortTermPage = {
  items: ShortTermRow[];
  total: number;
};

type SearchInstrument = {
  ticker: string;
  exchange?: string | null;
  name?: string | null;
};

const limit = 50;

function SearchDialog({
  open,
  onClose,
  onSelect,
}: {
  open: boolean;
  onClose: () => void;
  onSelect: (ticker: string) => void;
}) {
  const [q, setQ] = useState("");
  const query = q.trim();
  const shouldFetch = query.length >= 1;
  const { data, isLoading } = useSWR<SearchInstrument[]>(
    shouldFetch ? `${API_BASE}/v1/stocks/search?q=${encodeURIComponent(query)}&limit=20` : null,
    fetcher,
    { keepPreviousData: true }
  );
  const results = data ?? [];

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-lg border border-slate-200 bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-slate-200 px-4 py-3">
          <h3 className="text-sm font-semibold text-slate-900">Search by name or symbol</h3>
          <input
            type="text"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="e.g. AAPL or Apple"
            className="mt-2 w-full rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:border-yahooBlue focus:ring-1 focus:ring-yahooBlue"
            autoFocus
          />
        </div>
        <div className="max-h-72 overflow-y-auto">
          {isLoading && (
            <div className="px-4 py-3 text-sm text-slate-500">Loading…</div>
          )}
          {!shouldFetch && (
            <div className="px-4 py-3 text-sm text-slate-500">Type to search by symbol or company name.</div>
          )}
          {shouldFetch && !isLoading && results.length === 0 && (
            <div className="px-4 py-3 text-sm text-slate-500">No matches.</div>
          )}
          {results.map((s) => (
            <button
              key={s.ticker}
              type="button"
              onClick={() => {
                onSelect(s.ticker);
                onClose();
              }}
              className="flex w-full items-center justify-between gap-3 border-t border-slate-100 px-4 py-2 text-left hover:bg-slate-50"
            >
              <span className="font-medium text-slate-900">{s.ticker}</span>
              <span className="truncate text-sm text-slate-600">{s.name || ""}</span>
            </button>
          ))}
        </div>
        <div className="border-t border-slate-200 px-4 py-2 text-right">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export default function StocksPage() {
  const router = useRouter();
  const [offset, setOffset] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);

  const queryParams = useMemo(() => {
    const p = new URLSearchParams();
    p.set("limit", String(limit));
    p.set("offset", String(offset));
    if (searchQuery.trim()) p.set("q", searchQuery.trim());
    return p.toString();
  }, [offset, searchQuery]);

  const url = `${API_BASE}/v1/screener/short-term?${queryParams}`;
  const { data, error, isLoading } = useSWR<ShortTermPage>(url, fetcher);
  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const pageIndex = Math.floor(offset / limit);
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Short-term bias</h2>
            <p className="text-sm text-slate-500">
              Stocks that have a completed short-term analysis run.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setOffset(0);
              }}
              placeholder="Filter by name or symbol"
              className="rounded border border-slate-300 px-3 py-2 text-sm w-48 outline-none focus:border-yahooBlue"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => { setSearchQuery(""); setOffset(0); }}
                className="text-xs text-slate-500 hover:underline"
              >
                Clear
              </button>
            )}
            <button
              type="button"
              onClick={() => setSearchOpen(true)}
              className="rounded border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Search & go to quote
            </button>
          </div>
        </div>
        {searchQuery && (
          <p className="mt-2 text-sm text-slate-600">
            Filter: &quot;{searchQuery}&quot; — {total} result{total !== 1 ? "s" : ""}
          </p>
        )}
        {error && <p className="mt-2 text-sm text-rose-600">Failed to load stocks.</p>}
        {isLoading && <p className="mt-2 text-sm text-slate-500">Loading…</p>}
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
            {items.map((it) => {
              const biasColor =
                it.bias === "UP"
                  ? "text-emerald-600"
                  : it.bias === "DOWN"
                    ? "text-rose-600"
                    : "text-amber-600";
              return (
                <tr key={it.ticker} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">
                    <Link className="text-yahooBlue hover:underline" href={`/quote/${it.ticker}`}>
                      {it.ticker}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{it.name || "-"}</td>
                  <td className={`px-4 py-3 font-semibold ${biasColor}`}>{it.bias}</td>
                  <td className="px-4 py-3 text-slate-700">{Math.round(it.confidence * 100)}%</td>
                  <td className="px-4 py-3 text-slate-500">
                    {new Date(it.updated_at).toLocaleString()}
                  </td>
                </tr>
              );
            })}
            {items.length === 0 && !isLoading && (
              <tr>
                <td className="px-4 py-6 text-slate-500" colSpan={5}>
                  {searchQuery
                    ? "No matches. Try a different search or clear the filter."
                    : "No completed short-term analyses yet. Add tickers from the homepage."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-slate-600">
          Showing {from}–{to} of {total}
          {totalPages > 1 && ` · Page ${pageIndex + 1} of ${totalPages}`}
        </div>
        <div className="flex items-center gap-2">
          <button
            disabled={offset === 0}
            onClick={() => setOffset((o) => Math.max(0, o - limit))}
            className="rounded border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50 hover:bg-slate-50"
          >
            Previous
          </button>
          <button
            disabled={offset + limit >= total}
            onClick={() => setOffset((o) => o + limit)}
            className="rounded border border-slate-300 bg-white px-3 py-2 text-sm disabled:opacity-50 hover:bg-slate-50"
          >
            Next
          </button>
        </div>
      </div>

      <SearchDialog
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onSelect={(ticker) => {
          setSearchOpen(false);
          router.push(`/quote/${ticker}`);
        }}
      />
    </div>
  );
}
