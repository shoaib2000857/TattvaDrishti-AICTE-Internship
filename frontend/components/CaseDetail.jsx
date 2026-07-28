import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import RadarChart from "./RadarChart";
import HopTraceMap from "./HopTraceMap";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
});

const riskBadgeClasses = {
  "high-risk":
    "border-rose-500/40 bg-rose-500/15 text-rose-200 shadow shadow-rose-500/30",
  "medium-risk":
    "border-amber-500/40 bg-amber-500/15 text-amber-200 shadow shadow-amber-500/30",
  "low-risk":
    "border-emerald-500/40 bg-emerald-500/15 text-emerald-200 shadow shadow-emerald-500/30",
};

const defaultShareForm = {
  destination: "USA",
  justification: "Trusted cell requesting rapid alerting on hostile narrative.",
  include_personal_data: false,
};

export default function CaseDetail({
  caseData,
  submission,
  onShare,
  sharePending,
  shareOutput,
}) {
  const [formState, setFormState] = useState(defaultShareForm);
  const [showRiskWarning, setShowRiskWarning] = useState(false);
  const [pendingShareData, setPendingShareData] = useState(null);

  const metadataEntries = useMemo(() => {
    if (!submission?.metadata) return [];
    return Object.entries(submission.metadata).filter(([, value]) => Boolean(value));
  }, [submission]);

  const breakdown = caseData?.breakdown || {};
  const provenance = caseData?.provenance || {};
  const graphSummary = caseData?.graph_summary || {};
  const stylometric = breakdown.stylometric_anomalies || {};
  const heuristics = breakdown.heuristics || [];
  const graphCommunities = graphSummary.communities;
  const gnnClusters = Array.isArray(graphSummary.gnn_clusters)
    ? graphSummary.gnn_clusters
    : [];
  const coordinationAlerts = Array.isArray(graphSummary.coordination_alerts)
    ? graphSummary.coordination_alerts
    : [];
  const propagationChains = Array.isArray(graphSummary.propagation_chains)
    ? graphSummary.propagation_chains
    : [];

  const communitySummaries = useMemo(() => {
    const communities = Array.isArray(graphCommunities) ? graphCommunities : [];
    return communities.map((community) => {
      const entries = [];
      const actors = Array.isArray(community.actors) ? community.actors : [];
      if (actors.length) {
        entries.push({ label: "Actors", value: actors.join(", ") });
      }
      const contentNodes = Array.isArray(community.content)
        ? community.content
        : [];
      if (contentNodes.length) {
        entries.push({ label: "Content", value: contentNodes.join(", ") });
      }
      Object.entries(community || {})
        .filter(([key]) => !["actors", "content"].includes(key))
        .forEach(([key, value]) => {
          if (Array.isArray(value) && value.length) {
            entries.push({
              label: key.replace(/_/g, " "),
              value: value.join(", "),
            });
          } else if (value) {
            entries.push({
              label: key.replace(/_/g, " "),
              value: String(value),
            });
          }
        });
      if (entries.length === 0) {
        entries.push({ label: "Nodes", value: "No entities listed" });
      }
      return entries;
    });
  }, [graphCommunities]);

  if (!caseData) {
    return (
      <aside className="rounded-3xl border border-white/5 bg-slate-900/80 p-6 shadow-2xl shadow-black/50 backdrop-blur">
        <h2 className="text-2xl font-semibold text-white">Case intelligence</h2>
        <div className="mt-8 rounded-2xl border border-dashed border-white/10 bg-slate-900/60 px-5 py-12 text-center text-sm text-slate-500">
          Waiting for a selection. Choose an intake from the table to populate this
          panel.
        </div>
      </aside>
    );
  }

  const selectedClass = (caseData.classification || "event").toLowerCase();

  const handleShareSubmit = async (event) => {
    event.preventDefault();
    
    const shareData = {
      ...formState,
      intake_id: caseData.intake_id,
    };
    
    const classification = (caseData.classification || "").toLowerCase();
    const isHighRisk = classification === "high-risk" || 
                       (typeof caseData.composite_score === "number" && caseData.composite_score >= 0.7);
    
    if (isHighRisk) {
      setPendingShareData(shareData);
      setShowRiskWarning(true);
    } else {
      await onShare(shareData);
    }
  };
  
  const handleConfirmHighRiskShare = async () => {
    setShowRiskWarning(false);
    if (pendingShareData) {
      await onShare(pendingShareData);
      setPendingShareData(null);
    }
  };
  
  const handleCancelHighRiskShare = () => {
    setShowRiskWarning(false);
    setPendingShareData(null);
  };

  return (
    <aside className="flex flex-col gap-8 rounded-3xl border border-white/5 bg-slate-900/80 p-6 shadow-2xl shadow-black/50 backdrop-blur">
      <header className="flex items-start justify-between gap-3">
        <h2 className="text-2xl font-semibold text-white">Case intelligence</h2>
        <span
          className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wider ${riskBadgeClasses[selectedClass] || "border-white/10 bg-white/5 text-slate-200"}`}
        >
          {caseData.classification || "Unknown"}
        </span>
      </header>

      <section className="rounded-2xl border border-white/10 bg-slate-950/60 px-5 py-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">Intake ID</p>
            <p className="mt-1 font-mono text-xs text-emerald-200" title={caseData.intake_id}>
              {caseData.intake_id}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-wide text-slate-400">
              Composite score
            </p>
            <div className="mt-2">
              {typeof caseData.composite_score === "number" ? (
                <ScoreDial value={caseData.composite_score} />
              ) : (
                <p className="text-slate-400 text-sm">n/a</p>
              )}
            </div>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">
              Submitted
            </p>
            <p className="mt-1 text-slate-200">
              {caseData.submitted_at
                ? new Date(caseData.submitted_at).toLocaleString()
                : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-400">
              Graph risk actors
            </p>
            <p className="mt-1 text-slate-200">
              {Array.isArray(graphSummary.high_risk_actors) && graphSummary.high_risk_actors.length
                ? graphSummary.high_risk_actors.join(", ")
                : "None flagged"}
            </p>
          </div>
        </div>
      </section>

      {caseData.decision_reason && (
        <section className="rounded-2xl border border-emerald-500/10 bg-emerald-500/5 px-5 py-4">
          <p className="text-xs uppercase tracking-[0.32em] text-emerald-300">Decision rationale</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-100">
            {caseData.decision_reason}
          </p>
        </section>
      )}

      <section className="space-y-5">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Signal breakdown
        </h3>
        <ScoreBar label="Linguistic confidence" value={breakdown.linguistic_score} color="bg-emerald-400" />
        <ScoreBar label="Behavioral risk" value={breakdown.behavioral_score} color="bg-amber-400" />
        <ScoreBar label="AI Detection probability" value={breakdown.ai_probability} color="bg-cyan-400" />
        {breakdown.ollama_risk !== null && breakdown.ollama_risk !== undefined && (
          <ScoreBar label="Ollama Semantic Risk" value={breakdown.ollama_risk} color="bg-purple-400" />
        )}
        {breakdown.model_family && (
          <div className="rounded-xl border border-white/10 bg-slate-950/60 px-4 py-3">
            <p className="text-xs uppercase tracking-wide text-slate-400 mb-2">Model Family Detected</p>
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-fuchsia-300">{breakdown.model_family}</span>
              <span className="text-xs text-slate-400">
                {breakdown.model_family_confidence ? `${(breakdown.model_family_confidence * 100).toFixed(1)}%` : '—'}
              </span>
            </div>
            {breakdown.model_family_probabilities && Object.keys(breakdown.model_family_probabilities).length > 0 && (
              <div className="mt-3 space-y-1">
                {Object.entries(breakdown.model_family_probabilities).map(([family, prob]) => (
                  <div key={family} className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">{family}</span>
                    <span className="font-mono text-slate-300">{(prob * 100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-white/10 bg-slate-950/60 px-5 py-5">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Stylometric analysis
        </h3>
        <div className="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
              Anomalies
            </h4>
            <ul className="space-y-2 text-sm text-slate-200">
              {Object.keys(stylometric).length === 0 ? (
                <li className="text-xs text-slate-500">
                  No stylometric anomalies detected.
                </li>
              ) : (
                Object.entries(stylometric).map(([key, value]) => (
                  <li
                    key={key}
                    className="flex items-center justify-between rounded-xl border border-white/10 bg-slate-900/50 px-4 py-2"
                  >
                    <span className="text-xs uppercase tracking-wide text-slate-400">
                      {key.replace(/_/g, " ")}
                    </span>
                    <span className="font-mono text-sm text-emerald-200">
                      {typeof value === "number" ? value.toFixed(2) : String(value)}
                    </span>
                  </li>
                ))
              )}
            </ul>
          </div>

          <div className="flex justify-center items-start">
            <RadarChart breakdown={breakdown} />
          </div>
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Triggered heuristics
        </h3>
        <div className="mt-3 flex flex-wrap gap-2 text-sm text-emerald-200">
          {heuristics.length === 0 ? (
            <span className="text-xs text-slate-500">
              No heuristics were triggered for this case.
            </span>
          ) : (
            heuristics.map((heuristic) => (
              <span
                key={heuristic}
                className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs"
              >
                {heuristic}
              </span>
            ))
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-white/10 bg-slate-950/60 px-5 py-5">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Provenance checks
        </h3>
        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div className="rounded-xl border border-white/10 bg-slate-900/60 px-4 py-3 text-slate-200">
            Watermark: {provenance.watermark_present ? "detected" : "absent"}
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 px-4 py-3 text-slate-200">
            Signature: {provenance.signature_valid ? "valid" : "invalid"}
          </div>
          <div className="rounded-xl border border-white/10 bg-slate-900/60 px-4 py-3 text-slate-200 col-span-2">
            <p className="text-xs uppercase tracking-wide text-slate-400">Content fingerprint (SHA-256)</p>
            <p className="mt-1 font-mono text-[11px] break-all text-emerald-200">
              {provenance.content_hash || "—"}
            </p>
          </div>
        </div>
        <ul className="mt-4 space-y-1 text-xs text-slate-400">
          {Array.isArray(provenance.validation_notes) &&
          provenance.validation_notes.length ? (
            provenance.validation_notes.map((note, index) => (
              <li key={index}>• {note}</li>
            ))
          ) : (
            <li>• No additional validation notes.</li>
          )}
        </ul>
      </section>

      {/* GRAPH INTELLIGENCE SNAPSHOT: Combines Stat Cards, Visual Canvas, AND Community Listings */}
      <section className="rounded-2xl border border-white/10 bg-slate-950/60 px-5 py-5">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Graph intelligence snapshot
        </h3>
        <div className="mt-4 grid grid-cols-2 gap-3 text-center text-sm text-slate-200 md:grid-cols-4">
          <StatCard label="Nodes" value={graphSummary.node_count} />
          <StatCard label="Edges" value={graphSummary.edge_count} />
          <StatCard
            label="Communities"
            value={Array.isArray(graphSummary.communities) ? graphSummary.communities.length : 0}
          />
          <StatCard label="GNN clusters" value={gnnClusters.length} />
        </div>
        
        {/* Visual Force-Directed Canvas */}
        <GraphCanvas graphSummary={graphSummary} />

        {/* Text Community Listings (Re-integrated from incoming) */}
        <div className="mt-4 space-y-2 text-xs text-slate-400">
          {Array.isArray(graphSummary.communities) && graphSummary.communities.length ? (
            graphSummary.communities.map((community, index) => {
              const summary = communitySummaries[index] || [];
              return (
                <div
                  key={index}
                  className="rounded-xl border border-white/10 bg-slate-900/60 px-4 py-3"
                >
                  <p className="text-[10px] uppercase tracking-[0.35em] text-slate-500">
                    COMMUNITY {index + 1}
                  </p>
                  <div className="mt-2 space-y-1 text-xs text-slate-200">
                    {summary.map((entry, entryIndex) => (
                      <p key={`${index}-${entry.label}-${entryIndex}`}>
                        <span className="mr-2 text-[10px] uppercase tracking-[0.3em] text-slate-500">
                          {entry.label}:
                        </span>
                        <span className="font-mono text-[11px] text-emerald-200">
                          {entry.value}
                        </span>
                      </p>
                    ))}
                  </div>
                </div>
              );
            })
          ) : (
            <div className="rounded-xl border border-dashed border-white/10 bg-slate-900/50 px-4 py-3 text-xs text-slate-500">
              No community clusters reported for this intake.
            </div>
          )}
        </div>
      </section>

      <section className="rounded-2xl border border-white/10 bg-slate-950/60 px-5 py-5">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          GNN cluster detections
        </h3>
        {gnnClusters.length ? (
          <div className="mt-4 space-y-3 text-xs text-slate-300">
            {gnnClusters.map((cluster) => (
              <article
                key={cluster.cluster_id}
                className="rounded-xl border border-white/10 bg-slate-900/60 px-4 py-3"
              >
                <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.35em] text-slate-500">
                  <span>{cluster.cluster_id}</span>
                  <span className="text-emerald-300">{(cluster.score ?? 0).toFixed(2)}</span>
                </div>
                <div className="mt-3 space-y-1 text-[13px]">
                  {cluster.actors?.length ? (
                    <p>
                      <span className="text-slate-500">Actors:</span>
                      <span className="ml-2 font-mono text-emerald-200">
                        {cluster.actors.join(", ")}
                      </span>
                    </p>
                  ) : null}
                  {cluster.narratives?.length ? (
                    <p>
                      <span className="text-slate-500">Narratives:</span>
                      <span className="ml-2 font-mono text-cyan-200">
                        {cluster.narratives.join(", ")}
                      </span>
                    </p>
                  ) : null}
                  {cluster.content?.length ? (
                    <p>
                      <span className="text-slate-500">Content:</span>
                      <span className="ml-2 font-mono text-amber-200">
                        {cluster.content.join(", ")}
                      </span>
                    </p>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-xs text-slate-500">
            No GNN-driven communities have been scored yet for this case.
          </p>
        )}
      </section>

      {/* SIMILAR MESSAGE CLUSTERS VISUAL CARDS */}
      {gnnClusters.length > 0 && (
        <section className="rounded-2xl border border-white/10 bg-slate-950/60 px-5 py-5">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Similar message clusters
          </h3>
          <div className="mt-4 space-y-4">
            {gnnClusters.map((cluster) => (
              <article
                key={`message-${cluster.cluster_id}`}
                className="rounded-xl border border-slate-800 bg-gradient-to-b from-slate-900 to-black px-4 py-4 shadow-xl shadow-black/40"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="font-mono text-xs text-slate-200 tracking-wide">
                    {cluster.cluster_id}
                  </p>
                  <span
                    className={`rounded-full border px-3 py-1 font-mono text-[11px] shadow ${
                      getClusterScoreClasses(cluster.score)
                    }`}
                  >
                    {(cluster.score ?? 0).toFixed(2)}
                  </span>
                </div>
                <ClusterPillGroup
                  label="CONTENT NODES"
                  items={cluster.content}
                  pillClassName="bg-cyan-950/70 border-cyan-400/25 text-cyan-100 shadow-cyan-500/10"
                />
                <ClusterPillGroup
                  label="ACTORS"
                  items={cluster.actors}
                  pillClassName="bg-rose-950/70 border-rose-400/25 text-rose-100 shadow-rose-500/10"
                />
                <ClusterPillGroup
                  label="NARRATIVES"
                  items={cluster.narratives}
                  pillClassName="bg-purple-950/70 border-purple-400/25 text-purple-100 shadow-purple-500/10"
                />
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="rounded-2xl border border-white/10 bg-slate-950/60 px-5 py-5">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Cross-platform coordination alerts
        </h3>
        {coordinationAlerts.length ? (
          <div className="mt-4 space-y-3 text-xs text-slate-300">
            {coordinationAlerts.map((alert, index) => (
              <article
                key={`${alert.actor}-${index}`}
                className="rounded-xl border border-white/10 bg-slate-900/60 px-4 py-4"
              >
                <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.35em] text-slate-500">
                  <span>{alert.actor}</span>
                  <span className="text-rose-200">Risk {(alert.risk ?? 0).toFixed(2)}</span>
                </div>
                <div className="mt-3 space-y-1 text-[13px]">
                  {alert.peer_actors?.length ? (
                    <p>
                      <span className="text-slate-500">Peers:</span>
                      <span className="ml-2 font-mono text-emerald-200">
                        {alert.peer_actors.join(", ")}
                      </span>
                    </p>
                  ) : null}
                  {alert.shared_tags?.length ? (
                    <p>
                      <span className="text-slate-500">Shared narratives:</span>
                      <span className="ml-2 font-mono text-cyan-200">
                        {alert.shared_tags.join(", ")}
                      </span>
                    </p>
                  ) : null}
                  {alert.platforms?.length ? (
                    <p>
                      <span className="text-slate-500">Platforms:</span>
                      <span className="ml-2 font-mono text-amber-200">
                        {alert.platforms.join(", ")}
                      </span>
                    </p>
                  ) : null}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-xs text-slate-500">
            No coordination signals flagged between actors for this intake.
          </p>
        )}
      </section>

      <section className="rounded-2xl border border-white/10 bg-slate-950/60 px-5 py-5">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Propagation chains
        </h3>
        {propagationChains.length ? (
          <div className="mt-4 space-y-3 text-xs text-slate-300">
            {propagationChains.map((chain, index) => (
              <article
                key={`${chain.path?.join("-") || "chain"}-${index}`}
                className="rounded-xl border border-white/10 bg-slate-900/60 px-4 py-4"
              >
                <p className="font-mono text-[12px] text-emerald-200">
                  {(chain.path || []).join(" → ") || "No path computed"}
                </p>
                <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-[12px] text-slate-400">
                  <span>Likelihood {(chain.likelihood ?? 0).toFixed(2)}</span>
                  <span>
                    Platforms: <span className="font-mono text-amber-200">{(chain.platforms || []).join(", ") || "n/a"}</span>
                  </span>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-xs text-slate-500">
            Propagation modelling has not surfaced any cross-actor handoffs.
          </p>
        )}
      </section>

      <section className="rounded-2xl border border-white/10 bg-slate-950/60 px-5 py-5">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Submitted payload
        </h3>
        <div className="mt-4 space-y-3 text-sm text-slate-200">
          <p className="rounded-xl border border-white/5 bg-slate-900/60 px-4 py-3 text-slate-100">
            {submission?.text || "Source text not available in this session."}
          </p>
          <div className="grid grid-cols-2 gap-3 text-xs text-slate-300">
            {metadataEntries.length ? (
              metadataEntries.map(([key, value]) => (
                <div
                  key={key}
                  className="rounded-xl border border-white/10 bg-slate-900/60 px-3 py-2"
                >
                  <p className="text-[10px] uppercase tracking-[0.35em] text-slate-400">
                    {key.replace(/_/g, " ")}
                  </p>
                  <p className="mt-1 text-xs text-slate-200">
                    {typeof value === "string" ? value : JSON.stringify(value)}
                  </p>
                </div>
              ))
            ) : (
              <p className="col-span-2 text-xs text-slate-500">
                Metadata was not captured for this intake.
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-emerald-200">
            {Array.isArray(submission?.tags) && submission.tags.length ? (
              submission.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1"
                >
                  {tag}
                </span>
              ))
            ) : (
              <span className="text-xs text-slate-500">
                No analyst tags applied.
              </span>
            )}
          </div>
        </div>
      </section>

      <section className="space-y-4 rounded-2xl border border-white/10 bg-slate-950/60 px-5 py-5">
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Generate sharing package
          </h3>
          <p className="mt-1 text-xs text-slate-400">
            Wrap the analysis into a signed package for partner dissemination directly through the API.
          </p>
        </div>
        <form className="space-y-4" onSubmit={handleShareSubmit}>
          <label className="flex flex-col gap-2 text-slate-200">
            <span className="text-xs uppercase tracking-wide text-slate-400">
              Destination
            </span>
            <select
              value={formState.destination}
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  destination: event.target.value,
                }))
              }
              className="input"
            >
              <option value="USA">USA</option>
              <option value="EU">EU</option>
              <option value="IN">IN</option>
              <option value="AUS">AUS</option>
            </select>
          </label>

          <label className="flex flex-col gap-2 text-slate-200">
            <span className="text-xs uppercase tracking-wide text-slate-400">
              Justification
            </span>
            <textarea
              value={formState.justification}
              rows={2}
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  justification: event.target.value,
                }))
              }
              className="input"
            />
          </label>

          <button
            type="submit"
            disabled={sharePending}
            className="inline-flex w-full items-center justify-center gap-2 rounded-full border border-emerald-400/40 bg-emerald-400/20 px-4 py-2 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-400/30 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Build package
          </button>
        </form>
        {shareOutput ? (
          <>
            <pre className="max-h-48 overflow-y-auto rounded-2xl border border-white/10 bg-slate-950/80 px-4 py-3 text-xs text-slate-300">
              {shareOutput}
            </pre>
            <HopTraceMap sharePackage={shareOutput} />
          </>
        ) : null}
      </section>

      {/* High Risk Warning Dialog */}
      {showRiskWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="mx-4 max-w-md rounded-2xl border border-rose-500/30 bg-slate-900 p-6 shadow-2xl">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-rose-500/20">
                <svg className="h-6 w-6 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-rose-200">High Risk Content Warning</h3>
                <p className="mt-2 text-sm text-slate-300">
                  The package you are trying to send contains <span className="font-semibold text-rose-300">high-risk content</span> (Risk Score: {Math.round((caseData.composite_score || 0) * 100)}%).
                </p>
                <p className="mt-2 text-sm text-slate-400">
                  Destination: <span className="font-semibold text-white">{formState.destination}</span>
                </p>
                <p className="mt-1 text-sm text-slate-400">
                  Please confirm that you want to proceed with sharing this intelligence package.
                </p>
              </div>
            </div>
            <div className="mt-6 flex gap-3">
              <button
                onClick={handleCancelHighRiskShare}
                className="flex-1 rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmHighRiskShare}
                disabled={sharePending}
                className="flex-1 rounded-lg border border-rose-500/40 bg-rose-500/20 px-4 py-2 text-sm font-semibold text-rose-200 transition hover:bg-rose-500/30 disabled:opacity-50"
              >
                {sharePending ? "Processing..." : "Confirm & Send"}
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}

function ScoreBar({ label, value, color }) {
  const safeValue = typeof value === "number" ? Math.max(0, Math.min(value, 1)) : null;
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>{label}</span>
        <span>
          {safeValue === null ? "n/a" : `${Math.round(safeValue * 100)}%`}
        </span>
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-800">
        <div
          className={`${color} h-full rounded-full transition-all duration-300`}
          style={{ width: safeValue === null ? "4%" : `${Math.round(safeValue * 100)}%` }}
        />
      </div>
    </div>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/60 px-4 py-3">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-2 text-lg font-semibold text-emerald-200">
        {value ?? "—"}
      </p>
    </div>
  );
}

function GraphCanvas({ graphSummary }) {
  const graphRef = useRef(null);
  const containerRef = useRef(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [graphWidth, setGraphWidth] = useState(640);
  const hasZoomedRef = useRef(false);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const updateWidth = () => {
      setGraphWidth(Math.max(container.clientWidth, 320));
    };

    updateWidth();
    const resizeObserver = new ResizeObserver(updateWidth);
    resizeObserver.observe(container);

    return () => resizeObserver.disconnect();
  }, []);

  const graphData = useMemo(() => {
    const communities = Array.isArray(graphSummary?.communities)
      ? graphSummary.communities
      : [];
    const nodesById = new Map();
    const linksById = new Map();

    const addNode = (id, fallbackType, communityIndex) => {
      if (!id) return;
      const nodeId = String(id);
      if (!nodesById.has(nodeId)) {
        const type = getGraphNodeType(nodeId, fallbackType);
        nodesById.set(nodeId, {
          id: nodeId,
          type,
          label: getGraphNodeLabel(nodeId),
          communities: [communityIndex],
        });
        return;
      }
      nodesById.get(nodeId).communities.push(communityIndex);
    };

    const addLink = (source, target) => {
      if (!source || !target) return;
      const linkId = `${source}->${target}`;
      if (!linksById.has(linkId)) {
        linksById.set(linkId, {
          source: String(source),
          target: String(target),
        });
      }
    };

    communities.forEach((community, communityIndex) => {
      const actors = getCommunityValues(community, "actors");
      const contentNodes = getCommunityValues(community, "content");
      const narratives = getCommunityValues(community, "narratives");

      actors.forEach((actor) => addNode(actor, "actor", communityIndex));
      contentNodes.forEach((content) => addNode(content, "content", communityIndex));
      narratives.forEach((narrative) =>
        addNode(narrative, "narrative", communityIndex)
      );

      actors.forEach((actor) => {
        contentNodes.forEach((content) => addLink(actor, content));
      });
      contentNodes.forEach((content) => {
        narratives.forEach((narrative) => addLink(content, narrative));
      });
    });

    return {
      nodes: Array.from(nodesById.values()),
      links: Array.from(linksById.values()),
    };
  }, [graphSummary]);

  useEffect(() => {
    hasZoomedRef.current = false;
    setSelectedNode(null);
    setHoveredNode(null);
  }, [graphData]);

  return (
    <div className="mt-4">
      <div
        ref={containerRef}
        className="h-[280px] w-full overflow-hidden rounded-xl bg-[#020617] shadow-inner shadow-cyan-500/10"
      >
        {graphData.nodes.length ? (
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            width={graphWidth}
            height={280}
            backgroundColor="#020617"
            d3VelocityDecay={0.24}
            cooldownTicks={90}
            nodeCanvasObject={(node, ctx, globalScale) =>
              drawGraphNode(node, ctx, globalScale, hoveredNode?.id === node.id)
            }
            nodeLabel={(node) => node.label}
            nodePointerAreaPaint={(node, color, ctx) => {
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, 10, 0, 2 * Math.PI, false);
              ctx.fill();
            }}
            linkColor={() => "rgba(255, 255, 255, 0.15)"}
            linkWidth={0.8}
            onNodeHover={(node) => setHoveredNode(node)}
            onNodeClick={(node) => setSelectedNode(node)}
            onEngineStop={() => {
              if (!hasZoomedRef.current) {
                graphRef.current?.zoomToFit(500, 36);
                hasZoomedRef.current = true;
              }
            }}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-slate-500">
            No graph nodes available for this intake.
          </div>
        )}
      </div>
      {hoveredNode ? (
        <div className="mt-3 rounded-xl border border-cyan-400/20 bg-slate-950 px-4 py-2 text-xs text-cyan-100 shadow shadow-cyan-500/10">
          <span className="mr-2 text-[10px] uppercase tracking-[0.3em] text-slate-500">
            Hover
          </span>
          <span className="font-mono">{hoveredNode.label}</span>
        </div>
      ) : null}
      {selectedNode ? (
        <div className="mt-3 rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-xs text-slate-300 shadow shadow-purple-500/10">
          <span className="mr-2 text-[10px] uppercase tracking-[0.3em] text-slate-500">
            Selected
          </span>
          <span className="font-mono text-emerald-200">{selectedNode.id}</span>
          <span className="mx-2 text-slate-600">/</span>
          <span className="font-mono text-slate-300">{selectedNode.type}</span>
        </div>
      ) : null}
    </div>
  );
}

const graphNodeColors = {
  actor: "#fb7185",
  content: "#22d3ee",
  narrative: "#c084fc",
};

function getCommunityValues(community, key) {
  const values = Array.isArray(community?.[key]) ? community[key] : [];
  return values.filter((value) => value !== null && value !== undefined);
}

function getGraphNodeType(id, fallbackType) {
  if (id.startsWith("actor::")) return "actor";
  if (id.startsWith("content::")) return "content";
  if (id.startsWith("narrative::")) return "narrative";
  return fallbackType;
}

function getGraphNodeLabel(id) {
  return stripGraphPrefix(id);
}

function stripGraphPrefix(value) {
  return String(value).replace(/^(actor|content|narrative)::/, "");
}

function formatClusterPillValue(value) {
  return stripGraphPrefix(value).slice(0, 8);
}

function drawGraphNode(node, ctx, globalScale, isHovered) {
  const color = graphNodeColors[node.type] || "#e2e8f0";
  const radius = isHovered ? 7 : 5;

  ctx.save();
  ctx.shadowColor = color;
  ctx.shadowBlur = isHovered ? 24 : 16;
  ctx.beginPath();
  ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
  ctx.fillStyle = color;
  ctx.fill();

  ctx.shadowBlur = isHovered ? 34 : 20;
  ctx.beginPath();
  ctx.arc(node.x, node.y, radius + 3, 0, 2 * Math.PI, false);
  ctx.strokeStyle = color;
  ctx.globalAlpha = isHovered ? 0.55 : 0.28;
  ctx.lineWidth = 1.2;
  ctx.stroke();
  ctx.restore();

  if (isHovered) {
    const fontSize = Math.max(10 / globalScale, 3.5);
    ctx.save();
    ctx.font = `${fontSize}px monospace`;
    ctx.fillStyle = "rgba(226, 232, 240, 0.95)";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.shadowColor = "rgba(2, 6, 23, 0.95)";
    ctx.shadowBlur = 8;
    ctx.fillText(node.label, node.x, node.y + radius + 5);
    ctx.restore();
  }
}

function getClusterScoreClasses(score) {
  const safeScore = typeof score === "number" ? score : 0;
  if (safeScore > 0.75) {
    return "border-rose-400/50 bg-rose-500/20 text-rose-100 shadow-rose-500/30";
  }
  if (safeScore >= 0.5) {
    return "border-amber-400/50 bg-amber-500/20 text-amber-100 shadow-amber-500/25";
  }
  return "border-emerald-400/50 bg-emerald-500/20 text-emerald-100 shadow-emerald-500/25";
}

function ClusterPillGroup({ label, items, pillClassName }) {
  if (!Array.isArray(items) || items.length === 0) return null;

  return (
    <div className="mt-4">
      <p className="text-[10px] uppercase tracking-widest text-slate-500">
        {label}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {items.map((item, index) => (
          <span
            key={`${label}-${item}-${index}`}
            title={String(item)}
            className={`rounded-full border px-3 py-1 font-mono text-[11px] shadow ${pillClassName}`}
          >
            {formatClusterPillValue(item)}
          </span>
        ))}
      </div>
    </div>
  );
}

function ScoreDial({ value }) {
  const size = 60;
  const strokeWidth = 5;
  const center = size / 2;
  const radius = center - strokeWidth;
  const circumference = 2 * Math.PI * radius;

  const arcLength = circumference * 0.75;
  const safeValue = Math.max(0, Math.min(value, 1));
  const offset = arcLength - safeValue * arcLength;
  
  const scorePercent = safeValue * 100;
  let strokeColor, textColor;
  
  if (scorePercent >= 75) {
    strokeColor = "rgb(239 68 68)";
    textColor = "text-red-300";
  } else if (scorePercent >= 50) {
    strokeColor = "rgb(249 115 22)";
    textColor = "text-orange-300";
  } else {
    strokeColor = "rgb(52 211 153)";
    textColor = "text-emerald-200";
  }

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform rotate-[135deg]">
        <circle
          cx={center}
          cy={center}
          r={radius}
          stroke="rgba(255, 255, 255, 0.1)"
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={arcLength}
          strokeLinecap="round"
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={arcLength}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.3s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className={`${textColor} text-sm font-semibold`}>
          {Math.round(safeValue * 100)}%
        </span>
      </div>
    </div>
  );
}