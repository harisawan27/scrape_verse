"use client";

import React from "react";
import { CheckCircle2, XCircle, Loader2, Clock, Cpu } from "lucide-react";
import { WatchRun } from "../../types";
import { formatRelativeTime } from "../../lib/utils";

interface RunHistoryProps {
  runs: WatchRun[];
}

export function RunHistory({ runs }: RunHistoryProps) {
  const safeRuns = Array.isArray(runs) ? runs : [];

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
    <div className="space-y-2">
      {safeRuns.map((run) => {
        if (!run) return null;
        const isSucceeded = run.status === "succeeded";
        const isFailed = run.status === "failed";
        const isRunning = run.status === "running" || run.status === "pending";

        const durationSeconds =
          run.started_at && run.completed_at
            ? (
                Math.max(
                  0,
                  new Date(run.completed_at).getTime() -
                    new Date(run.started_at).getTime()
                ) / 1000
              ).toFixed(1)
            : null;

        return (
          <div
            key={run.id}
            className="flex items-center justify-between p-3.5 rounded-xl bg-space-900/70 border border-space-750/70 hover:border-space-600 transition-colors text-xs"
          >
            <div className="flex items-center gap-3">
              {isSucceeded && (
                <CheckCircle2 className="h-4 w-4 text-emerald-400 flex-shrink-0" />
              )}
              {isFailed && (
                <XCircle className="h-4 w-4 text-rose-400 flex-shrink-0" />
              )}
              {isRunning && (
                <Loader2 className="h-4 w-4 text-radar-cyan animate-spin flex-shrink-0" />
              )}

              <div>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-white capitalize">
                    {run.status}
                  </span>
                  {run.bright_data_collection_id && (
                    <span className="text-[10px] font-mono text-slate-400 bg-space-850 px-1.5 py-0.5 rounded border border-space-700">
                      {run.bright_data_collection_id}
                    </span>
                  )}
                </div>
                {run.error_code && (
                  <p className="text-[11px] text-rose-400 font-mono mt-0.5">
                    Error: {run.error_code}
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center gap-4 text-slate-400 font-mono text-[11px]">
              {durationSeconds !== null && (
                <span className="hidden sm:inline flex items-center gap-1">
                  <Cpu className="h-3 w-3 text-slate-500" />
                  {durationSeconds}s
                </span>
              )}
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3 text-slate-500" />
                {formatRelativeTime(run.started_at || run.created_at)}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
