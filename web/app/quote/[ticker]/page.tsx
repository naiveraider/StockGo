"use client";

import { useMemo } from "react";
import Link from "next/link";
import useSWR from "swr";
import { NewsListCard, PredictionCard, StockOverviewCard } from "../../../components/Cards";
import { IndicatorChartCard, PriceChartCard } from "../../../components/ChartCards";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function QuotePage({ params }: { params: { ticker: string } }) {
  const ticker = useMemo(() => (params.ticker || "TSLA").toUpperCase(), [params.ticker]);

  // Preload universe display name if present
  const { data: meta } = useSWR<{ ticker: string; name?: string }[]>(
    `${API_BASE}/v1/stocks/search?q=${encodeURIComponent(ticker)}&limit=1`,
    fetcher
  );
  const name = meta?.[0]?.name;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-xs text-slate-500">Quote</div>
            <h2 className="text-2xl font-semibold text-slate-900">
              {ticker}{" "}
              {name ? <span className="ml-2 text-base font-normal text-slate-500">{name}</span> : null}
            </h2>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <Link className="text-yahooBlue hover:underline" href={`/quote/${ticker}/long-term`}>
              Long-term bias →
            </Link>
          </div>
        </div>
      </div>

      <section className="grid gap-4 md:grid-cols-2">
        <StockOverviewCard ticker={ticker} />
        <PredictionCard ticker={ticker} />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <PriceChartCard ticker={ticker} />
        <IndicatorChartCard ticker={ticker} />
      </section>

      <section className="grid gap-4">
        <NewsListCard ticker={ticker} />
      </section>
    </div>
  );
}

