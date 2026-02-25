"use client";

import { useState } from "react";
import Link from "next/link";

export default function LongTermLanding() {
  const [ticker, setTicker] = useState("TSLA");
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="text-xl font-semibold text-slate-900">Long-term bias</h2>
        <p className="mt-1 text-sm text-slate-600">Enter a ticker to open its long-term bias page.</p>
        <div className="mt-3 flex gap-2">
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            className="w-40 rounded border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-yahooBlue"
            placeholder="e.g. TSLA"
          />
          <Link
            href={`/quote/${ticker.trim().toUpperCase()}/long-term`}
            className="rounded bg-yahooBlue px-4 py-2 text-sm font-medium text-white hover:opacity-95"
          >
            View
          </Link>
        </div>
      </div>
    </div>
  );
}

