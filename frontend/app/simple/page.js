"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import IntakeForm from "@/components/IntakeForm";
import ImageAnalyzer from "@/components/ImageAnalyzer";
import Toast from "@/components/Toast";
import { submitIntake, fetchCase, createEventStream } from "@/lib/api";

const HISTORY_LIMIT = 8;

export default function SimpleDashboardPage() {
  const [cases, setCases] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingCase, setIsLoadingCase] = useState(false);
  const [activeTool, setActiveTool] = useState("message");
  const [riskFilter, setRiskFilter] = useState("all");
  const [streamStatus, setStreamStatus] = useState("connecting");
  const [toast, setToast] = useState({ message: "", tone: "success" });
  const submissionsRef = useRef({});
  const eventControllerRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const intakeSectionRef = useRef(null);

  useEffect(() => {
    const timer = toast.message
      ? setTimeout(() => setToast({ message: "", tone: "success" }), 4200)
      : null;
    return () => timer && clearTimeout(timer);
  }, [toast]);

  const sortCases = (data) =>
    [...data].sort((a, b) => {
      const dateA = a.submitted_at ? new Date(a.submitted_at).getTime() : 0;
      const dateB = b.submitted_at ? new Date(b.submitted_at).getTime() : 0;
      return dateB - dateA;
    });

  const upsertCase = (result) => {
    if (!result?.intake_id) return;
    setCases((previous) => {
      const existingIndex = previous.findIndex(
        (item) => item.intake_id === result.intake_id
      );
      if (existingIndex >= 0) {
        const updated = [...previous];
        updated[existingIndex] = { ...updated[existingIndex], ...result };
        return sortCases(updated);
      }
      return sortCases([result, ...previous]);
    });
  };

  const startEventStream = () => {
    if (eventControllerRef.current) return;
    setStreamStatus("connecting");
    const source = createEventStream(
      async (event) => {
        setStreamStatus("live");
        upsertCase({
          intake_id: event.intake_id,
          submitted_at: event.submitted_at,
          classification: event.classification,
          composite_score: event.score,
        });
        try {
          const hydrated = await fetchCase(event.intake_id);
          upsertCase(hydrated);
        } catch (error) {
          console.error("Failed to hydrate case via simplified stream", error);
        }
      },
      () => {
        setStreamStatus("reconnecting");
        if (eventControllerRef.current) {
          eventControllerRef.current.close();
          eventControllerRef.current = null;
        }
        if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = setTimeout(() => startEventStream(), 4000);
      }
    );
    source.onopen = () => setStreamStatus("live");
    eventControllerRef.current = source;
  };

  useEffect(() => {
    startEventStream();
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (eventControllerRef.current) {
        eventControllerRef.current.close();
        eventControllerRef.current = null;
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmitIntake = async (payload) => {
    try {
      setIsSubmitting(true);
      const result = await submitIntake(payload);
      submissionsRef.current[result.intake_id] = payload;
      upsertCase(result);
      setSelectedId(result.intake_id);
      setToast({ message: "Analysis complete. Review the priority result.", tone: "success" });
      return true;
    } catch (error) {
      setToast({
        message: `Unable to analyse this message: ${error.message}`,
        tone: "error",
      });
      return false;
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSelectCase = async (intakeId) => {
    if (!intakeId) return;
    setSelectedId(intakeId);
    setIsLoadingCase(true);
    try {
      const hydrated = await fetchCase(intakeId);
      upsertCase(hydrated);
      requestAnimationFrame(() => {
        document.getElementById("analysis-result")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      });
    } catch (error) {
      setToast({
        message: `Unable to load the selected analysis: ${error.message}`,
        tone: "error",
      });
    } finally {
      setIsLoadingCase(false);
    }
  };

  const metrics = useMemo(() => {
    const total = cases.length;
    const highRisk = cases.filter(
      (item) => getRiskLevel(item.classification, item.composite_score).key === "high"
    ).length;
    const needsReview = cases.filter(
      (item) => getRiskLevel(item.classification, item.composite_score).key === "medium"
    ).length;
    const average =
      total === 0
        ? 0
        : Math.round(
            (cases.reduce((sum, item) => sum + (item.composite_score || 0), 0) /
              total) *
              100
          );
    return { total, highRisk, needsReview, average };
  }, [cases]);

  const filteredCases = useMemo(() => {
    if (riskFilter === "all") return cases;
    return cases.filter(
      (item) => getRiskLevel(item.classification, item.composite_score).key === riskFilter
    );
  }, [cases, riskFilter]);

  const selectedCase = cases.find((item) => item.intake_id === selectedId);
  const submissionPayload = submissionsRef.current[selectedId] || null;

  const startNewAnalysis = () => {
    setActiveTool("message");
    intakeSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    setTimeout(() => document.getElementById("payload-text")?.focus(), 450);
  };

  return (
    <div className="simple-dashboard min-h-screen overflow-x-hidden bg-[#f4f6f8] text-slate-950">
      <a
        href="#main-content"
        className="fixed left-4 top-3 z-[60] -translate-y-20 rounded-lg bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition focus:translate-y-0"
      >
        Skip to main content
      </a>

      <AppHeader streamStatus={streamStatus} onNewAnalysis={startNewAnalysis} />

      <main id="main-content" className="mx-auto w-full max-w-[96rem] px-4 pb-20 pt-8 sm:px-6 lg:px-8">
        <WelcomePanel onStart={startNewAnalysis} />
        <SimpleStats metrics={metrics} />

        <section
          ref={intakeSectionRef}
          id="analysis-workspace"
          className="mt-6 grid scroll-mt-24 gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]"
        >
          <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-5 pt-5 sm:px-7 sm:pt-7">
              <div className="flex items-start gap-3">
                <StepNumber value="1" />
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-700">
                    Start analysis
                  </p>
                  <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950 sm:text-2xl">
                    What would you like to check?
                  </h2>
                  <p className="mt-1 text-sm leading-6 text-slate-500">
                    Choose a content type. Your information stays within the analysis workflow.
                  </p>
                </div>
              </div>

              <div className="mt-6 flex gap-1 rounded-xl bg-slate-100 p-1" role="tablist" aria-label="Analysis type">
                <ToolTab
                  active={activeTool === "message"}
                  onClick={() => setActiveTool("message")}
                  icon="message"
                  label="Message or text"
                />
                <ToolTab
                  active={activeTool === "image"}
                  onClick={() => setActiveTool("image")}
                  icon="image"
                  label="Image or media"
                />
              </div>
            </div>

            <div className="p-5 sm:p-7">
              {activeTool === "message" ? (
                <IntakeForm
                  onSubmit={handleSubmitIntake}
                  isSubmitting={isSubmitting}
                  onValidationError={(message) => setToast({ message, tone: "error" })}
                  variant="simple"
                  metadataLabelStyle="bold"
                />
              ) : (
                <ImageAnalyzer variant="simple" />
              )}
            </div>
          </div>

          <div id="analysis-result" className="scroll-mt-24">
            <CaseOverview
              caseData={selectedCase}
              submission={submissionPayload}
              isLoading={isLoadingCase}
              onStart={startNewAnalysis}
            />
          </div>
        </section>

        <ResultHistory
          items={filteredCases}
          totalItems={cases.length}
          selectedId={selectedId}
          activeFilter={riskFilter}
          onFilter={setRiskFilter}
          onSelect={handleSelectCase}
        />

        <footer className="mt-8 flex flex-col gap-2 border-t border-slate-200 pt-6 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <p>TattvaDrishti decision-support interface · Human review remains essential.</p>
          <p>Results indicate priority, not guilt or intent.</p>
        </footer>
      </main>

      <Toast message={toast.message} tone={toast.tone} />
    </div>
  );
}

function AppHeader({ streamStatus, onNewAnalysis }) {
  const status = {
    live: { label: "Live monitoring", dot: "bg-emerald-500" },
    connecting: { label: "Connecting", dot: "bg-amber-500" },
    reconnecting: { label: "Reconnecting", dot: "bg-amber-500" },
  }[streamStatus];

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/90 bg-white/95 backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-[96rem] items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-slate-950 text-white shadow-sm">
            <Icon name="focus" className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="truncate font-semibold tracking-tight text-slate-950">TattvaDrishti</p>
            <p className="hidden text-[11px] font-medium uppercase tracking-[0.13em] text-slate-500 sm:block">
              Rapid message assessment
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <div className="hidden items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600 md:flex">
            <span className={`h-2 w-2 rounded-full ${status.dot} ${streamStatus !== "live" ? "animate-pulse" : ""}`} />
            {status.label}
          </div>
          <button
            type="button"
            onClick={onNewAnalysis}
            className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-blue-700 px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200"
          >
            <Icon name="plus" className="h-4 w-4" />
            <span className="hidden sm:inline">New analysis</span>
            <span className="sm:hidden">New</span>
          </button>
          <Link
            href="/"
            className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-slate-100"
          >
            <Icon name="settings" className="h-4 w-4" />
            <span className="hidden lg:inline">Analyst workspace</span>
          </Link>
        </div>
      </div>
    </header>
  );
}

function WelcomePanel({ onStart }) {
  return (
    <section className="relative overflow-hidden rounded-3xl bg-slate-950 px-6 py-7 text-white shadow-xl shadow-slate-900/10 sm:px-8 sm:py-9">
      <div className="absolute -right-16 -top-24 h-72 w-72 rounded-full border-[44px] border-blue-500/15" aria-hidden="true" />
      <div className="absolute -bottom-28 right-36 h-52 w-52 rounded-full bg-blue-600/10 blur-2xl" aria-hidden="true" />
      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-semibold text-blue-200">
            <Icon name="shield" className="h-3.5 w-3.5" />
            Fast, guided and plain-language
          </div>
          <h1 className="mt-4 max-w-2xl text-3xl font-semibold leading-tight tracking-[-0.03em] sm:text-4xl lg:text-[2.7rem]">
            Understand a suspicious message in minutes.
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
            Paste content, add its location, and receive a clear priority level with the signals that influenced it.
          </p>
        </div>
        <button
          type="button"
          onClick={onStart}
          className="inline-flex min-h-12 shrink-0 items-center justify-center gap-2 self-start rounded-xl bg-white px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-blue-50 focus:outline-none focus:ring-4 focus:ring-blue-400/40 lg:self-auto"
        >
          Check a message
          <Icon name="arrow" className="h-4 w-4" />
        </button>
      </div>
    </section>
  );
}

function SimpleStats({ metrics }) {
  const stats = [
    { label: "Analysed this session", value: metrics.total, icon: "document", tone: "blue" },
    { label: "High priority", value: metrics.highRisk, icon: "alert", tone: "rose" },
    { label: "Needs review", value: metrics.needsReview, icon: "review", tone: "amber" },
    { label: "Average risk score", value: `${metrics.average}%`, icon: "chart", tone: "slate" },
  ];

  const tones = {
    blue: "bg-blue-50 text-blue-700",
    rose: "bg-rose-50 text-rose-700",
    amber: "bg-amber-50 text-amber-700",
    slate: "bg-slate-100 text-slate-700",
  };

  return (
    <section className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Session summary">
      {stats.map((item) => (
        <article key={item.label} className="flex min-h-24 min-w-0 items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
          <div className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${tones[item.tone]}`}>
            <Icon name={item.icon} className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="text-2xl font-semibold tracking-tight text-slate-950">{item.value}</p>
            <p className="mt-0.5 text-xs font-medium leading-4 text-slate-500">{item.label}</p>
          </div>
        </article>
      ))}
    </section>
  );
}

function ToolTab({ active, onClick, icon, label }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={`flex min-h-11 flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition focus:outline-none focus:ring-4 focus:ring-blue-100 ${
        active ? "bg-white text-blue-800 shadow-sm" : "text-slate-500 hover:text-slate-800"
      }`}
    >
      <Icon name={icon} className="h-4 w-4" />
      {label}
    </button>
  );
}

function StepNumber({ value }) {
  return (
    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-blue-50 text-sm font-bold text-blue-700">
      {value}
    </span>
  );
}

function CaseOverview({ caseData, submission, isLoading, onStart }) {
  const [copied, setCopied] = useState(false);

  if (!caseData) {
    return (
      <section className="flex min-h-[38rem] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-start gap-3 border-b border-slate-200 px-5 py-5 sm:px-7 sm:py-7">
          <StepNumber value="2" />
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">Result</p>
            <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950 sm:text-2xl">Your assessment appears here</h2>
          </div>
        </div>
        <div className="grid flex-1 place-items-center px-6 py-12 text-center">
          <div className="max-w-md">
            <div className="mx-auto grid h-20 w-20 place-items-center rounded-3xl bg-blue-50 text-blue-700">
              <Icon name="scan" className="h-9 w-9" />
            </div>
            <h3 className="mt-6 text-xl font-semibold text-slate-950">Ready when you are</h3>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              Add a message and its location. TattvaDrishti will show the priority, a short explanation, and any important signals.
            </p>
            <div className="mt-6 grid gap-2 text-left text-sm text-slate-600 sm:grid-cols-3">
              {[
                ["1", "Paste content"],
                ["2", "Add location"],
                ["3", "Review result"],
              ].map(([number, label]) => (
                <div key={number} className="flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2.5">
                  <span className="font-bold text-blue-700">{number}</span>
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    );
  }

  const heuristics = Array.isArray(caseData?.breakdown?.heuristics)
    ? caseData.breakdown.heuristics.slice(0, 6)
    : [];
  const metadataEntries = submission?.metadata
    ? Object.entries(submission.metadata).filter(([, value]) => Boolean(value) && value !== "unspecified")
    : [];
  const numericScore = typeof caseData.composite_score === "number" ? caseData.composite_score : null;
  const score = numericScore !== null ? `${Math.round(numericScore * 100)}%` : "Pending";
  const risk = getRiskLevel(caseData.classification, caseData.composite_score);
  const summaryText =
    caseData.summary ||
    caseData.assessment ||
    caseData.reason ||
    caseData.findings ||
    "A detailed explanation will appear when the analysis pipeline returns the complete result.";
  const narrativeText =
    caseData.cleaned_text || caseData.text || submission?.text || "Original message is unavailable for this case.";

  const copyCaseId = async () => {
    try {
      await navigator.clipboard.writeText(caseData.intake_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className={`border-b px-5 py-5 sm:px-7 sm:py-7 ${risk.header}`}>
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <span className={`mt-1 h-3 w-3 shrink-0 rounded-full ${risk.dot}`} />
            <div>
              <p className={`text-xs font-bold uppercase tracking-[0.16em] ${risk.text}`}>Assessment complete</p>
              <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">{risk.priority}</h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-slate-600">{risk.recommendation}</p>
            </div>
          </div>
          <div className={`shrink-0 rounded-2xl border px-4 py-3 text-right ${risk.scoreCard}`}>
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Risk score</p>
            <p className={`mt-0.5 text-3xl font-semibold tracking-tight ${risk.text}`}>{score}</p>
          </div>
        </div>
        {numericScore !== null && (
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-white/80">
            <div className={`h-full rounded-full transition-all duration-700 ${risk.bar}`} style={{ width: `${Math.round(numericScore * 100)}%` }} />
          </div>
        )}
      </div>

      <div className="space-y-5 p-5 sm:p-7">
        {isLoading && (
          <div className="flex items-center gap-2 rounded-xl bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700">
            <span className="h-2 w-2 animate-pulse rounded-full bg-blue-600" />
            Refreshing full case details…
          </div>
        )}

        <section>
          <div className="flex items-center gap-2">
            <Icon name="summary" className="h-5 w-5 text-blue-700" />
            <h3 className="text-sm font-bold uppercase tracking-[0.12em] text-slate-700">What the system found</h3>
          </div>
          <p className="mt-3 text-base leading-7 text-slate-800">{summaryText}</p>
        </section>

        {caseData.decision_reason && (
          <section className="rounded-2xl border border-blue-100 bg-blue-50/70 p-4">
            <h3 className="text-sm font-semibold text-blue-950">Why this priority was assigned</h3>
            <p className="mt-2 text-sm leading-6 text-slate-700">{caseData.decision_reason}</p>
          </section>
        )}

        <section className="border-t border-slate-100 pt-5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Icon name="signal" className="h-5 w-5 text-blue-700" />
              <h3 className="text-sm font-bold uppercase tracking-[0.12em] text-slate-700">Important signals</h3>
            </div>
            <span className="text-xs text-slate-400">{heuristics.length} detected</span>
          </div>
          {heuristics.length ? (
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {heuristics.map((heuristic) => (
                <li key={heuristic} className="flex items-start gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-sm leading-5 text-slate-700">
                  <Icon name="check" className="mt-0.5 h-4 w-4 shrink-0 text-blue-700" />
                  {heuristic}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">No specific heuristic signals were flagged.</p>
          )}
        </section>

        <details className="group rounded-2xl border border-slate-200">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-4 text-sm font-semibold text-slate-800 marker:content-none">
            View original message and case details
            <Icon name="chevron" className="h-4 w-4 text-slate-400 transition group-open:rotate-180" />
          </summary>
          <div className="space-y-5 border-t border-slate-200 px-4 py-5">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.12em] text-slate-500">Original message</p>
              <p className="mt-2 whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-700">{narrativeText}</p>
            </div>
            {metadataEntries.length > 0 && (
              <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
                {metadataEntries.map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-xs font-medium capitalize text-slate-500">{key.replace(/_/g, " ")}</dt>
                    <dd className="mt-1 font-medium text-slate-800">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 text-xs text-slate-500">
              <span>{caseData.submitted_at ? formatTimestamp(caseData.submitted_at, true) : "Timestamp unavailable"}</span>
              <button type="button" onClick={copyCaseId} className="inline-flex items-center gap-1.5 font-semibold text-blue-700 hover:text-blue-900">
                <Icon name="copy" className="h-3.5 w-3.5" />
                {copied ? "Case ID copied" : "Copy case ID"}
              </button>
            </div>
          </div>
        </details>

        <div className="flex flex-col gap-3 rounded-2xl bg-slate-950 p-4 text-white sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold">Need to check another message?</p>
            <p className="mt-0.5 text-xs text-slate-400">Start a clean assessment without losing this result.</p>
          </div>
          <button type="button" onClick={onStart} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-blue-50">
            <Icon name="plus" className="h-4 w-4" />
            New analysis
          </button>
        </div>
      </div>
    </section>
  );
}

function ResultHistory({ items, totalItems, selectedId, activeFilter, onFilter, onSelect }) {
  const filters = [
    ["all", "All"],
    ["high", "High"],
    ["medium", "Review"],
    ["low", "Low"],
  ];

  return (
    <section id="recent-analyses" className="mt-6 scroll-mt-24 overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-4 border-b border-slate-200 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-7">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-blue-700">Session activity</p>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">Recent analyses</h2>
          <p className="mt-1 text-sm text-slate-500">Select any item to reopen its assessment.</p>
        </div>
        <div className="flex flex-wrap gap-1 rounded-xl bg-slate-100 p-1" aria-label="Filter analyses by priority">
          {filters.map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => onFilter(key)}
              className={`rounded-lg px-3 py-2 text-xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-blue-200 ${
                activeFilter === key ? "bg-white text-slate-950 shadow-sm" : "text-slate-500 hover:text-slate-800"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {!totalItems ? (
        <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-slate-100 text-slate-500">
            <Icon name="history" className="h-5 w-5" />
          </div>
          <p className="mt-4 text-sm font-semibold text-slate-700">No analyses in this session</p>
          <p className="mt-1 text-xs text-slate-500">Completed checks will be listed here.</p>
        </div>
      ) : !items.length ? (
        <div className="px-6 py-10 text-center text-sm text-slate-500">No results match this priority filter.</div>
      ) : (
        <div className="divide-y divide-slate-100">
          {items.slice(0, HISTORY_LIMIT).map((item) => {
            const risk = getRiskLevel(item.classification, item.composite_score);
            const score = typeof item.composite_score === "number" ? `${Math.round(item.composite_score * 100)}%` : "Pending";
            const isSelected = item.intake_id === selectedId;
            return (
              <button
                key={item.intake_id}
                type="button"
                onClick={() => onSelect(item.intake_id)}
                className={`grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 px-5 py-4 text-left transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-inset focus:ring-blue-100 sm:gap-5 sm:px-7 ${isSelected ? "bg-blue-50/60" : ""}`}
              >
                <span className={`h-3 w-3 rounded-full ${risk.dot}`} />
                <span className="min-w-0">
                  <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="font-semibold text-slate-900">{risk.priority}</span>
                    <span className="text-xs text-slate-500">{item.submitted_at ? formatTimestamp(item.submitted_at) : "Processing"}</span>
                  </span>
                  <span className="mt-1 block truncate text-xs text-slate-400">Case {shortId(item.intake_id)}</span>
                </span>
                <span className="flex items-center gap-3">
                  <span className={`rounded-lg px-2.5 py-1.5 text-sm font-bold ${risk.badge}`}>{score}</span>
                  <Icon name="chevronRight" className="hidden h-4 w-4 text-slate-400 sm:block" />
                </span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}

function getRiskLevel(classification, score) {
  const value = (classification || "").toLowerCase();
  const numeric = typeof score === "number" ? score : null;
  if (value.includes("high") || (numeric !== null && numeric >= 0.7)) {
    return {
      key: "high",
      priority: "High priority",
      recommendation: "Escalate for prompt human review and preserve the original content and source context.",
      text: "text-rose-700",
      dot: "bg-rose-600",
      bar: "bg-rose-600",
      header: "border-rose-200 bg-rose-50",
      scoreCard: "border-rose-200 bg-white/80",
      badge: "bg-rose-50 text-rose-700",
    };
  }
  if (value.includes("medium") || (numeric !== null && numeric >= 0.4)) {
    return {
      key: "medium",
      priority: "Needs review",
      recommendation: "Review the message with its source and local context before deciding on further action.",
      text: "text-amber-700",
      dot: "bg-amber-500",
      bar: "bg-amber-500",
      header: "border-amber-200 bg-amber-50",
      scoreCard: "border-amber-200 bg-white/80",
      badge: "bg-amber-50 text-amber-700",
    };
  }
  return {
    key: "low",
    priority: "Low priority",
    recommendation: "No urgent indicators were identified. Record the result and continue routine review if context requires it.",
    text: "text-emerald-700",
    dot: "bg-emerald-600",
    bar: "bg-emerald-600",
    header: "border-emerald-200 bg-emerald-50",
    scoreCard: "border-emerald-200 bg-white/80",
    badge: "bg-emerald-50 text-emerald-700",
  };
}

function Icon({ name, className = "h-5 w-5" }) {
  const paths = {
    focus: <><path d="M12 3c5.2 0 9.2 4.5 10 9-.8 4.5-4.8 9-10 9S2.8 16.5 2 12c.8-4.5 4.8-9 10-9Z"/><circle cx="12" cy="12" r="3.2"/></>,
    shield: <path d="M12 3 5 6v5c0 4.6 2.9 8.2 7 10 4.1-1.8 7-5.4 7-10V6l-7-3Zm-3 9 2 2 4-4" />,
    plus: <path d="M12 5v14M5 12h14" />,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    document: <><path d="M6 3h8l4 4v14H6V3Z"/><path d="M14 3v5h5M9 12h6M9 16h6"/></>,
    alert: <><path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 9v4m0 3.5v.1"/></>,
    review: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5M11 8v3l2 2"/></>,
    chart: <><path d="M4 20V10m6 10V4m6 16v-7m5 7H2"/></>,
    message: <path d="M4 5h16v12H8l-4 4V5Z" />,
    image: <><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m4 18 5-5 3 3 3-4 5 6"/></>,
    scan: <><path d="M8 3H4a1 1 0 0 0-1 1v4m13-5h4a1 1 0 0 1 1 1v4m0 8v4a1 1 0 0 1-1 1h-4M8 21H4a1 1 0 0 1-1-1v-4"/><circle cx="12" cy="12" r="4"/></>,
    summary: <><path d="M5 4h14v16H5z"/><path d="M8 9h8m-8 4h8m-8 4h5"/></>,
    signal: <><path d="M5 19v-2m5 2v-6m5 6V9m5 10V4"/></>,
    check: <path d="m5 12 4 4 10-10" />,
    chevron: <path d="m6 9 6 6 6-6" />,
    chevronRight: <path d="m9 6 6 6-6 6" />,
    copy: <><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5m4-1v5l3 2"/></>,
  };
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

function shortId(value) {
  if (!value) return "—";
  return value.length > 12 ? `${value.slice(0, 8)}…${value.slice(-4)}` : value;
}

function formatTimestamp(value, includeYear = false) {
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      day: "2-digit",
      month: "short",
      ...(includeYear ? { year: "numeric" } : {}),
    });
  } catch {
    return "—";
  }
}
