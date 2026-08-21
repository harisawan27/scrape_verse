"use client";

import React, { useState } from "react";
import {
  Globe,
  ExternalLink,
  Clock,
  Shield,
  Layers,
  Star,
  Zap,
  Settings,
  Pause,
  Play,
  Loader2,
  Cloud,
  CheckCircle2,
  Target,
} from "lucide-react";
import { WatchOverview } from "../../types";
import { HealthBadge } from "../common/HealthBadge";
import { formatCadence, formatCurrency, formatRelativeTime, formatRuleDescription } from "../../lib/utils";
import { api } from "../../lib/api";

interface WatchDetailHeroProps {
  overview: WatchOverview;
  onRefresh: () => void;
  onOpenControls: () => void;
}

export function WatchDetailHero({
  overview,
  onRefresh,
  onOpenControls,
}: WatchDetailHeroProps) {
  const { watch, health_status, latest_value, latest_snapshot, stats } = overview;
  const [running, setRunning] = useState(false);
  const [runMessage, setRunMessage] = useState<string | null>(null);
  const [togglingPause, setTogglingPause] = useState(false);

  const isPaused = watch.status === "paused";

  const handleManualRun = async () => {
    try {
      setRunning(true);
      setRunMessage(null);
      await api.triggerWatchRun(watch.id, true);
      setRunMessage("Collection Complete");
      onRefresh();
      setTimeout(() => setRunMessage(null), 3000);
    } catch (err) {
      console.error("Manual run failed:", err);
      setRunMessage("Run Failed");
      setTimeout(() => setRunMessage(null), 3000);
    } finally {
      setRunning(false);
    }
  };

  const handleTogglePause = async () => {
    try {
      setTogglingPause(true);
      const newStatus = isPaused ? "active" : "paused";
      await api.updateWatch(watch.id, { status: newStatus });
      onRefresh();
    } catch (err) {
      console.error("Toggle pause failed:", err);
    } finally {
      setTogglingPause(false);
    }
  };

  const isOutOfStock =
    latest_value?.availability &&
    latest_value.availability.toLowerCase().includes("out");

  const hasPrice = latest_value?.price !== null && latest_value?.price !== undefined;

  return (
    <div className="rounded-3xl p-6 md:p-8 bg-gradient-to-b from-space-850 to-space-900 border border-space-700/80 shadow-2xl space-y-6">
      {/* Top Bar: Title, Domain, Health, Action Buttons */}
      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
        <div className="space-y-2.5 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2">
            <HealthBadge status={health_status} size="md" />

            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-radar-cyan/10 border border-radar-cyan/25 text-radar-cyan text-xs font-mono">
              <Cloud className="h-3.5 w-3.5 text-radar-cyan" />
              <span>Bright Data Scraper Studio</span>
            </div>

            <span className="text-xs px-2.5 py-1 rounded-full bg-space-800 border border-space-700 font-mono text-slate-300">
              Cadence: {formatCadence(watch.schedule?.cadence || "custom", watch.monitoring_spec?.cadence_minutes || 30)}
            </span>
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight leading-snug">
            {watch.title}
          </h1>

          <div className="flex items-center gap-3 text-xs text-slate-400">
            <a
              href={watch.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-radar-cyan hover:underline font-mono truncate max-w-lg"
            >
              <Globe className="h-3.5 w-3.5 flex-shrink-0" />
              <span className="truncate">{watch.url}</span>
              <ExternalLink className="h-3 w-3 flex-shrink-0" />
            </a>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={handleManualRun}
            disabled={running || isPaused}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-gradient-to-r from-radar-cyan to-cyan-400 hover:from-cyan-400 hover:to-cyan-300 text-space-950 transition-all shadow-glow disabled:opacity-40"
          >
            {running ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Running Scan...</span>
              </>
            ) : (
              <>
                <Zap className="h-4 w-4" />
                <span>{runMessage || "Run Now"}</span>
              </>
            )}
          </button>

          <button
            onClick={handleTogglePause}
            disabled={togglingPause}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold border transition-colors ${
              isPaused
                ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/20"
                : "bg-space-800 text-slate-300 border-space-700 hover:bg-space-750"
            }`}
          >
            {togglingPause ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : isPaused ? (
              <>
                <Play className="h-3.5 w-3.5 text-emerald-400" />
                <span>Resume Monitoring</span>
              </>
            ) : (
              <>
                <Pause className="h-3.5 w-3.5 text-slate-400" />
                <span>Pause Watch</span>
              </>
            )}
          </button>

          <button
            onClick={onOpenControls}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold bg-space-800 hover:bg-space-750 text-slate-200 border border-space-700 transition-colors"
          >
            <Settings className="h-3.5 w-3.5 text-slate-400" />
            <span>Configure</span>
          </button>
        </div>
      </div>

      {/* Hero Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Latest Price Card */}
        <div className="p-4 rounded-2xl bg-space-950/80 border border-space-750/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
            Current Monitored Value
          </span>
          <div className="text-2xl font-black text-white font-mono">
            {hasPrice
              ? formatCurrency(latest_value!.price, latest_value!.currency || "PKR")
              : (
                <span className="text-sm font-medium text-radar-cyan animate-pulse">
                  First scan in progress...
                </span>
              )}
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block font-mono">
            {latest_value?.captured_at
              ? `Captured ${formatRelativeTime(latest_value.captured_at)}`
              : "Awaiting first run"}
          </span>
        </div>

        {/* Availability & Rating */}
        <div className="p-4 rounded-2xl bg-space-950/80 border border-space-750/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
            Stock & Seller
          </span>
          <div className="flex items-center gap-2">
            {latest_value?.availability ? (
              <span
                className={`text-xs font-bold px-2.5 py-1 rounded-md border ${
                  isOutOfStock
                    ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                    : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                }`}
              >
                {latest_value.availability.replace(/_/g, " ")}
              </span>
            ) : (
              <span className="text-xs text-slate-400 font-mono">In Stock</span>
            )}

            {latest_value?.rating && (
              <span className="flex items-center gap-1 text-amber-400 font-bold text-xs bg-amber-500/10 border border-amber-500/20 px-2 py-1 rounded-md">
                <Star className="h-3 w-3 fill-amber-400" />
                {latest_value.rating}
              </span>
            )}
          </div>
          <span className="text-[11px] text-slate-400 mt-1.5 block truncate">
            Merchant: {latest_snapshot?.payload?.seller || "Daraz Verified"}
          </span>
        </div>

        {/* Total Runs Executed */}
        <div className="p-4 rounded-2xl bg-space-950/80 border border-space-750/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
            Scraper Execution Health
          </span>
          <div className="text-2xl font-black text-white font-mono">
            {stats.successful_runs}{" "}
            <span className="text-xs font-normal text-slate-400">
              / {stats.total_runs} runs
            </span>
          </div>
          <span className="text-[11px] text-emerald-400 font-medium mt-1 block">
            {stats.failed_runs === 0
              ? "100% Extraction Health"
              : `${stats.failed_runs} extraction failure(s)`}
          </span>
        </div>

        {/* Semantic Events Count */}
        <div className="p-4 rounded-2xl bg-space-950/80 border border-space-750/80">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
            Surfaced Signals
          </span>
          <div className="text-2xl font-black text-radar-cyan font-mono">
            {stats.total_events}
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">
            Meaningful changes alerted
          </span>
        </div>
      </div>

      {/* Why Web Radar is Watching (Active Rules) */}
      <div className="p-4 rounded-2xl bg-space-950/60 border border-space-750 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-300">
            <Target className="h-4 w-4 text-radar-indigo" />
            <span>Why Web Radar is Watching This Page</span>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            Vertical: {watch.monitoring_spec?.vertical || "product"}
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          {(watch.monitoring_spec?.rules || []).length === 0 ? (
            <p className="text-xs text-slate-500 italic">No custom rules specified (monitoring all structured fields).</p>
          ) : (
            (watch.monitoring_spec?.rules || []).map((rule, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-space-850 border border-space-700 text-xs font-mono"
              >
                <span className="h-2 w-2 rounded-full bg-radar-emerald" />
                <span className="font-semibold text-white font-sans">
                  {formatRuleDescription(rule)}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
