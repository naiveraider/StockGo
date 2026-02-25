"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { AuthBar } from "./AuthBar";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface Instrument {
  ticker: string;
  exchange?: string | null;
  name?: string | null;
}

export function TopNav() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);

  const query = q.trim();
  const shouldFetch = query.length >= 1;
  const { data } = useSWR<Instrument[]>(
    shouldFetch ? `${API_BASE}/v1/stocks/search?q=${encodeURIComponent(query)}&limit=8` : null,
    fetcher,
    { keepPreviousData: true }
  );

  const suggestions = useMemo(() => data || [], [data]);

  useEffect(() => {
    if (!shouldFetch) setOpen(false);
    else setOpen(true);
  }, [shouldFetch]);

  function goTicker(ticker: string) {
    setOpen(false);
    setQ("");
    router.push(`/quote/${encodeURIComponent(ticker)}`);
  }

  return (
    <div className="sticky top-0 z-50 border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-semibold text-yahooBlue">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded bg-yahooBlue text-white">
            Y
          </span>
          <span className="hidden sm:block">StockGo Finance</span>
        </Link>

        <nav className="hidden md:flex items-center gap-4 text-sm text-slate-700">
          <Link className="hover:text-yahooBlue" href="/">
            Home
          </Link>
          <Link className="hover:text-yahooBlue" href="/stocks">
            Short-term bias
          </Link>
          <Link className="hover:text-yahooBlue" href="/long-term">
            Long-term bias
          </Link>
        </nav>

        <div className="relative flex-1">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onFocus={() => shouldFetch && setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 120)}
            placeholder="Search US stocks (e.g. TSLA, AAPL)"
            className="w-full rounded-full border border-slate-300 bg-slate-50 px-4 py-2 text-sm outline-none focus:border-yahooBlue focus:ring-2 focus:ring-blue-100"
          />
          {open && suggestions.length > 0 && (
            <div className="absolute mt-2 w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
              {suggestions.map((s) => (
                <button
                  key={s.ticker}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => goTicker(s.ticker)}
                  className="flex w-full items-start justify-between gap-3 px-4 py-2 text-left hover:bg-slate-50"
                >
                  <div>
                    <div className="text-sm font-medium text-slate-900">{s.ticker}</div>
                    <div className="text-xs text-slate-500 line-clamp-1">{s.name || ""}</div>
                  </div>
                  <div className="text-xs text-slate-400">{s.exchange || ""}</div>
                </button>
              ))}
              <div className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
                Press Enter to open ticker (manual).
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          <AuthBar />
        </div>
      </div>
    </div>
  );
}

