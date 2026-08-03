"use client";

import { useState } from "react";
import { submitBatchFile } from "@/lib/api";

export default function BatchUpload({ onComplete, onError }) {
  const [file, setFile] = useState(null);
  const [sourceSystem, setSourceSystem] = useState("");
  const [collectionId, setCollectionId] = useState("");
  const [classificationMarking, setClassificationMarking] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [lastBatch, setLastBatch] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [previewState, setPreviewState] = useState(null);

  const togglePreview = () => {
    if (showPreview) {
      setShowPreview(false);
      return;
    }
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const preview = parseBulkPreview(reader.result || "");
      setPreviewState(preview);
      setShowPreview(true);
    };
    reader.onerror = () => {
      setPreviewState({
        error: "Could not parse file. Check that it is valid JSON.",
        messages: [],
        total: 0,
        valid: 0,
        invalid: 0,
      });
      setShowPreview(true);
    };
    reader.readAsText(file);
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!file) {
      onError?.("Choose a JSON, JSONL, or NDJSON message file.");
      return;
    }
    try {
      setIsUploading(true);
      const response = await submitBatchFile({
        file,
        sourceSystem: sourceSystem.trim() || "analyst-upload",
        collectionId: collectionId.trim(),
        classificationMarking: classificationMarking.trim(),
      });
      setLastBatch(response);
      onComplete?.(response);
    } catch (error) {
      onError?.(error.message || "Batch upload failed.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/70 p-6 shadow-2xl shadow-black/30">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-cyan-300">Bulk collection intake</p>
          <h2 className="mt-2 text-xl font-semibold text-white">Process a message archive</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Upload a versioned JSON envelope or one message object per line. Invalid records are reported without cancelling valid records.
          </p>
        </div>
      </div>

      <form onSubmit={submit} className="mt-5 grid gap-4 md:grid-cols-2">
        <label className="text-sm font-medium text-slate-200">
          Message archive
          <input
            type="file"
            accept=".json,.jsonl,.ndjson,application/json,application/x-ndjson"
            onChange={(event) => {
              setFile(event.target.files?.[0] || null);
              setShowPreview(false);
              setPreviewState(null);
            }}
            className="mt-2 block w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2.5 text-sm text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-cyan-500/15 file:px-3 file:py-1.5 file:font-semibold file:text-cyan-200"
          />
          {file && (
            <div className="mt-2 space-y-2">
              <p className="font-mono text-xs text-slate-500">{file.name}</p>
              <button
                type="button"
                onClick={togglePreview}
                className="rounded-full border border-violet-500/40 bg-violet-500/10 px-4 py-1.5 text-xs font-semibold text-violet-200 transition hover:bg-violet-500/20"
              >
                {showPreview ? "Hide preview" : "Preview messages"}
              </button>
            </div>
          )}
        </label>
        <label className="text-sm font-medium text-slate-200">
          Source system
          <input
            value={sourceSystem}
            onChange={(event) => setSourceSystem(event.target.value)}
            placeholder="agency-chat-export"
            className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/70 px-3.5 py-3 text-sm text-slate-100 placeholder:text-slate-500"
          />
        </label>
        <label className="text-sm font-medium text-slate-200">
          Collection ID <span className="font-normal text-slate-500">(optional)</span>
          <input
            value={collectionId}
            onChange={(event) => setCollectionId(event.target.value)}
            placeholder="collection-2026-07"
            className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/70 px-3.5 py-3 text-sm text-slate-100 placeholder:text-slate-500"
          />
        </label>
        <label className="text-sm font-medium text-slate-200">
          Classification marking <span className="font-normal text-slate-500">(optional)</span>
          <input
            value={classificationMarking}
            onChange={(event) => setClassificationMarking(event.target.value)}
            placeholder="OFFICIAL:SENSITIVE"
            className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950/70 px-3.5 py-3 text-sm text-slate-100 placeholder:text-slate-500"
          />
        </label>
        <div className="flex flex-wrap items-center gap-4 md:col-span-2">
          <button
            type="submit"
            disabled={isUploading}
            className="rounded-xl bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isUploading ? "Processing batch…" : "Upload and process"}
          </button>
          {lastBatch && (
            <p className="text-sm text-slate-300">
              Batch <span className="font-mono text-xs text-slate-400">{lastBatch.batch_id}</span>: {lastBatch.succeeded} succeeded, {lastBatch.failed} failed.
            </p>
          )}
        </div>
      </form>
      {showPreview && (
        <BulkPreviewPanel
          preview={previewState}
          onClose={() => setShowPreview(false)}
        />
      )}
    </section>
  );
}

function BulkPreviewPanel({ preview, onClose }) {
  if (!preview || preview.error || preview.messages.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6 backdrop-blur-sm">
        <div className="w-full max-w-2xl overflow-hidden rounded-3xl border border-white/10 bg-slate-950 shadow-2xl shadow-black/60">
          <div className="flex items-start justify-between gap-4 border-b border-white/10 px-6 py-5">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-violet-300">
                Message preview
              </p>
              <h3 className="mt-2 text-lg font-semibold text-white">
                Bulk archive check
              </h3>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold text-slate-300 transition hover:bg-white/10"
            >
              Close
            </button>
          </div>
          <div className="px-6 py-5">
            <p className="rounded-2xl border border-rose-500/20 bg-rose-500/10 px-5 py-4 text-xs text-rose-400">
              Could not parse file. Check that it is valid JSON.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const shownMessages = preview.messages.slice(0, 10);
  const hiddenCount = Math.max(0, preview.messages.length - shownMessages.length);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6 backdrop-blur-sm">
      <div className="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-3xl border border-white/10 bg-slate-950 shadow-2xl shadow-black/60">
        <div className="flex items-start justify-between gap-4 border-b border-white/10 px-6 py-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-violet-300">
              Message preview
            </p>
            <h3 className="mt-2 text-lg font-semibold text-white">
              Bulk archive check
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-semibold text-slate-300 transition hover:bg-white/10"
          >
            Close
          </button>
        </div>
        <div className="border-b border-white/10 px-6 py-4">
          <div className="flex flex-wrap gap-4 text-[11px] text-slate-500">
            <span>{preview.total} total messages</span>
            <span>{preview.valid} valid</span>
            <span>{preview.invalid} invalid</span>
          </div>
        </div>
        <div className="max-h-96 overflow-y-auto px-6 py-5">
          <div className="space-y-3">
            {shownMessages.map((message, index) => (
              <article
                key={index}
                className="space-y-2 rounded-xl border border-white/10 bg-slate-900/60 px-4 py-3 text-sm text-slate-200"
              >
                {message.text || message.content ? (
                  <p className="whitespace-pre-wrap">{message.text || message.content}</p>
                ) : (
                  <p className="text-xs text-slate-500">
                    Unknown format — keys: [{Object.keys(message).join(", ")}]
                  </p>
                )}
                <MessageMetadata message={message} />
              </article>
            ))}
          </div>
          {hiddenCount > 0 && (
            <p className="mt-3 text-xs text-slate-500">
              + {hiddenCount} more messages not shown
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function MessageMetadata({ message }) {
  const fields = ["source", "platform", "region", "actor_id", "tags", "language"];
  const entries = fields
    .filter((field) => message[field] !== undefined && message[field] !== null && message[field] !== "")
    .map((field) => {
      const value = Array.isArray(message[field])
        ? message[field].join(", ")
        : String(message[field]);
      return `${field}: ${value}`;
    });

  if (entries.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {entries.map((entry) => (
        <span
          key={entry}
          className="rounded-full border border-white/10 bg-slate-800 px-2 py-0.5 text-[10px] text-slate-400"
        >
          {entry}
        </span>
      ))}
    </div>
  );
}

function parseBulkPreview(rawText) {
  const raw = String(rawText).trim();
  if (!raw) {
    return createBulkPreviewError();
  }

  try {
    const parsed = JSON.parse(raw);
    const messages = Array.isArray(parsed)
      ? parsed
      : Array.isArray(parsed?.messages)
      ? parsed.messages
      : [];
    const validMessages = messages.filter((message) => message && typeof message === "object" && !Array.isArray(message));

    if (validMessages.length === 0) {
      return createBulkPreviewError();
    }

    return {
      error: "",
      messages: validMessages,
      total: messages.length,
      valid: validMessages.length,
      invalid: messages.length - validMessages.length,
    };
  } catch {
    const lines = raw.split(/\r?\n/).filter((line) => line.trim());
    const messages = [];
    let invalid = 0;

    lines.forEach((line) => {
      try {
        const parsedLine = JSON.parse(line);
        if (parsedLine && typeof parsedLine === "object" && !Array.isArray(parsedLine)) {
          messages.push(parsedLine);
        } else {
          invalid += 1;
        }
      } catch {
        invalid += 1;
      }
    });

    if (messages.length === 0) {
      return createBulkPreviewError();
    }

    return {
      error: "",
      messages,
      total: lines.length,
      valid: messages.length,
      invalid,
    };
  }
}

function createBulkPreviewError() {
  return {
    error: "Could not parse file. Check that it is valid JSON.",
    messages: [],
    total: 0,
    valid: 0,
    invalid: 0,
  };
}
