"use client";

import { useEffect, useState } from "react";
import { askAnalystCopilot, fetchNarrativeTrace } from "@/lib/api";

const prompts = [
  "Summarise why this cluster was flagged.",
  "Show the strongest evidence linking these accounts.",
  "What changed in the last 2 hours?",
  "Trace the origin of this narrative.",
];

export default function NarrativeTracker({ intakeId }) {
  const [trace, setTrace] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState(prompts[0]);
  const [answer, setAnswer] = useState(null);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    setTrace(null);
    setAnswer(null);
    if (!intakeId) return;
    setLoading(true);
    setError("");
    fetchNarrativeTrace(intakeId)
      .then(setTrace)
      .catch((requestError) => setError(requestError.message || "Narrative trace unavailable"))
      .finally(() => setLoading(false));
  }, [intakeId]);

  const ask = async (selectedQuestion = question) => {
    if (!intakeId || !selectedQuestion.trim()) return;
    setQuestion(selectedQuestion);
    setAsking(true);
    setError("");
    try {
      setAnswer(await askAnalystCopilot({ question: selectedQuestion, intake_id: intakeId }));
    } catch (requestError) {
      setError(requestError.message || "Copilot unavailable");
    } finally {
      setAsking(false);
    }
  };

  if (!intakeId) {
    return <section className="rounded-3xl border border-white/10 bg-slate-900/60 p-8 text-center text-sm text-slate-400">Select an analysed case to trace its cross-platform narrative and question the evidence.</section>;
  }

  return (
    <section className="min-w-0 overflow-hidden rounded-3xl border border-fuchsia-400/20 bg-slate-900/75 p-5 sm:p-7">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
        <div className="min-w-0"><p className="text-xs font-semibold uppercase tracking-[0.3em] text-fuchsia-300">Cross-platform narrative tracker</p><h2 className="mt-2 break-words text-2xl font-semibold text-white">{trace?.label || (loading ? "Mapping narrative…" : "Narrative evidence")}</h2></div>
        {trace ? <span className="max-w-full truncate rounded-full border border-white/10 bg-slate-950/60 px-3 py-2 font-mono text-xs text-slate-400">{trace.narrative_id}</span> : null}
      </div>
      {error ? <p className="mt-4 break-words rounded-xl border border-rose-400/20 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</p> : null}

      {trace ? (
        <>
          <div className="mt-6 grid min-w-0 gap-4 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <div className="min-w-0 rounded-2xl border border-fuchsia-400/20 bg-fuchsia-500/[0.06] p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-fuchsia-300">Earliest observed lead</p>
              <p className="mt-3 break-words text-lg font-medium text-slate-100">{trace.origin.platform}{trace.origin.actor_id ? ` · ${trace.origin.actor_id}` : ""}</p>
              <p className="mt-1 text-sm text-slate-400">{new Date(trace.origin.observed_at).toLocaleString()}{trace.origin.region ? ` · ${trace.origin.region}` : ""}</p>
              <p className="mt-3 text-sm text-slate-300">Confidence {Math.round(trace.origin.confidence * 100)}%</p>
              <p className="mt-3 rounded-xl bg-slate-950/45 p-3 text-xs leading-relaxed text-amber-200">{trace.origin.caveat}</p>
            </div>
            <div className="min-w-0 rounded-2xl border border-white/10 bg-slate-950/45 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Platform movement</p>
              <div className="mt-5 flex min-w-0 flex-wrap items-center gap-2">
                {trace.platforms.map((platform, index) => <div key={platform} className="contents"><span className="max-w-full truncate rounded-xl border border-cyan-400/20 bg-cyan-500/10 px-4 py-2 text-sm capitalize text-cyan-200">{platform}</span>{index < trace.platforms.length - 1 ? <span className="text-slate-600">→</span> : null}</div>)}
              </div>
              <div className="mt-5 flex flex-wrap gap-4 text-sm text-slate-400"><span>{trace.observations.length} observations</span><span>{trace.actors.length} actors</span><span>{trace.velocity_per_hour.toFixed(1)} posts/hr</span><span>Acceleration {trace.acceleration >= 0 ? "+" : ""}{trace.acceleration.toFixed(2)}</span></div>
            </div>
          </div>

          <div className="mt-5 min-w-0 rounded-2xl border border-white/10 bg-slate-950/45 p-5">
            <h3 className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Observed propagation timeline</h3>
            <div className="mt-5 max-h-96 space-y-0 overflow-y-auto overflow-x-hidden pr-1">
              {trace.observations.map((item, index) => <div key={item.intake_id} className="grid min-w-0 grid-cols-[1.25rem_minmax(0,1fr)] gap-3"><div className="flex flex-col items-center"><span className="mt-1 h-3 w-3 shrink-0 rounded-full border-2 border-fuchsia-300 bg-slate-950" />{index < trace.observations.length - 1 ? <span className="h-full min-h-12 w-px bg-fuchsia-400/20" /> : null}</div><article className="min-w-0 pb-5"><div className="flex min-w-0 flex-wrap gap-x-3 gap-y-1 text-xs"><span className="font-semibold capitalize text-fuchsia-200">{item.platform}</span><span className="text-slate-500">{new Date(item.observed_at).toLocaleString()}</span>{item.actor_id ? <span className="max-w-full truncate text-cyan-300">{item.actor_id}</span> : null}</div><p className="mt-2 break-words text-sm leading-relaxed text-slate-300">{item.text_preview}</p>{item.similarity_to_previous != null ? <p className="mt-1 text-xs text-slate-500">{Math.round(item.similarity_to_previous * 100)}% similarity to previous observation</p> : null}</article></div>)}
            </div>
          </div>

          <div className="mt-5 grid min-w-0 gap-5 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <div className="min-w-0 rounded-2xl border border-white/10 bg-slate-950/45 p-5"><h3 className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Closest related content</h3><div className="mt-4 max-h-72 space-y-3 overflow-y-auto overflow-x-hidden">{trace.matches.slice(0, 10).map((match) => <article key={match.intake_id} className="min-w-0 rounded-xl border border-white/5 p-3"><div className="flex justify-between gap-3 text-xs"><span className="capitalize text-cyan-300">{match.platform} · {match.relationship}</span><span className="shrink-0 text-slate-400">{Math.round(match.similarity * 100)}%</span></div><p className="mt-2 break-words text-sm text-slate-300">{match.text_preview}</p></article>)}</div></div>
            <div className="min-w-0 rounded-2xl border border-emerald-400/20 bg-emerald-500/[0.04] p-5"><p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-300">Evidence-bounded analyst copilot</p><div className="mt-4 flex flex-wrap gap-2">{prompts.map((prompt) => <button key={prompt} onClick={() => ask(prompt)} className="max-w-full rounded-full border border-white/10 px-3 py-2 text-left text-xs text-slate-300 hover:border-emerald-400/40">{prompt}</button>)}</div><div className="mt-4 flex min-w-0 flex-col gap-2 sm:flex-row"><input value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => event.key === "Enter" && ask()} className="min-w-0 flex-1 rounded-xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-slate-100" /><button onClick={() => ask()} disabled={asking} className="shrink-0 rounded-xl bg-emerald-400 px-5 py-3 text-sm font-semibold text-slate-950 disabled:opacity-50">{asking ? "Checking…" : "Ask evidence"}</button></div>{answer ? <div className="mt-4 min-w-0 rounded-xl border border-emerald-400/20 bg-slate-950/50 p-4"><p className="break-words text-sm leading-relaxed text-slate-200">{answer.answer}</p><p className="mt-3 text-xs text-slate-500">Scope: {answer.scope} · {answer.citations.length} cited observations</p><ul className="mt-2 list-inside list-disc text-xs text-amber-200">{answer.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div> : null}</div>
          </div>
        </>
      ) : null}
    </section>
  );
}
