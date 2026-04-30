"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { authedJson, fetchCurrentUser, getStoredToken, hasMinRole, type UserRole } from "../../lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

type ShortTermIdea = {
  ticker: string;
  name?: string | null;
  why_now: string;
  catalyst: string;
  catalyst_date?: string | null;
  technical_setup: string;
  bull_case: string;
  bear_case: string;
  entry_range: string;
  exit_strategy: string;
  risk_level: "low" | "medium" | "high";
  confidence: number;
};

type ShortTermIdeasResponse = {
  generated_at: string;
  source_model?: string | null;
  fallback_used: boolean;
  candidates_considered: number;
  ideas: ShortTermIdea[];
};

export default function ShortTermPickPage() {
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

  const { data, error, isLoading } = useSWR<ShortTermIdeasResponse>(
    access === "ok" && token
      ? `${API_BASE}/v1/screener/short-term-ideas`
      : null,
    (url: string) => authedJson<ShortTermIdeasResponse>(url, token as string)
  );

  const ideas = data?.ideas ?? [];

  if (access === "checking") {
    return <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">Checking access...</div>;
  }

  if (access === "need-login") {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-slate-700">
        Please <Link className="text-yahooBlue hover:underline" href="/login">login</Link> to access Short-term pick.
      </div>
    );
  }

  if (access === "forbidden") {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
        Short-term pick requires at least the Advanced role.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Short-term picks</h2>
            <p className="text-sm text-slate-500">
              3 high-conviction U.S. swing trade ideas for a 2-4 week holding period, generated in the background and served from the database.
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
        {error && <p className="mt-2 text-sm text-rose-600">Failed to load short-term ideas.</p>}
        {isLoading && <p className="mt-2 text-sm text-slate-500">Loading...</p>}
      </div>

      {ideas.length === 0 && !isLoading ? (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
          No qualified short-term ideas are available right now.
        </div>
      ) : (
        <div className="grid gap-4">
          {ideas.map((idea) => (
            <article key={idea.ticker} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Link className="text-xl font-semibold text-yahooBlue hover:underline" href={`/quote/${idea.ticker}`}>
                      {idea.ticker}
                    </Link>
                    <span className="text-sm text-slate-500">{idea.name || "Unknown company"}</span>
                  </div>
                  <p className="mt-2 max-w-3xl text-sm text-slate-700">{idea.why_now}</p>
                </div>
                <div className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700">
                  Confidence {Math.round(idea.confidence * 100)}%
                </div>
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <section className="rounded-lg bg-slate-50 p-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Catalyst</div>
                  <p className="mt-2 text-sm text-slate-800">{idea.catalyst}</p>
                  <p className="mt-2 text-xs text-slate-500">
                    Expected date: {idea.catalyst_date || "Not available"}
                  </p>
                </section>
                <section className="rounded-lg bg-slate-50 p-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Technical setup</div>
                  <p className="mt-2 text-sm text-slate-800">{idea.technical_setup}</p>
                </section>
                <section className="rounded-lg bg-emerald-50 p-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Bull case</div>
                  <p className="mt-2 text-sm text-emerald-900">{idea.bull_case}</p>
                </section>
                <section className="rounded-lg bg-rose-50 p-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-rose-700">Bear case</div>
                  <p className="mt-2 text-sm text-rose-900">{idea.bear_case}</p>
                </section>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-3">
                <div className="rounded border border-slate-200 p-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Entry range</div>
                  <p className="mt-1 text-sm text-slate-900">{idea.entry_range}</p>
                </div>
                <div className="rounded border border-slate-200 p-3 md:col-span-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Exit strategy</div>
                  <p className="mt-1 text-sm text-slate-900">{idea.exit_strategy}</p>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
                <span className="inline-flex rounded-full bg-slate-100 px-3 py-1 font-medium capitalize text-slate-700">
                  Risk: {idea.risk_level}
                </span>
                <Link className="text-yahooBlue hover:underline" href={`/quote/${idea.ticker}`}>
                  Open quote
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
