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
            onChange={(event) => setFile(event.target.files?.[0] || null)}
            className="mt-2 block w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2.5 text-sm text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-cyan-500/15 file:px-3 file:py-1.5 file:font-semibold file:text-cyan-200"
          />
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
    </section>
  );
}
