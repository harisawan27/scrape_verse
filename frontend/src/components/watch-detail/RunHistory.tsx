"use client";

import React from "react";
import { CheckCircle2, XCircle, Loader2, Clock, Cpu, Calendar, Tag, ShieldAlert } from "lucide-react";
import { WatchRun } from "../../types";
import { formatCurrency, formatRelativeTime } from "../../lib/utils";

interface RunHistoryProps {
  runs: WatchRun[];
}

export function RunHistory({ runs }: RunHistoryProps) {
  const safeRuns = Array.isArray(runs) ? [...runs] : [];

  // Sort newest first by scheduled_for or created_at
  safeRuns.sort((a, b) => {
    const timeA = new Date(a.scheduled_for || a.started_at || a.created_at || 0).getTime();
    const timeB = new Date(b.scheduled_for || b.started_at || b.created_at || 0).getTime();
    return timeB - timeA;
  });

  if (safeRuns.length === 0) {
    return (
      <div className="p-6 rounded-2xl bg-space-950/40 border border-space-750 text-center">
        <p className="text-xs text-slate-400">
          No runs recorded yet. Click &quot;Run Now&quot; to execute the first live collection.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2.5">
      {safeRuns.map((run, idx) => {
        if (!run) return null;
        const isSucceeded = (run.status as string) === "succeeded" || (run.status as string) === "success";
        const isFailed = run.status === "failed";
        const isRunning = run.status === "running" || run.status === "pending";

        const endTime = run.finished_at || run.completed_at;
        const durationSeconds =
          run.started_at && endTime
            ? (
                Math.max(
                  0,
                  new Date(endTime).getTime() - new Date(run.started_at).getTime()
                ) / 1000
              ).toFixed(1)
            : null;

        const snapshotPrice = run.snapshot?.payload?.price;
        const snapshotCurrency = run.snapshot?.payload?.currency || "PKR";
        const hasSnapshotPrice = snapshotPrice !== undefined && snapshotPrice !== null;

        // Determine trigger label
        const isInitial = idx === safeRuns.length - 1 && safeRuns.length > 1;
        const triggerLabel = isInitial ? "Initial Baseline Scan" : "Scheduled Scan";

        return (
          <div
            key={run.id || idx}
            className="flex flex-col sm:flex-row sm:items-center justify-between p-3.5 rounded-2xl bg-space-900/80 border border-space-750/80 hover:border-space-600 transition-all text-xs gap-3"
          >
            {/* Left: Status Icon, Trigger Type, Status, Collection ID */}
            <div className="flex items-start sm:items-center gap-3">
              <div className="mt-0.5 sm:mt-0">
                {isSucceeded && (
                  <CheckCircle2 className="h-4 w-4 text-emerald-400 flex-shrink-0" />
                )}
                {isFailed && (
                  <XCircle className="h-4 w-4 text-rose-400 flex-shrink-0" />
                )}
                {isRunning && (
                  <Loader2 className="h-4 w-4 text-radar-cyan animate-spin flex-shrink-0" />
                )}
              </div>

              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-white">
                    {triggerLabel}
                  </span>

                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border ${
                      isSucceeded
                        ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                        : isFailed
                        ? "bg-rose-500/10 text-rose-300 border-rose-500/30"
                        : "bg-radar-cyan/10 text-radar-cyan border-radar-cyan/30"
                    }`}
                  >
                    {run.status}
                  </span>

                  {run.bright_data_collection_id && (
                    <span className="text-[10px] font-mono text-slate-400 bg-space-850 px-1.5 py-0.5 rounded border border-space-700">
                      {run.bright_data_collection_id}
                    </span>
                  )}
                </div>

                {/* Error details if failed */}
                {isFailed && (
                  <div className="flex items-center gap-1.5 text-[11px] text-rose-400 font-mono">
                    <ShieldAlert className="h-3 w-3 flex-shrink-0" />
                    <span>
                      {run.error_code || "execution_failed"}
                      {run.error_detail ? `: ${run.error_detail}` : ""}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Right: Extracted Price, Duration, Timestamp */}
            <div className="flex items-center gap-3 sm:gap-4 text-slate-400 font-mono text-[11px] self-end sm:self-center">
              {hasSnapshotPrice && (
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-space-950 border border-space-750 text-white font-bold">
                  <Tag className="h-3 w-3 text-radar-cyan" />
                  <span>{formatCurrency(snapshotPrice, snapshotCurrency)}</span>
                </div>
              )}

              {durationSeconds !== null && (
                <span className="hidden md:inline flex items-center gap-1">
                  <Cpu className="h-3 w-3 text-slate-500" />
                  {durationSeconds}s
                </span>
              )}

              <span className="flex items-center gap-1" title={run.scheduled_for || run.started_at || run.created_at}>
                <Clock className="h-3 w-3 text-slate-500" />
                {formatRelativeTime(run.scheduled_for || run.started_at || run.created_at)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
