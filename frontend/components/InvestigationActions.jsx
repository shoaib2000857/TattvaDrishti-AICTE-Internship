import { useEffect, useState } from "react";
import { fetchEvidenceReview, findSimilarMessages } from "@/lib/api";

function formatObservedAt(value) {
  if (!value) return "Time unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Time unavailable" : date.toLocaleString();
}

function EvidenceList({ items, marker, empty }) {
  if (!items?.length) return <p className="text-xs leading-relaxed text-slate-500">{empty}</p>;
  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={`${item.source}-${item.label}`} className="flex gap-3 text-sm">
          <span className="mt-0.5 text-base leading-none text-emerald-300">{marker}</span>
          <div>
            <p className="font-medium text-slate-100">{item.label}</p>
            <p className="mt-1 text-xs leading-relaxed text-slate-400">{item.description}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function InvestigationActions({ intakeId, onOpenCase }) {
  const [scope, setScope] = useState("current_batch");
  const [similar, setSimilar] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [similarError, setSimilarError] = useState("");
  const [evidenceError, setEvidenceError] = useState("");

  useEffect(() => {
    setSimilar(null);
    setEvidence(null);
    setSimilarError("");
    setEvidenceError("");
  }, [intakeId]);

  const searchSimilar = async () => {
    setSimilarLoading(true);
    setSimilarError("");
    try {
      setSimilar(await findSimilarMessages(intakeId, { scope }));
    } catch (error) {
      setSimilarError(error.message || "Unable to search analysed messages.");
    } finally {
      setSimilarLoading(false);
    }
  };

  const reviewEvidence = async () => {
    setEvidenceLoading(true);
    setEvidenceError("");
    try {
      setEvidence(await fetchEvidenceReview(intakeId));
    } catch (error) {
      setEvidenceError(error.message || "Unable to assemble the evidence review.");
    } finally {
      setEvidenceLoading(false);
    }
  };

  return (
    <section className="rounded-2xl border border-cyan-400/15 bg-cyan-400/[0.035] px-5 py-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-cyan-300">Investigation actions</p>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-300">
            Search only when needed, or review the existing signals behind this assessment.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={searchSimilar}
            disabled={similarLoading}
            className="inline-flex items-center justify-center rounded-xl border border-cyan-400/35 bg-cyan-400/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-wait disabled:opacity-60"
          >
            {similarLoading ? "Searching analyzed messages…" : "Find Similar Messages"}
          </button>
          <button
            type="button"
            onClick={reviewEvidence}
            disabled={evidenceLoading}
            className="inline-flex items-center justify-center rounded-xl border border-emerald-400/35 bg-emerald-400/10 px-4 py-2 text-sm font-semibold text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-wait disabled:opacity-60"
          >
            {evidenceLoading ? "Reviewing evidence…" : "Review Evidence"}
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-400">
        <label htmlFor={`similar-scope-${intakeId}`}>Search scope</label>
        <select
          id={`similar-scope-${intakeId}`}
          value={scope}
          onChange={(event) => setScope(event.target.value)}
          className="rounded-lg border border-white/10 bg-slate-950/70 px-3 py-1.5 text-xs text-slate-200 outline-none focus:border-cyan-400/60"
        >
          <option value="current_batch">Current batch / dataset</option>
          <option value="all_cases">All analyzed cases</option>
        </select>
      </div>

      {similarError && <p role="alert" className="mt-4 text-sm text-rose-300">{similarError}</p>}
      {similar && (
        <div className="mt-5 border-t border-white/10 pt-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200">Related content</h3>
              <p className="mt-1 text-sm text-cyan-100">{similar.message}</p>
            </div>
            <span className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-3 py-1 text-xs text-cyan-100">
              {similar.scope === "current_batch" ? "Current batch" : "All analyzed cases"}
            </span>
          </div>
          {similar.results?.length > 0 && (
            <div className="mt-4 space-y-3">
              {similar.results.map((result) => (
                <button
                  type="button"
                  key={result.intake_id}
                  onClick={() => onOpenCase?.(result.intake_id)}
                  className="w-full rounded-xl border border-white/10 bg-slate-950/55 p-4 text-left transition hover:border-cyan-400/35 hover:bg-slate-900/80 focus:outline-none focus:ring-2 focus:ring-cyan-400/40"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <p className="max-w-2xl text-sm leading-relaxed text-slate-100">{result.text_preview}</p>
                    <span className="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-2.5 py-1 font-mono text-xs font-semibold text-cyan-100">
                      {Math.round(result.similarity * 100)}% similar
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400">
                    <span>{result.platform || "Platform unavailable"}</span>
                    <span>{result.actor_id || "Actor unavailable"}</span>
                    <span>{result.region || "Region unavailable"}</span>
                    <span>{formatObservedAt(result.observed_at)}</span>
                    <span className="text-amber-200">{result.classification || "Priority unavailable"}</span>
                    {result.narrative && <span className="text-purple-200">Narrative: {result.narrative}</span>}
                  </div>
                  <div className="mt-3 border-t border-white/5 pt-3">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">Why related</p>
                    <ul className="mt-2 space-y-1 text-xs text-slate-300">
                      {(result.matching_reasons || []).map((reason) => <li key={reason}>• {reason}</li>)}
                    </ul>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {evidenceError && <p role="alert" className="mt-4 text-sm text-rose-300">{evidenceError}</p>}
      {evidence && (
        <div className="mt-5 border-t border-white/10 pt-5">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-200">Evidence review</h3>
          <div className="mt-4 grid gap-4 xl:grid-cols-2">
            <article className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.045] p-4">
              <h4 className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-200">Evidence supporting concern</h4>
              <div className="mt-4"><EvidenceList items={evidence.supporting} marker="✓" empty="No stored signal is currently supporting this concern." /></div>
            </article>
            <article className="rounded-xl border border-amber-400/20 bg-amber-400/[0.04] p-4">
              <h4 className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-200">Reducing concern / uncertainty</h4>
              <div className="mt-4"><EvidenceList items={[...(evidence.counter || []), ...(evidence.uncertainties || [])]} marker="•" empty="No additional uncertainty notes are available." /></div>
            </article>
          </div>
          {evidence.signals_disagree && (
            <div className="mt-4 rounded-xl border border-purple-400/25 bg-purple-400/10 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-purple-200">Signals disagree</p>
              <p className="mt-2 text-xs leading-relaxed text-purple-100">{evidence.disagreement_summary}</p>
            </div>
          )}
          <div className="mt-4 rounded-xl border border-white/10 bg-slate-950/55 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-300">Analyst judgement required</p>
            <p className="mt-2 text-xs leading-relaxed text-slate-400">{evidence.analyst_note}</p>
          </div>
        </div>
      )}
    </section>
  );
}
