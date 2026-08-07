"use client";

import { useState } from "react";
import {
  Activity, ArrowDown, ArrowRight, Blocks, Bot, BrainCircuit, Check,
  ChevronRight, Database, FileArchive, Fingerprint, Github, Globe2,
  Image as ImageIcon, Layers3, LockKeyhole, Map, Menu, Network,
  Radio, ScanText, ShieldCheck, Sparkles, Users, X, Zap,
} from "lucide-react";
import Logo from "./Logo";
import SignalOrb from "./SignalOrb";
import DemoConsole from "./DemoConsole";

const featureGroups = [
  {
    label: "Collect & understand",
    title: "Evidence enters in the format you actually receive it.",
    copy: "Move from one suspicious message to full historical archives without losing the context that makes evidence useful.",
    features: [
      { icon: ScanText, title: "Narrative analysis", text: "Inspect text with language, region, source, platform, actor and narrative context." },
      { icon: FileArchive, title: "Batch archives", text: "Process JSON, JSONL and NDJSON collections with per-record validation and source lineage." },
      { icon: Radio, title: "Public-channel intake", text: "Extract and sanitize public Telegram posts for specialised AI-origin and lexical analysis." },
      { icon: ImageIcon, title: "Image intelligence", text: "Screen for AI generation, violence, gore, offensive content, embedded text and QR codes." },
    ],
  },
  {
    label: "Analyse & explain",
    title: "Four evidence planes. One defensible assessment.",
    copy: "Independent analytical signals remain visible, helping analysts understand agreement, disagreement and uncertainty.",
    features: [
      { icon: BrainCircuit, title: "Semantic risk", text: "Local LLM reasoning examines contextual danger, manipulation and likely intent." },
      { icon: Bot, title: "AI-origin estimation", text: "Transformer inference estimates machine-versus-human writing patterns at batch scale." },
      { icon: Activity, title: "Behavioural signals", text: "Urgency, calls to action, emotional pressure, links and platform cues become evidence." },
      { icon: Fingerprint, title: "Stylometry & provenance", text: "Lexical diversity, entropy, repetition, burstiness and fingerprints support traceability." },
    ],
  },
  {
    label: "Connect & protect",
    title: "See the campaign, then share only what is necessary.",
    copy: "Cases become relationships across content, actors, narratives and regions, with policy-aware paths for trusted exchange.",
    features: [
      { icon: Network, title: "Threat graph", text: "Reveal communities, actor rankings, coordination alerts and propagation indicators." },
      { icon: Map, title: "Geographic risk", text: "Map normalised case signals to understand where narratives are appearing." },
      { icon: LockKeyhole, title: "Controlled sharing", text: "Prepare redacted, signed and encrypted packages with justification and policy tags." },
      { icon: Blocks, title: "Federated audit", text: "A four-node tamper-evident prototype validates integrity across trusted participants." },
    ],
  },
];

const audiences = [
  { icon: ShieldCheck, role: "Guided", title: "Field & enforcement teams", text: "A low-clutter path to priority, key findings and a clear recommended next step." },
  { icon: Activity, role: "Analyst", title: "Cyber & intelligence analysts", text: "Detailed evidence, case history, graphs, maps, live signals and sharing controls." },
  { icon: Network, role: "Superuser", title: "Technical supervisors", text: "Federation health, chain validation, synchronisation and global monitoring." },
];

const workflow = [
  { num: "01", icon: Database, label: "Collect", detail: "Messages, archives, channels, images" },
  { num: "02", icon: Layers3, label: "Normalise", detail: "Clean, validate, preserve lineage" },
  { num: "03", icon: BrainCircuit, label: "Analyse", detail: "Fuse independent evidence" },
  { num: "04", icon: Network, label: "Correlate", detail: "Actors, narratives, regions, URLs" },
  { num: "05", icon: Sparkles, label: "Explain", detail: "Priority, uncertainty, next step" },
  { num: "06", icon: LockKeyhole, label: "Share", detail: "Redacted, signed, auditable" },
];

const stack = ["Next.js", "FastAPI", "PyTorch", "Transformers", "Ollama", "NetworkX", "SQLite", "Fernet", "Ed25519", "Docker"];

export default function Showcase() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeFeature, setActiveFeature] = useState(0);
  const active = featureGroups[activeFeature];

  const closeMenu = () => setMenuOpen(false);

  return (
    <main id="top">
      <nav className="nav-wrap" aria-label="Primary navigation">
        <div className="nav-inner">
          <Logo />
          <div className={`nav-links ${menuOpen ? "open" : ""}`}>
            <a href="#problem" onClick={closeMenu}>Why it matters</a>
            <a href="#capabilities" onClick={closeMenu}>Capabilities</a>
            <a href="#workflow" onClick={closeMenu}>How it works</a>
            <a href="#demo" onClick={closeMenu}>Try the demo</a>
            <a className="nav-cta" href="/TattvaDrishti-NCSRC-Dossier.pdf" target="_blank" onClick={closeMenu}>Project dossier <ArrowRight size={15} /></a>
          </div>
          <button className="menu-button" onClick={() => setMenuOpen((value) => !value)} aria-label="Toggle navigation" aria-expanded={menuOpen}>
            {menuOpen ? <X /> : <Menu />}
          </button>
        </div>
      </nav>

      <header className="hero section-shell">
        <div className="hero-grid" />
        <div className="hero-noise" />
        <div className="hero-content container">
          <div className="hero-copy">

            <p className="eyebrow">Analyst-centric intelligence for AI-enabled information operations</p>
            <h1>See through<br />the <em>signal.</em></h1>
            <p className="hero-lede">TattvaDrishti turns suspicious digital content into explainable, connected and auditable intelligence, so analysts can decide faster, with the evidence in view.</p>
            <div className="hero-actions">
              <a href="#demo" className="primary-button">Experience the workflow <ArrowRight size={18} /></a>
              <a href="#capabilities" className="text-button">Explore capabilities <ArrowDown size={17} /></a>
            </div>
            <div className="hero-proof">
              <div><b>4</b><span>independent<br />evidence planes</span></div>
              <div><b>5K</b><span>records per<br />batch by default</span></div>
              <div><b>3</b><span>role-specific<br />experiences</span></div>
            </div>
          </div>
          <div className="hero-visual">
            <SignalOrb />
            <div className="visual-caption"><i /><span>Evidence fusion engine</span><b>ACTIVE</b></div>
          </div>
        </div>
        <div className="hero-bottom container">
          <span>Developed by <b>Team ASHTOJ</b></span>
          <span>Keshav Memorial Institute of Technology</span>
          <span>SIH 2025 Winners</span>
          <span>AICTE Cyber Security Internship 2025–26</span>
        </div>
      </header>

      <section className="problem-section section-shell" id="problem">
        <div className="container">
          <div className="section-heading split-heading">
            <div><span className="section-index">01 / THE CHALLENGE</span><h2>The threat isn’t just fake content.<br /><em>It’s speed, scale and coordination.</em></h2></div>
            <p>Generative AI lowers the cost of persuasive, targeted narratives. The operational challenge is finding what matters, why it matters, and how it connects—without outsourcing judgement to a single opaque score.</p>
          </div>
          <div className="problem-grid">
            <article><span>01</span><Zap /><h3>Volume outpaces review</h3><p>Thousands of messages and channel posts compete for limited analyst attention under time pressure.</p></article>
            <article><span>02</span><BrainCircuit /><h3>A score is not an explanation</h3><p>Origin probability alone cannot establish manipulation, operational context or proportionate action.</p></article>
            <article><span>03</span><Network /><h3>Campaigns hide between cases</h3><p>Recurring actors, narratives and propagation paths remain invisible when each message is reviewed alone.</p></article>
            <article className="problem-answer"><span>THE RESPONSE</span><Logo compact /><h3>One workflow from raw evidence to human decision.</h3><a href="#workflow">Follow the evidence <ArrowRight size={17} /></a></article>
          </div>
        </div>
      </section>

      <section className="workflow-section section-shell" id="workflow">
        <div className="container">
          <div className="section-heading compact-heading"><span className="section-index">02 / OPERATIONAL WORKFLOW</span><h2>From collection to controlled sharing.</h2><p>Context stays attached at every step.</p></div>
          <div className="workflow-track">
            {workflow.map(({ num, icon: Icon, label, detail }, index) => (
              <div className="workflow-step" key={num}>
                <div className="workflow-card"><span>{num}</span><Icon /><h3>{label}</h3><p>{detail}</p></div>
                {index < workflow.length - 1 && <ChevronRight className="workflow-arrow" />}
              </div>
            ))}
          </div>
          <div className="workflow-principles">
            <span><Check /> Evidence lineage</span><span><Check /> Graceful degradation</span><span><Check /> Explainability by construction</span><span><Check /> Human accountability</span>
          </div>
        </div>
      </section>

      <section className="capabilities-section section-shell" id="capabilities">
        <div className="container">
          <div className="section-heading split-heading light-heading">
            <div><span className="section-index">03 / CURRENT PROTOTYPE</span><h2>A full intelligence workflow.<br /><em>Not another detector.</em></h2></div>
            <p>Built as modular decision support for field personnel, intelligence analysts and technical supervisors.</p>
          </div>
          <div className="capability-tabs" role="tablist" aria-label="Capability categories">
            {featureGroups.map((group, index) => <button key={group.label} className={activeFeature === index ? "active" : ""} onClick={() => setActiveFeature(index)}><span>0{index + 1}</span>{group.label}</button>)}
          </div>
          <div className="capability-panel">
            <div className="capability-intro"><span>CAPABILITY SET 0{activeFeature + 1}</span><h3>{active.title}</h3><p>{active.copy}</p></div>
            <div className="feature-grid">
              {active.features.map(({ icon: Icon, title, text }) => <article key={title}><Icon /><div><h4>{title}</h4><p>{text}</p></div></article>)}
            </div>
          </div>
          <div className="fusion-strip">
            <div className="fusion-title"><span>THE FUSION MODEL</span><strong>Independent signals remain inspectable.</strong></div>
            {[["Semantic risk", "40%", "#53d9ea"], ["AI-origin", "35%", "#36c9a1"], ["Behavioural", "15%", "#f1ad5a"], ["Stylometric", "10%", "#a990ef"]].map(([label, value, color]) => <div className="fusion-metric" key={label} style={{ "--metric": color }}><i /><b>{value}</b><span>{label}</span></div>)}
            <small>Prototype weights; operational deployment requires calibration.</small>
          </div>
        </div>
      </section>

      <section className="demo-section section-shell" id="demo">
        <div className="demo-glow" />
        <div className="container">
          <div className="section-heading demo-heading"><span className="section-index">04 / INTERACTIVE EXPLAINER</span><h2>Put a narrative through the lens.</h2><p>See how separate signals become a review priority, supporting evidence and an accountable next step.</p></div>
          <DemoConsole />
        </div>
      </section>

      <section className="audience-section section-shell">
        <div className="container">
          <div className="section-heading split-heading"><div><span className="section-index">05 / DESIGNED FOR DECISIONS</span><h2>The right depth<br /><em>for every role.</em></h2></div><p>Progressive disclosure keeps the first decision simple while preserving forensic depth for those who need it.</p></div>
          <div className="audience-grid">
            {audiences.map(({ icon: Icon, role, title, text }, index) => <article key={role}><div className="audience-top"><span>0{index + 1}</span><Icon /></div><p className="role-label">{role} dashboard</p><h3>{title}</h3><p>{text}</p><div className="role-line" /></article>)}
          </div>
        </div>
      </section>

      <section className="scale-section section-shell">
        <div className="container scale-grid">
          <div className="scale-copy"><span className="section-index">06 / ENGINEERED BEYOND A DEMO</span><h2>Built to preserve evidence<br />when the volume grows.</h2><p>Vectorised model work, bounded local-LLM concurrency and ordered persistence turn raw archives into traceable case collections.</p><a href="/TattvaDrishti-NCSRC-Dossier.pdf" target="_blank" className="text-button">Read the technical dossier <ArrowRight size={17} /></a></div>
          <div className="scale-metrics">
            <div><b>5,000</b><span>default records<br />per batch</span></div><div><b>25 <small>MiB</small></b><span>default archive<br />upload limit</span></div><div><b>16</b><span>default transformer<br />batch size</span></div><div><b>2</b><span>bounded concurrent<br />local-LLM calls</span></div>
          </div>
          <p className="benchmark-note"><Activity size={15} /> Team-observed demonstration: ~150 messages in approximately 10–15 seconds on a specific setup. This is not a formal benchmark.</p>
        </div>
      </section>

      <section className="trust-section section-shell">
        <div className="container trust-grid">
          <div className="trust-visual"><div className="trust-rings"><ShieldCheck /></div><span className="trust-tag tag-a">Local-first</span><span className="trust-tag tag-b">Signed</span><span className="trust-tag tag-c">Auditable</span></div>
          <div className="trust-copy"><span className="section-index">07 / TRUST BY DESIGN</span><h2>Sovereign where it matters.<br /><em>Accountable everywhere.</em></h2><p>Core text analysis can run locally. Evidence receives fingerprints, timestamps and audit events. Sharing defaults to redaction and adds explicit justification, signing and encryption.</p><div className="trust-points"><span><Fingerprint /> Evidence integrity</span><span><LockKeyhole /> Controlled sharing</span><span><Database /> Local deployment</span><span><Globe2 /> Interoperability path</span></div><div className="responsible-note"><ShieldCheck /><div><b>Responsible-use boundary</b><p>TattvaDrishti does not establish truth, guilt or malicious intent. High-impact decisions require corroboration, lawful authority and human judgement.</p></div></div></div>
        </div>
      </section>

      <section className="stack-section section-shell">
        <div className="container"><span>BUILT WITH</span><div className="stack-list">{stack.map((item) => <b key={item}>{item}</b>)}</div></div>
      </section>

      <section className="closing-section section-shell">
        <div className="closing-grid" />
        <div className="container closing-inner">
          <span className="section-index">TATTVADRISHTI / NCSRC 2026</span>
          <h2>Don’t replace the analyst.<br /><em>Expand their field of view.</em></h2>
          <p>We’re building toward an independently evaluated, secure and interoperable pilot for responsible intelligence work.</p>
          <div className="closing-actions"><a href="/TattvaDrishti-NCSRC-Dossier.pdf" target="_blank" className="primary-button">View project dossier <ArrowRight size={18} /></a><a href="https://github.com/shoaib2000857/TattvaDrishti-AICTE-Internship" target="_blank" rel="noreferrer" className="secondary-button"><Github size={18} /> Explore the repository</a></div>
        </div>
      </section>

      <footer>
        <div className="container footer-top"><Logo /><div><b>Team ASHTOJ</b><span>Keshav Memorial Institute of Technology, Hyderabad</span></div><div><b>Presented at NCSRC 2026</b><span>National Cyber Security Research Council</span></div></div>
        <div className="container footer-bottom"><span>© 2026 Team ASHTOJ. Prototype for research and demonstration.</span><a href="#top">Back to top ↑</a></div>
      </footer>
    </main>
  );
}
