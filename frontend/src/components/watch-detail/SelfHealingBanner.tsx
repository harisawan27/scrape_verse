"use client";

import React from "react";
import { Wrench, ShieldAlert, CheckCircle, RefreshCw, Cpu } from "lucide-react";
import { ScraperRepair } from "../../types";
import { formatRelativeTime } from "../../lib/utils";

interface SelfHealingBannerProps {
  repair: ScraperRepair | null;
}

export function SelfHealingBanner({ repair }: SelfHealingBannerProps) {
  if (!repair) return null;

  const isResolved = repair.status === "resolved";
  const isInProgress = repair.status === "in_progress" || repair.status === "pending";
  const isFailed = repair.status === "failed";

  return (
    <div
      className={`rounded-2xl p-5 border transition-all ${
        isResolved
          ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-200"
          : isFailed
          ? "bg-rose-500/10 border-rose-500/30 text-rose-200"
          : "bg-amber-500/10 border-amber-500/30 text-amber-200 shadow-glow-amber"
      }`}
    >
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div
            className={`p-2.5 rounded-xl border flex-shrink-0 ${
              isResolved
                ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-400"
                : isFailed
                ? "bg-rose-500/20 border-rose-500/40 text-rose-400"
                : "bg-amber-500/20 border-amber-500/40 text-amber-400 animate-pulse"
            }`}
          >
            {isResolved ? (
              <CheckCircle className="h-5 w-5" />
            ) : isFailed ? (
              <ShieldAlert className="h-5 w-5" />
            ) : (
              <Wrench className="h-5 w-5" />
            )}
          </div>

          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider font-mono">
                Bright Data Self-Healing Scraper Studio
              </span>
              <span
                className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${
                  isResolved
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                    : isFailed
                    ? "bg-rose-500/20 text-rose-300 border-rose-500/40"
                    : "bg-amber-500/20 text-amber-300 border-amber-500/40"
                }`}
              >
                {repair.status.replace(/_/g, " ")}
              </span>
            </div>

            <h4 className="text-sm font-bold text-white">
              {isResolved
                ? "Scraper Layout Drift Automatically Healed"
                : isFailed
                ? "Scraper Layout Drift Repair Unresolved"
                : "Scraper Schema Drift Detected — Autonomous Repair in Progress"}
            </h4>

            <p className="text-xs text-slate-300 leading-relaxed max-w-2xl">
              {repair.repair_prompt}
            </p>
          </div>
        </div>

        {/* Repair Metadata */}
        <div className="flex md:flex-col items-end justify-between md:justify-center gap-1.5 text-xs text-slate-400 font-mono border-t md:border-t-0 md:border-l border-space-700/50 pt-2 md:pt-0 md:pl-4">
          <div className="flex items-center gap-1.5">
            <Cpu className="h-3.5 w-3.5 text-radar-cyan" />
            <span>{repair.collector_id}</span>
          </div>
          <div>Attempts: {repair.attempt_count}</div>
          <div className="text-[11px] text-slate-400">
            {isResolved
              ? `Healed ${formatRelativeTime(repair.resolved_at)}`
              : `Started ${formatRelativeTime(repair.created_at)}`}
          </div>
        </div>
      </div>
    </div>
  );
}
