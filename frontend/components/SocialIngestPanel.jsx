"use client";

import { useMemo, useState } from "react";
import { ingestTelegramLink } from "@/lib/api";

const telegramUrlPattern =
  /^https?:\/\/(?:www\.)?(?:t\.me|telegram\.me)\/[A-Za-z0-9_]{3,64}\/\d+(?:[/?#].*)?$/i;

const formatPercent = (value) =>
  typeof value === "number" ? `${Math.round(value)}%` : "0%";

const formatDecimal = (value, digits = 1) =>
  typeof value === "number" ? value.toFixed(digits) : "0";

export default function SocialIngestPanel() {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const isValid = useMemo(() => {
    const value = url.trim();
    return value.length === 0 || telegramUrlPattern.test(value);
  }, [url]);

  const prediction = result?.prediction || "";
  const predictionTag = result?.prediction_tag || "Standby";
  const analytics = result?.analytics || {};
  const metadata = result?.metadata || {};
  const humanConfidence =
    typeof result?.human_confidence === "number" ? result.human_confidence : 0;
  const aiConfidence =
    typeof result?.ai_confidence === "number" ? result.ai_confidence : 0;
  const primaryConfidence = prediction === "AI" ? aiConfidence : humanConfidence;
  const leansAi = String(prediction).toLowerCase() === "ai";
  const accent = leansAi
    ? {
        label: predictionTag,
        text: "text-cyan-200",
        glow: "shadow-cyan-500/20",
        border: "border-cyan-300/30",
        bg: "bg-cyan-400/10",
      }
    : {
        label: predictionTag,
        text: "text-emerald-200",
        glow: "shadow-emerald-500/20",
        border: "border-emerald-300/30",
        bg: "bg-emerald-400/10",
      };

  const handleUrlChange = (event) => {
    const value = event.target.value;
    setUrl(value);
    setResult(null);
    if (!value.trim()) {
      setError("");
      return;
    }
    setError(
      telegramUrlPattern.test(value.trim())
        ? ""
        : "Enter a public Telegram post link like https://t.me/channel/123."
    );
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const cleanedUrl = url.trim();
    if (!cleanedUrl) {
      setError("Paste a public Telegram post link first.");
      return;
    }
    if (!telegramUrlPattern.test(cleanedUrl)) {
      setError("Enter a public Telegram post link like https://t.me/channel/123.");
      return;
    }

    try {
      setIsLoading(true);
      setError("");
      const payload = await ingestTelegramLink({ url: cleanedUrl });
      setResult(payload);
    } catch (requestError) {
      setResult(null);
      setError(requestError.message || "Unable to analyze this Telegram post.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="relative overflow-hidden rounded-2xl border border-white/10 bg-slate-950/90 shadow-2xl shadow-black/40">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/70 to-transparent" />
      <div className="absolute inset-y-0 right-0 w-px bg-gradient-to-b from-cyan-300/0 via-fuchsia-400/40 to-emerald-300/0" />

      <div className="grid gap-0 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="border-b border-white/10 p-6 xl:border-b-0 xl:border-r">
          <div className="flex flex-col gap-2">
            <p className="text-xs font-bold uppercase tracking-[0.28em] text-cyan-300">
              Telegram Signal Intake
            </p>
            <h2 className="text-2xl font-semibold text-white">
              Public post extraction console
            </h2>
            <p className="max-w-2xl text-sm leading-6 text-slate-400">
              Ingest a public Telegram post, normalize the message body, and route it into the DeBERTa-v3 LoRA detector.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <label className="block">
              <span className="text-sm font-semibold text-slate-200">Public Telegram URL</span>
              <div className="mt-2 flex flex-col gap-3 lg:flex-row">
                <input
                  value={url}
                  onChange={handleUrlChange}
                  placeholder="Paste public Telegram link (e.g., https://t.me/channel/123)..."
                  className={`min-h-12 flex-1 rounded-lg border bg-black/40 px-4 py-3 font-mono text-sm text-slate-100 placeholder:text-slate-600 outline-none transition duration-300 focus:ring-2 ${
                    error
                      ? "border-rose-400/60 focus:border-rose-300 focus:ring-rose-500/30"
                      : "border-white/10 focus:border-cyan-300 focus:ring-cyan-400/30"
                  }`}
                  aria-invalid={!isValid}
                />
                <button
                  type="submit"
                  disabled={isLoading || !url.trim() || !isValid}
                  className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-cyan-300 px-6 py-3 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-500/20 transition duration-300 hover:bg-cyan-200 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
                >
                  {isLoading && (
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-900/20 border-t-slate-950" />
                  )}
                  {isLoading ? "Analyzing..." : "Analyze Post"}
                </button>
              </div>
            </label>

            {error && (
              <div className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm font-medium text-rose-200">
                {error}
              </div>
            )}
          </form>

          <div className="mt-6 rounded-xl border border-white/10 bg-black/30 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-xs font-bold uppercase tracking-[0.24em] text-slate-400">
                Extracted Text
              </h3>
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 font-mono text-xs text-slate-300">
                {result?.text_length || analytics.total_characters || 0} chars
              </span>
            </div>
            {isLoading ? (
              <div className="mt-4 space-y-3">
                <div className="h-4 w-11/12 animate-pulse rounded bg-white/10" />
                <div className="h-4 w-10/12 animate-pulse rounded bg-white/10" />
                <div className="h-4 w-8/12 animate-pulse rounded bg-white/10" />
                <div className="h-44 animate-pulse rounded-lg bg-white/[0.06]" />
              </div>
            ) : (
              <textarea
                readOnly
                value={result?.extracted_text || ""}
                placeholder="Awaiting Telegram extraction..."
                className="mt-4 h-80 w-full resize-none rounded-lg border border-white/10 bg-slate-950/80 p-4 font-mono text-sm leading-6 text-slate-200 outline-none placeholder:text-slate-700"
              />
            )}
          </div>
        </div>

        <div className="p-6">
          <div className="flex flex-col gap-2">
            <p className="text-xs font-bold uppercase tracking-[0.28em] text-fuchsia-300">
              Analysis Command Center
            </p>
            <h3 className="text-2xl font-semibold text-white">AI forensics telemetry</h3>
          </div>

          <div
            className={`mt-6 rounded-xl border p-5 shadow-2xl transition duration-500 ${accent.border} ${accent.bg} ${accent.glow}`}
          >
            {isLoading ? (
              <div className="space-y-5">
                <div className="h-5 w-40 animate-pulse rounded bg-white/10" />
                <div className="h-10 w-56 animate-pulse rounded bg-white/10" />
                <div className="h-4 animate-pulse rounded-full bg-white/10" />
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.24em] text-slate-400">
                      Prediction vector
                    </p>
                    <p className={`mt-2 text-4xl font-semibold ${accent.text}`}>
                      {prediction || "Standby"}
                    </p>
                  </div>
                  <span className={`rounded-full border px-3 py-1 font-mono text-xs ${accent.border} ${accent.text}`}>
                    {accent.label} | {formatPercent(primaryConfidence)}
                  </span>
                </div>
                <div className="mt-6">
                  <div className="mb-2 flex items-center justify-between font-mono text-xs text-slate-400">
                    <span>classification spectrum</span>
                    <span>Human {formatPercent(humanConfidence)} / AI {formatPercent(aiConfidence)}</span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-black/60 ring-1 ring-white/10">
                    <div
                      className="flex h-full w-full transition-all duration-700"
                    >
                      <div
                        className="h-full bg-gradient-to-r from-emerald-300 via-green-400 to-teal-300"
                        style={{ width: `${result ? humanConfidence : 0}%` }}
                      />
                      <div
                        className="h-full bg-gradient-to-r from-cyan-300 via-sky-400 to-fuchsia-400"
                        style={{ width: `${result ? aiConfidence : 0}%` }}
                      />
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-3 font-mono text-xs">
                    <span className="rounded bg-emerald-400/10 px-2 py-1 text-emerald-200">
                      HUMAN {formatPercent(humanConfidence)}
                    </span>
                    <span className="rounded bg-cyan-400/10 px-2 py-1 text-cyan-200">
                      AI {formatPercent(aiConfidence)}
                    </span>
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <MetricTile
              label="Lexical Richness"
              value={formatPercent(analytics.lexical_richness)}
              detail="unique words"
              loading={isLoading}
              tone="emerald"
            />
            <MetricTile
              label="Structural Pace"
              value={formatDecimal(analytics.words_per_sentence)}
              detail="words / sentence"
              loading={isLoading}
              tone="cyan"
            />
            <MetricTile
              label="Stylometric Markers"
              value={`${analytics.exclamation_markers || 0}`}
              detail="exclamation markers"
              loading={isLoading}
              tone="fuchsia"
            />
            <MetricTile
              label="Volumetrics"
              value={`${analytics.total_words || 0}`}
              detail={`${analytics.total_characters || 0} chars | ${analytics.total_sentences || 0} ${analytics.total_sentences === 1 ? "sentence boundary" : "sentence boundaries"}`}
              loading={isLoading}
              tone="slate"
            />
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <SystemBadge label="Source: Telegram" />
            <SystemBadge label={`Channel: ${metadata.channel || "pending"}`} />
            <SystemBadge label={`Post: ${metadata.post_id || "pending"}`} />
            <SystemBadge label={`Model: ${"DeBERTa-v3-Lora"}`} />
          </div>
        </div>
      </div>
    </section>
  );
}

function MetricTile({ label, value, detail, loading, tone }) {
  const toneClass =
    tone === "emerald"
      ? "text-emerald-200 border-emerald-300/20"
      : tone === "cyan"
      ? "text-cyan-200 border-cyan-300/20"
      : tone === "fuchsia"
      ? "text-fuchsia-200 border-fuchsia-300/20"
      : "text-slate-200 border-white/10";

  return (
    <div className={`rounded-xl bg-white/[0.045] p-4 ring-1 ring-white/[0.03] ${toneClass}`}>
      {loading ? (
        <div className="space-y-3">
          <div className="h-3 w-28 animate-pulse rounded bg-white/10" />
          <div className="h-8 w-20 animate-pulse rounded bg-white/10" />
          <div className="h-3 w-24 animate-pulse rounded bg-white/10" />
        </div>
      ) : (
        <>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">
            {label}
          </p>
          <p className="mt-3 text-3xl font-semibold">{value}</p>
          <p className="mt-1 break-words font-mono text-xs leading-5 text-slate-500">{detail}</p>
        </>
      )}
    </div>
  );
}

function SystemBadge({ label }) {
  return (
    <span className="rounded-md border border-white/10 bg-zinc-900 px-2.5 py-1 font-mono text-xs text-cyan-200 shadow-sm shadow-cyan-500/10">
      [{label}]
    </span>
  );
}
