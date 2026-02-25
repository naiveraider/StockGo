"use client";

import useSWR from "swr";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface ChartPoint {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma20?: number | null;
  ma200?: number | null;
  rsi14?: number | null;
  macd?: number | null;
  macd_signal?: number | null;
}

interface ChartResponse {
  ticker: string;
  timeframe: string;
  points: ChartPoint[];
}

function formatDateLabel(iso: string) {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export function PriceChartCard({ ticker }: { ticker: string }) {
  const { data, error, isLoading } = useSWR<ChartResponse>(
    `${API_BASE}/v1/stock/chart?ticker=${encodeURIComponent(ticker)}&days=180&timeframe=1d`,
    fetcher,
    { refreshInterval: 60_000 }
  );

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Price &amp; Moving Averages</h2>
        <span className="text-[11px] text-slate-500">Daily close, MA20, MA200</span>
      </div>
      {isLoading && <p className="text-xs text-slate-500">Loading chart...</p>}
      {error && <p className="text-xs text-rose-400">Failed to load chart.</p>}
      {data && data.points.length > 0 && (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.points}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="ts"
                tickFormatter={formatDateLabel}
                tick={{ fontSize: 10, fill: "#9ca3af" }}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "#9ca3af" }}
                stroke="#374151"
                domain={["auto", "auto"]}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "#020617", borderColor: "#1f2937", fontSize: 11 }}
                labelFormatter={(v) => new Date(v).toLocaleDateString()}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Area
                type="monotone"
                dataKey="close"
                name="Close"
                stroke="#38bdf8"
                fill="#0f172a"
                fillOpacity={0.4}
              />
              <Line
                type="monotone"
                dataKey="ma20"
                name="MA20"
                stroke="#22c55e"
                dot={false}
                strokeWidth={1.2}
              />
              <Line
                type="monotone"
                dataKey="ma200"
                name="MA200"
                stroke="#f97316"
                dot={false}
                strokeWidth={1.2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}

export function IndicatorChartCard({ ticker }: { ticker: string }) {
  const { data, error, isLoading } = useSWR<ChartResponse>(
    `${API_BASE}/v1/stock/chart?ticker=${encodeURIComponent(ticker)}&days=180&timeframe=1d`,
    fetcher,
    { refreshInterval: 60_000 }
  );

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">RSI &amp; MACD</h2>
        <span className="text-[11px] text-slate-500">Daily indicators</span>
      </div>
      {isLoading && <p className="text-xs text-slate-500">Loading indicators...</p>}
      {error && <p className="text-xs text-rose-400">Failed to load indicators.</p>}
      {data && data.points.length > 0 && (
        <>
          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.points}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis
                  dataKey="ts"
                  tickFormatter={formatDateLabel}
                  tick={{ fontSize: 9, fill: "#9ca3af" }}
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fontSize: 9, fill: "#9ca3af" }}
                  stroke="#374151"
                />
                <Tooltip
                  contentStyle={{ backgroundColor: "#020617", borderColor: "#1f2937", fontSize: 11 }}
                  labelFormatter={(v) => new Date(v).toLocaleDateString()}
                />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                <Line
                  type="monotone"
                  dataKey="rsi14"
                  name="RSI14"
                  stroke="#eab308"
                  dot={false}
                  strokeWidth={1.2}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="h-32">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.points}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis
                  dataKey="ts"
                  tickFormatter={formatDateLabel}
                  tick={{ fontSize: 9, fill: "#9ca3af" }}
                />
                <YAxis tick={{ fontSize: 9, fill: "#9ca3af" }} stroke="#374151" />
                <Tooltip
                  contentStyle={{ backgroundColor: "#020617", borderColor: "#1f2937", fontSize: 11 }}
                  labelFormatter={(v) => new Date(v).toLocaleDateString()}
                />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                <Line
                  type="monotone"
                  dataKey="macd"
                  name="MACD"
                  stroke="#38bdf8"
                  dot={false}
                  strokeWidth={1.2}
                />
                <Line
                  type="monotone"
                  dataKey="macd_signal"
                  name="Signal"
                  stroke="#f97316"
                  dot={false}
                  strokeWidth={1.0}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </section>
  );
}

