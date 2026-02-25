"use client";

import { useState } from "react";

interface Props {
  initialTicker?: string;
  onSubmit(ticker: string): void;
}

export function TickerSearch({ initialTicker = "TSLA", onSubmit }: Props) {
  const [value, setValue] = useState(initialTicker);

  return (
    <form
      className="mb-4 flex gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        const t = value.trim().toUpperCase();
        if (t) onSubmit(t);
      }}
    >
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="e.g. TSLA, AAPL, MSFT"
        className="flex-1 rounded border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 outline-none focus:border-sky-500"
      />
      <button
        type="submit"
        className="rounded bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 active:bg-sky-700"
      >
        Analyze
      </button>
    </form>
  );
}

