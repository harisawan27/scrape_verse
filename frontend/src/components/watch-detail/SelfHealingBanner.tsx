"use client";

import React, { useState } from "react";
import {
  Wrench,
  ShieldAlert,
  CheckCircle,
  RefreshCw,
  Cpu,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  Zap,
  Layers,
} from "lucide-react";
import { ScraperRepair } from "../../types";
import { formatRelativeTime } from "../../lib/utils";

interface SelfHealingBannerProps {
  repair: ScraperRepair | null;
  collectorId?: string;
}

const REPAIR_LIFECYCLE_STAGES = [
  { id: "drift_detected", label: "1. Drift Detected", desc: "HTML schema changed" },
  { id: "extraction_failed", label: "2. Schema Failure Identified", desc: "Missing required fields" },
  { id: "healing_requested", label: "3. Self-Healing Requested", desc: "Prompt sent to Bright Data" },
  { id: "repair_generated", label: "4. Repair Generated", desc: "Selector code regenerated" },
  { id: "recovered", label: "5. Production Recovery", desc: "Tested & restored" },
];

export function SelfHealingBanner({ repair, collectorId = "c_msz0zrtw29tjzhzakl" }: SelfHealingBannerProps) {
  const [explainerOpen, setExplainerOpen] = useState(false);

  // If no repair is active, show the healthy autonomous protection explainer
  if (!repair) {
    return (
      <div className="rounded-2xl p-5 bg-gradient-to-r from-space-900 via-space-850 to-space-900 border border-space-750/80 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 font-mono">
                  Bright Data Scraper Studio Active
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                  Healthy Scraper
                </span>
              </div>
              <h4 className="text-sm font-bold text-white mt-0.5">
                Autonomous Extraction & Self-Healing Enabled
              </h4>
            </div>
          </div>

          <button
            onClick={() => setExplainerOpen(!explainerOpen)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-space-800 hover:bg-space-750 text-slate-300 hover:text-white border border-space-700 transition-colors"
          >
            <span>{explainerOpen ? "Hide Self-Healing Flow" : "How Self-Healing Works"}</span>
            {explainerOpen ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </button>
        </div>

        {explainerOpen && (
          <div className="pt-3 border-t border-space-750/60 animate-fadeIn space-y-4">
            <p className="text-xs text-slate-300 leading-relaxed max-w-3xl">
              When target websites change their layout, traditional scrapers break silently. Web Radar detects extraction schema failures in real time and automatically triggers <strong>Bright Data Self-Healing</strong> to repair the scraper code without losing monitoring history.
            </p>

            {/* 5-Stage Lifecycle Diagram */}
            <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
              {REPAIR_LIFECYCLE_STAGES.map((st, i) => (
                <div
                  key={i}
                  className="p-3 rounded-xl bg-space-950/70 border border-space-750/70 text-xs"
                >
                  <div className="font-bold text-radar-cyan mb-1">{st.label}</div>
                  <div className="text-[11px] text-slate-400 leading-snug">{st.desc}</div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 bg-space-950/50 p-2.5 rounded-xl border border-space-800">
              <span>Collector ID: <strong className="text-radar-cyan">{collectorId}</strong></span>
              <span>Self-Healing Engine: <strong className="text-emerald-400">Bright Data Scraper Studio</strong></span>
            </div>
          </div>
        )}
      </div>
    );
  }

  const isResolved = repair.status === "resolved";
  const isInProgress = repair.status === "in_progress" || repair.status === "pending";
  const isFailed = repair.status === "failed";

  return (
    <div
      className={`rounded-3xl p-6 border transition-all ${
        isResolved
          ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-200"
          : isFailed
          ? "bg-rose-500/10 border-rose-500/30 text-rose-200"
          : "bg-gradient-to-r from-amber-500/15 via-space-900 to-space-850 border-amber-500/40 text-amber-200 shadow-glow-amber"
      }`}
    >
      <div className="space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div
              className={`p-3 rounded-2xl border flex-shrink-0 ${
                isResolved
                  ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-400"
                  : isFailed
                  ? "bg-rose-500/20 border-rose-500/40 text-rose-400"
                  : "bg-amber-500/20 border-amber-500/40 text-amber-400 animate-pulse"
              }`}
            >
              {isResolved ? (
                <CheckCircle className="h-6 w-6" />
              ) : isFailed ? (
                <ShieldAlert className="h-6 w-6" />
              ) : (
                <Wrench className="h-6 w-6" />
              )}
            </div>

            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider font-mono text-amber-400">
                  Bright Data Scraper Studio Self-Healing
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

              <h4 className="text-base font-extrabold text-white">
                {isResolved
                  ? "Scraper Layout Drift Automatically Healed & Restored"
                  : isFailed
                  ? "Scraper Layout Drift Repair Unresolved"
                  : "Scraper Layout Drift Detected — Autonomous Repair in Progress"}
              </h4>

              <p className="text-xs text-slate-300 leading-relaxed max-w-2xl">
                {repair.repair_prompt}
              </p>
            </div>
          </div>

          {/* Repair Telemetry Metadata */}
          <div className="flex md:flex-col items-end justify-between md:justify-center gap-1.5 text-xs text-slate-400 font-mono border-t md:border-t-0 md:border-l border-space-700/50 pt-3 md:pt-0 md:pl-4">
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

        {/* 5-Stage Visual Progress Stepper */}
        <div className="p-3.5 rounded-2xl bg-space-950/80 border border-space-750">
          <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-5 gap-2 text-xs">
            {REPAIR_LIFECYCLE_STAGES.map((st, i) => {
              const active =
                (i === 0) ||
                (i === 1) ||
                (i === 2 && isInProgress) ||
                (i === 3 && isInProgress) ||
                (i === 4 && isResolved);

              return (
                <div
                  key={i}
                  className={`p-2.5 rounded-xl border transition-all ${
                    isResolved
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                      : active
                      ? "bg-amber-500/15 border-amber-500/40 text-amber-300 font-bold"
                      : "bg-space-900 border-space-800 text-slate-500"
                  }`}
                >
                  <div className="text-[11px] font-bold">{st.label}</div>
                  <div className="text-[10px] text-slate-400 mt-0.5">{st.desc}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
