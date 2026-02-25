"use client";

import useSWR from "swr";
import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

type MiniPoint = { ts: string; value: number };
type MarketItem = {
  symbol: string;
  name: string;
  last?: number | null;
  change?: number | null;
  change_percent?: number | null;
  mini: MiniPoint[];
};

type MarketsOverview = { items: MarketItem[] };

function formatNumber(n?: number | null, digits = 2) {
  if (n === undefined || n === null) return "-";
  return n.toFixed(digits);
}

export function MarketsStrip() {
  const { data, error, isLoading } = useSWR<MarketsOverview>(
    `${API_BASE}/v1/markets/overview`,
    fetcher,
    { refreshInterval: 60_000 }
  );

  const items = data?.items ?? [];

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs font-semibold text-slate-700">US Markets snapshot</div>
        {isLoading && <div className="text-[11px] text-slate-400">Refreshing…</div>}
        {error && <div className="text-[11px] text-rose-500">Failed to load markets</div>}
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-6">
        {items.map((m) => {
          const ch = m.change ?? 0;
          const pct = m.change_percent ?? 0;
          const up = ch >= 0;
          const colorMain = up ? "text-emerald-600" : "text-rose-600";
          const colorPct = up ? "text-emerald-500" : "text-rose-500";

          return (
            <div
              key={m.symbol}
              className="flex flex-col justify-between rounded border border-dashed border-slate-200 px-2 py-2"
            >
              <div className="text-xs font-semibold text-yahooBlue">{m.name}</div>
              <div className="mt-1 text-sm font-semibold text-slate-900">
                {formatNumber(m.last, 2)}
              </div>
              <div className={`text-xs ${colorMain}`}>
                {ch >= 0 ? "+" : ""}
                {formatNumber(ch, 2)}
              </div>
              <div className={`text-[11px] ${colorPct}`}>
                ({pct >= 0 ? "+" : ""}
                {formatNumber(pct, 2)}%)
              </div>
              <div className="mt-1 h-10">
                {m.mini && m.mini.length > 1 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={m.mini}>
                      <YAxis hide domain={["dataMin", "dataMax"]} />
                      <Area
                        type="monotone"
                        dataKey="value"
                        stroke={up ? "#16a34a" : "#dc2626"}
                        fill={up ? "#bbf7d0" : "#fecaca"}
                        fillOpacity={0.5}
                        strokeWidth={1}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full rounded bg-slate-100" />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

