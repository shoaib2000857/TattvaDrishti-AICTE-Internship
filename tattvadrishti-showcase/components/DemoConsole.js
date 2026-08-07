"use client";

import { useMemo, useState } from "react";
import { ArrowRight, Check, CircleAlert, ScanSearch, Sparkles } from "lucide-react";

const samples = [
  {
    label: "Urgency & pressure",
    text: "URGENT: Share this with everyone before it gets removed. They do not want you to know the truth. Act now and warn your family!",
  },
  {
    label: "Neutral update",
    text: "The city administration published its revised public transport schedule this morning. The notice is available on the official portal.",
  },
  {
    label: "Coordinated narrative",
    text: "Post this exact message in every local group at 8 PM. Use the same hashtag, tag three people, and do not mention where it came from.",
  },
];

function getAnalysis(text) {
  const normalized = text.toLowerCase();
  const pressure = ["urgent", "act now", "before", "share", "everyone", "truth", "warn"]
    .filter((word) => normalized.includes(word)).length;
  const coordination = ["exact message", "every", "hashtag", "8 pm", "tag three", "same"]
    .filter((word) => normalized.includes(word)).length;
  const punctuation = (text.match(/!/g) || []).length;
  const score = Math.min(92, 18 + pressure * 9 + coordination * 10 + punctuation * 3);
  const tier = score >= 75 ? "Critical" : score >= 60 ? "High" : score >= 35 ? "Medium" : "Low";
  const findings = [];
  if (pressure > 1) findings.push("Urgency and emotional-pressure language detected");
  if (coordination > 1) findings.push("Coordinated amplification cues present");
  if (punctuation > 0) findings.push("Aggressive punctuation increases salience");
  if (!findings.length) findings.push("No strong manipulation cues in this short sample");
  findings.push("Source context and corroboration still required");
  return { score, tier, findings: findings.slice(0, 3) };
}

export default function DemoConsole() {
  const [text, setText] = useState(samples[0].text);
  const [phase, setPhase] = useState("ready");
  const [result, setResult] = useState(null);
  const charCount = text.length;
  const bars = useMemo(() => result ? [result.score, Math.max(22, result.score - 11), Math.max(16, result.score - 24), Math.max(12, result.score - 31)] : [0, 0, 0, 0], [result]);

  const analyze = () => {
    if (text.trim().length < 20 || phase === "scanning") return;
    setPhase("scanning");
    setResult(null);
    window.setTimeout(() => {
      setResult(getAnalysis(text));
      setPhase("complete");
    }, 1350);
  };

  return (
    <div className="demo-shell">
      <div className="demo-topbar">
        <div className="window-dots"><i /><i /><i /></div>
        <span>GUIDED ANALYSIS / DEMONSTRATION</span>
        <span className="demo-status"><i /> Simulation online</span>
      </div>
      <div className="demo-body">
        <div className="demo-input-pane">
          <div className="pane-kicker"><ScanSearch size={15} /> Narrative intake</div>
          <label htmlFor="demo-narrative">Paste or choose a sample narrative</label>
          <textarea
            id="demo-narrative"
            value={text}
            onChange={(event) => { setText(event.target.value); setPhase("ready"); setResult(null); }}
            maxLength={600}
          />
          <div className="textarea-meta">
            <span>English · Public-source sample</span><span>{charCount}/600</span>
          </div>
          <div className="sample-row">
            {samples.map((sample) => (
              <button key={sample.label} onClick={() => { setText(sample.text); setPhase("ready"); setResult(null); }}>
                {sample.label}
              </button>
            ))}
          </div>
          <button className="analyze-button" onClick={analyze} disabled={charCount < 20 || phase === "scanning"}>
            {phase === "scanning" ? <><span className="spinner" /> Fusing evidence signals…</> : <><Sparkles size={17} /> Analyse narrative <ArrowRight size={17} /></>}
          </button>
          <p className="demo-note">Illustrative frontend simulation — not a factual assessment.</p>
        </div>
        <div className={`demo-result-pane ${phase}`}>
          {phase === "scanning" && (
            <div className="scan-state">
              <div className="scanner"><span /></div>
              <strong>Analysing independent signals</strong>
              <p>Semantic · AI-origin · Behavioural · Stylometric</p>
            </div>
          )}
          {result && (
            <div className="result-content">
              <div className="result-heading">
                <div><span>REVIEW PRIORITY</span><strong className={`tier tier-${result.tier.toLowerCase()}`}>{result.tier}</strong></div>
                <div className="score-ring" style={{ "--score": `${result.score * 3.6}deg` }}><span><b>{result.score}</b>/100</span></div>
              </div>
              <div className="signal-bars">
                {[
                  ["Semantic risk", bars[0]], ["AI-origin pattern", bars[1]],
                  ["Behavioural", bars[2]], ["Stylometric", bars[3]],
                ].map(([label, value]) => (
                  <div className="signal-row" key={label}>
                    <span>{label}</span><div><i style={{ width: `${value}%` }} /></div><b>{value}%</b>
                  </div>
                ))}
              </div>
              <div className="findings">
                <span>KEY FINDINGS</span>
                {result.findings.map((finding, index) => <p key={finding}>{index === result.findings.length - 1 ? <CircleAlert size={14} /> : <Check size={14} />}{finding}</p>)}
              </div>
              <div className="human-note"><span>HUMAN IN THE LOOP</span> This priority supports review; it never determines truth, intent or enforcement action.</div>
            </div>
          )}
          {phase === "ready" && (
            <div className="empty-result">
              <div className="empty-rings"><ScanSearch /></div>
              <strong>Evidence, not a black box</strong>
              <p>Run the simulation to see how TattvaDrishti turns a narrative into an explainable review priority.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
