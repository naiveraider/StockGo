"use client";

import Link from "next/link";
import { MarketsStrip } from "../components/MarketsStrip";
import { HomeStocksPreview } from "../components/HomeStocksPreview";

export default function HomePage() {
  return (
    <div className="space-y-4">
      <MarketsStrip />

      <HomeStocksPreview />

      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <div className="flex flex-col gap-2">
          <h2 className="text-2xl font-semibold text-slate-900">StockGo Finance</h2>
          <p className="text-slate-600">
            Use the top search bar to open any ticker, browse the{" "}
            <Link className="text-yahooBlue hover:underline" href="/stocks">
              full US stock list
            </Link>
            , or check a ticker’s{" "}
            <Link className="text-yahooBlue hover:underline" href="/long-term">
              long-term bias
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  );
}

