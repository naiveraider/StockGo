"use client";

import useSWR from "swr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useMemo } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

type StockSummary = {
  ticker: string;
  exchange?: string | null;
  name?: string | null;
  last?: number | null;
  change?: number | null;
  change_percent?: number | null;
  market_cap?: number | null;
};

type Page = {
  items: StockSummary[];
  limit: number;
  offset: number;
  total: number;
};

type SearchInstrument = {
  ticker: string;
  exchange?: string | null;
  name?: string | null;
};

const limit = 20;

function fmt(n?: number | null, digits = 2) {
  if (n === undefined || n === null) return "-";
  return n.toFixed(digits);
}

function fmtCap(n?: number | null) {
  if (n === undefined || n === null) return "-";
  const abs = Math.abs(n);
  if (abs >= 1e12) return (n / 1e12).toFixed(2) + "T";
  if (abs >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (abs >= 1e6) return (n / 1e6).toFixed(2) + "M";
  return n.toFixed(0);
}

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

export function HomeStocksPreview() {
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

  const { data, error, isLoading } = useSWR<Page>(
    `${API_BASE}/v1/stocks/summary?${queryParams}`,
    fetcher,
    { refreshInterval: 120_000 }
  );

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-2">
        <div className="text-sm font-semibold text-slate-900">All US stocks (preview)</div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setOffset(0);
            }}
            placeholder="Filter by name or symbol"
            className="w-40 rounded border border-slate-300 px-2 py-1.5 text-xs outline-none focus:border-yahooBlue"
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
            className="rounded border border-slate-300 bg-white px-2 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Search & go to quote
          </button>
          <Link
            href="/stocks"
            className="text-xs font-medium text-yahooBlue hover:underline"
          >
            Open Screener
          </Link>
        </div>
      </div>
      {searchQuery && total > 0 && (
        <div className="px-4 py-1 text-xs text-slate-600">
          Filter: &quot;{searchQuery}&quot; — {total} result{total !== 1 ? "s" : ""}
        </div>
      )}
      {error && <div className="px-4 py-2 text-xs text-rose-600">Failed to load stocks preview.</div>}
      {isLoading && <div className="px-4 py-2 text-xs text-slate-500">Loading…</div>}
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead className="bg-slate-50 text-left text-[11px] text-slate-500">
            <tr>
              <th className="px-4 py-2">Symbol</th>
              <th className="px-4 py-2">Name</th>
              <th className="px-4 py-2 text-right">Last</th>
              <th className="px-4 py-2 text-right">Change</th>
              <th className="px-4 py-2 text-right">Market cap</th>
              <th className="px-4 py-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => {
              const ch = s.change ?? 0;
              const pct = s.change_percent ?? 0;
              const up = ch >= 0;
              const color = up ? "text-emerald-600" : "text-rose-600";
              return (
                <tr key={s.ticker} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2 font-semibold text-slate-900">
                    <Link className="text-yahooBlue hover:underline" href={`/quote/${s.ticker}`}>
                      {s.ticker}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-700">{s.name || "-"}</td>
                  <td className="px-4 py-2 text-right text-slate-900">{fmt(s.last, 2)}</td>
                  <td className={`px-4 py-2 text-right ${color}`}>
                    {ch >= 0 ? "+" : ""}
                    {fmt(ch, 2)} ({pct >= 0 ? "+" : ""}
                    {fmt(pct, 2)}%)
                  </td>
                  <td className="px-4 py-2 text-right text-slate-700">{fmtCap(s.market_cap)}</td>
                  <td className="px-4 py-2 text-right">
                    <button
                      type="button"
                      onClick={async () => {
                        await fetch(
                          `${API_BASE}/v1/screener/add?ticker=${encodeURIComponent(s.ticker)}`,
                          { method: "POST" }
                        );
                        router.push(`/stocks?symbol=${encodeURIComponent(s.ticker)}`);
                      }}
                      className="rounded border border-slate-300 px-2 py-1 text-[11px] text-slate-700 hover:bg-slate-100"
                    >
                      Add to Screener
                    </button>
                  </td>
                </tr>
              );
            })}
            {items.length === 0 && !isLoading && (
              <tr>
                <td className="px-4 py-4 text-slate-500" colSpan={6}>
                  {searchQuery
                    ? "No matches. Try a different search or clear the filter."
                    : "No stocks yet. Run universe sync in Screener first."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 px-4 py-2">
        <div className="text-xs text-slate-600">
          Showing {from}–{to} of {total}
          {totalPages > 1 && ` · Page ${Math.floor(offset / limit) + 1} of ${totalPages}`}
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset((o) => Math.max(0, o - limit))}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs disabled:opacity-50 hover:bg-slate-50"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={offset + limit >= total}
            onClick={() => setOffset((o) => o + limit)}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs disabled:opacity-50 hover:bg-slate-50"
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
    </section>
  );
}
