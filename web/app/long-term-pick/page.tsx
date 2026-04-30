"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { authedJson, fetchCurrentUser, getStoredToken, hasMinRole, type UserRole } from "../../lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type LongTermIdea = {
  ticker: string;
  name?: string | null;
  business_model: string;
  growth_drivers: string;
  competitive_advantage: string;
  risks_and_threats: string;
  valuation: string;
  why_outperform: string;
  confidence: number;
};

type LongTermIdeasResponse = {
  generated_at: string;
  source_model?: string | null;
  fallback_used: boolean;
  candidates_considered: number;
  ideas: LongTermIdea[];
};

export default function LongTermPickPage() {
  const [token, setToken] = useState<string | null>(null);
  const [access, setAccess] = useState<"checking" | "need-login" | "forbidden" | "ok">("checking");

  useEffect(() => {
    const init = async () => {
      const t = getStoredToken();
      if (!t) {
        setAccess("need-login");
        return;
      }
      const me = await fetchCurrentUser(API_BASE, t);
      if (!me) {
        setAccess("need-login");
        return;
      }
      if (!hasMinRole(me.role, "advanced" as UserRole)) {
        setAccess("forbidden");
        return;
      }
      setToken(t);
      setAccess("ok");
    };
    void init();
  }, []);

  const { data, error, isLoading } = useSWR<LongTermIdeasResponse>(
    access === "ok" && token
      ? `${API_BASE}/v1/screener/long-term-ideas`
      : null,
    (url: string) => authedJson<LongTermIdeasResponse>(url, token as string)
  );

  const ideas = data?.ideas ?? [];

  if (access === "checking") {
    return <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">Checking access...</div>;
  }

  if (access === "need-login") {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-slate-700">
        Please <Link className="text-yahooBlue hover:underline" href="/login">login</Link> to access Long-term pick.
      </div>
    );
  }

  if (access === "forbidden") {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
        Long-term pick requires at least the Advanced role.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Long-term picks</h2>
            <p className="text-sm text-slate-500">
              3 high-conviction U.S. compounder ideas for a 3-year horizon, refreshed in the background and read from the database.
            </p>
          </div>
        </div>
        {data && (
          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
            <span>Generated {new Date(data.generated_at).toLocaleString()}</span>
            <span>Candidate pool {data.candidates_considered}</span>
            <span>{data.fallback_used ? "Rule-based fallback" : "LLM-generated"}</span>
          </div>
        )}
        {error && <p className="mt-2 text-sm text-rose-600">Failed to load long-term ideas.</p>}
        {isLoading && <p className="mt-2 text-sm text-slate-500">Loading...</p>}
      </div>

      {ideas.length === 0 && !isLoading ? (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
          No qualified long-term ideas are available right now.
        </div>
      ) : (
        <div className="grid gap-4">
          {ideas.map((idea) => (
            <article key={idea.ticker} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link className="text-xl font-semibold text-yahooBlue hover:underline" href={`/quote/${idea.ticker}/long-term`}>
                      {idea.ticker}
                    </Link>
                    <span className="text-sm text-slate-500">{idea.name || "Unknown company"}</span>
                  </div>
                  <p className="mt-2 max-w-3xl text-sm text-slate-700">{idea.business_model}</p>
                </div>
                <div className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700">
                  Confidence {Math.round(idea.confidence * 100)}%
                </div>
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <section className="rounded-lg bg-slate-50 p-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Growth drivers</div>
                  <p className="mt-2 text-sm text-slate-800">{idea.growth_drivers}</p>
                </section>
                <section className="rounded-lg bg-slate-50 p-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Competitive advantage</div>
                  <p className="mt-2 text-sm text-slate-800">{idea.competitive_advantage}</p>
                </section>
                <section className="rounded-lg bg-amber-50 p-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-amber-700">Risks and threats</div>
                  <p className="mt-2 text-sm text-amber-950">{idea.risks_and_threats}</p>
                </section>
                <section className="rounded-lg bg-emerald-50 p-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Why it can outperform</div>
                  <p className="mt-2 text-sm text-emerald-950">{idea.why_outperform}</p>
                </section>
              </div>

              <div className="mt-4 rounded border border-slate-200 p-4">
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Valuation</div>
                <p className="mt-2 text-sm text-slate-900">{idea.valuation}</p>
              </div>

              <div className="mt-4 flex flex-wrap items-center justify-end gap-3 text-sm">
                <Link className="text-yahooBlue hover:underline" href={`/quote/${idea.ticker}/long-term`}>
                  Open long-term report
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
