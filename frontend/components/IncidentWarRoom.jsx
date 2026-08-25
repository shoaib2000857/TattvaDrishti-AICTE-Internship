"use client";

import { useEffect, useState } from "react";
import { fetchWarRoom } from "@/lib/api";

const statusTone = {
  accelerating: "border-rose-400/30 bg-rose-500/10 text-rose-200",
  emerging: "border-amber-400/30 bg-amber-500/10 text-amber-200",
  stable: "border-emerald-400/30 bg-emerald-500/10 text-emerald-200",
};

export default function IncidentWarRoom({ refreshKey }) {
  const [snapshot, setSnapshot] = useState(null);
  const [title, setTitle] = useState("Live Influence Incident");
  const [query, setQuery] = useState("");
  const [windowHours, setWindowHours] = useState(168);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setSnapshot(await fetchWarRoom({ title, query, windowHours }));
    } catch (requestError) {
      setError(requestError.message || "War room unavailable");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const maxTimeline = Math.max(1, ...(snapshot?.timeline || []).map((item) => item.posts));

  return (
    <section className="min-w-0 overflow-hidden rounded-3xl border border-cyan-400/20 bg-slate-900/75 p-5 shadow-2xl shadow-cyan-950/20 sm:p-7">
      <div className="flex min-w-0 flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-cyan-300">Incident command</p>
          <h2 className="mt-2 break-words text-2xl font-semibold text-white">{snapshot?.title || title}</h2>
          <p className="mt-2 text-sm text-slate-400">Live cross-platform narrative posture · refreshes every 30 seconds</p>
        </div>
        <div className="grid min-w-0 gap-3 sm:grid-cols-[minmax(12rem,1fr)_minmax(10rem,1fr)_8rem_auto]">
          <input value={title} onChange={(event) => setTitle(event.target.value)} aria-label="Incident title" className="min-w-0 rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100" placeholder="Incident title" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} aria-label="Evidence filter" className="min-w-0 rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100" placeholder="Filter evidence" />
          <select value={windowHours} onChange={(event) => setWindowHours(Number(event.target.value))} className="rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-slate-100">
            <option value={24}>24 hours</option><option value={168}>7 days</option><option value={720}>30 days</option>
          </select>
          <button onClick={load} disabled={loading} className="rounded-xl bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50">{loading ? "Syncing…" : "Update"}</button>
        </div>
      </div>

      {error ? <p className="mt-5 rounded-xl border border-rose-400/20 bg-rose-500/10 p-3 text-sm text-rose-200">{error}</p> : null}

      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metric label="Posts analysed" value={snapshot?.posts_analyzed ?? "—"} />
        <Metric label="Major narratives" value={snapshot?.major_narratives ?? "—"} />
        <Metric label="Emerging clusters" value={snapshot?.emerging_clusters ?? "—"} />
        <Metric label="Priority accounts" value={snapshot?.high_priority_accounts ?? "—"} />
        <Metric label="Accelerating" value={snapshot?.accelerating_narratives ?? "—"} alert />
      </div>

      <div className="mt-6 grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(17rem,0.8fr)]">
        <div className="min-w-0 rounded-2xl border border-white/10 bg-slate-950/45 p-4">
          <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-300">Major narratives</h3>
          <div className="mt-3 max-h-80 space-y-3 overflow-y-auto overflow-x-hidden pr-1">
            {(snapshot?.narratives || []).map((item) => (
              <article key={item.narrative_id} className="min-w-0 rounded-xl border border-white/5 bg-white/[0.03] p-3">
                <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0"><p className="break-words font-medium text-slate-100">{item.label}</p><p className="mt-1 break-words text-xs text-slate-400">{item.platforms.join(" → ")} · {item.posts} posts · {item.actors} actors</p></div>
                  <span className={`shrink-0 rounded-full border px-2 py-1 text-[10px] font-semibold uppercase ${statusTone[item.status]}`}>{item.status}</span>
                </div>
                <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-400"><span>Risk {Math.round(item.average_risk * 100)}%</span><span>{item.velocity_per_hour.toFixed(1)} posts/hr</span><span>Δ {item.acceleration >= 0 ? "+" : ""}{item.acceleration.toFixed(2)}</span></div>
              </article>
            ))}
            {!loading && !snapshot?.narratives?.length ? <p className="py-8 text-center text-sm text-slate-500">Upload a cross-platform batch to populate this incident.</p> : null}
          </div>
        </div>

        <div className="min-w-0 space-y-5">
          <Panel title="Geographic hotspots">
            {(snapshot?.hotspots || []).slice(0, 6).map((item) => <div key={item.region} className="flex min-w-0 justify-between gap-3 text-sm"><span className="truncate text-slate-300">{item.region}</span><span className="shrink-0 text-cyan-300">{item.posts} · {Math.round(item.average_risk * 100)}%</span></div>)}
          </Panel>
          <Panel title="Platform coverage">
            {Object.entries(snapshot?.platforms || {}).map(([platform, count]) => <div key={platform} className="flex justify-between gap-3 text-sm"><span className="capitalize text-slate-300">{platform}</span><span className="text-cyan-300">{count}</span></div>)}
          </Panel>
        </div>
      </div>

      <div className="mt-5 min-w-0 overflow-x-auto rounded-2xl border border-white/10 bg-slate-950/45 p-4">
        <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-300">Activity timeline</h3>
        <div className="mt-4 flex min-w-[36rem] items-end gap-1" style={{ height: 112 }}>
          {(snapshot?.timeline || []).map((item) => <div key={item.start} title={`${new Date(item.start).toLocaleString()} · ${item.posts} posts`} className="group flex h-full min-w-2 flex-1 items-end"><div className="w-full rounded-t bg-gradient-to-t from-cyan-600 to-emerald-300 transition group-hover:to-white" style={{ height: `${Math.max(5, (item.posts / maxTimeline) * 100)}%` }} /></div>)}
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value, alert = false }) {
  return <div className="min-w-0 rounded-2xl border border-white/10 bg-slate-950/50 p-4"><p className="break-words text-[10px] uppercase tracking-[0.18em] text-slate-500">{label}</p><p className={`mt-2 text-2xl font-semibold ${alert ? "text-rose-200" : "text-cyan-200"}`}>{value}</p></div>;
}

function Panel({ title, children }) {
  return <div className="min-w-0 space-y-2 rounded-2xl border border-white/10 bg-slate-950/45 p-4"><h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">{title}</h3>{children}</div>;
}
