"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Globe,
  Clock,
  Zap,
  ArrowUpRight,
  Sparkles,
  Package,
  Star,
  Loader2,
  ExternalLink,
  Target,
  Cloud,
} from "lucide-react";
import { WatchSummary } from "../../types";
import { HealthBadge } from "../common/HealthBadge";
import { formatCadence, formatCurrency, formatRelativeTime } from "../../lib/utils";
import { api } from "../../lib/api";

interface WatchCardProps {
  watch: WatchSummary;
  onRefresh?: () => void;
}

export function WatchCard({ watch, onRefresh }: WatchCardProps) {
  const [running, setRunning] = useState(false);
  const [runMessage, setRunMessage] = useState<string | null>(null);

  const handleManualRun = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    try {
      setRunning(true);
      setRunMessage(null);
      await api.triggerWatchRun(watch.id, true);
      setRunMessage("Collection Done");
      if (onRefresh) onRefresh();
      setTimeout(() => setRunMessage(null), 3000);
    } catch (err: any) {
      console.error("Manual run failed:", err);
      setRunMessage("Run Failed");
      setTimeout(() => setRunMessage(null), 3000);
    } finally {
      setRunning(false);
    }
  };

  const isOutOfStock =
    watch.latest_value?.availability &&
    watch.latest_value.availability.toLowerCase().includes("out");

  const hasPrice = watch.latest_value?.price !== null && watch.latest_value?.price !== undefined;

  return (
    <Link
      href={`/watches/${watch.id}`}
      className="group relative rounded-3xl p-5 bg-gradient-to-b from-space-850 to-space-900 border border-space-700/80 hover:border-radar-cyan/60 transition-all duration-200 hover:shadow-glow flex flex-col justify-between"
    >
      <div className="space-y-3">
        {/* Top Badges: Domain + Health */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-space-800 border border-space-700 text-slate-300 text-xs font-mono">
            <Globe className="h-3 w-3 text-radar-cyan" />
            <span className="truncate max-w-[130px]">{watch.domain}</span>
          </div>

          <HealthBadge status={watch.health_status} size="sm" />
        </div>

        {/* Watch Title */}
        <h3 className="text-base font-bold text-white group-hover:text-radar-cyan transition-colors line-clamp-2 leading-snug">
          {watch.title}
        </h3>

        {/* Price & Stock Display */}
        <div className="p-3.5 rounded-2xl bg-space-950/80 border border-space-750/80">
          <div className="flex items-baseline justify-between gap-2">
            <div>
              <div className="flex items-center gap-1.5 mb-0.5">
                <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
                  Current Monitored Value
                </span>
                {watch.latest_value?.original_price && watch.latest_value.price && watch.latest_value.original_price > watch.latest_value.price && (
                  <span className="text-[9px] font-bold px-1 py-0.2 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-mono">
                    {Math.round(((watch.latest_value.original_price - watch.latest_value.price) / watch.latest_value.original_price) * 100)}% off
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-2 flex-wrap">
                <span className="text-xl font-black text-white tracking-tight font-mono">
                  {hasPrice
                    ? formatCurrency(
                        watch.latest_value!.price,
                        watch.latest_value!.currency || "PKR"
                      )
                    : (
                      <span className="text-sm font-medium text-radar-cyan animate-pulse">
                        First scan in progress...
                      </span>
                    )}
                </span>
                {watch.latest_value?.original_price && watch.latest_value.price && watch.latest_value.original_price > watch.latest_value.price && (
                  <span className="text-[11px] text-slate-500 line-through font-mono">
                    {formatCurrency(watch.latest_value.original_price, watch.latest_value.currency || "PKR")}
                  </span>
                )}
              </div>
            </div>

            {watch.latest_value?.availability && (
              <span
                className={`text-[11px] font-bold px-2 py-0.5 rounded-md border ${
                  isOutOfStock
                    ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                    : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                }`}
              >
                {watch.latest_value.availability.replace(/_/g, " ")}
              </span>
            )}
          </div>

          {/* Rating & Reviews */}
          {watch.latest_value?.rating && (
            <div className="flex items-center gap-2 mt-2 pt-2 border-t border-space-800 text-xs text-slate-400">
              <span className="flex items-center gap-1 text-amber-400 font-medium">
                <Star className="h-3 w-3 fill-amber-400" />
                {watch.latest_value.rating}
              </span>
              {watch.latest_value.reviews_count !== null && (
                <span>({watch.latest_value.reviews_count} reviews)</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Footer Info & Quick Actions */}
      <div className="space-y-3 pt-3">
        <div className="flex items-center justify-between text-xs text-slate-400 border-t border-space-750 pt-2.5">
          <div className="flex items-center gap-1.5 font-mono text-slate-300">
            <Clock className="h-3.5 w-3.5 text-slate-500" />
            <span>{formatCadence(watch.status === "paused" ? "paused" : "custom", watch.cadence_minutes)}</span>
          </div>

          <span className="text-[11px] text-slate-400 font-mono">
            {watch.latest_successful_run_at
              ? `Checked ${formatRelativeTime(watch.latest_successful_run_at)}`
              : "Pending baseline"}
          </span>
        </div>

        {/* Quick Action Button */}
        <div className="flex items-center justify-between gap-2 pt-1">
          <button
            onClick={handleManualRun}
            disabled={running || watch.status === "paused"}
            title="Execute immediate live collection against this Watch"
            className="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-xl text-xs font-semibold bg-space-800 hover:bg-space-750 border border-space-700 text-slate-200 hover:text-white transition-colors disabled:opacity-40"
          >
            {running ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin text-radar-cyan" />
                <span>Running Scan...</span>
              </>
            ) : (
              <>
                <Zap className="h-3.5 w-3.5 text-amber-400" />
                <span>{runMessage || "Run Now"}</span>
              </>
            )}
          </button>

          <span className="p-2 rounded-xl bg-space-800 text-slate-400 group-hover:text-white group-hover:bg-radar-cyan/20 transition-colors">
            <ArrowUpRight className="h-4 w-4" />
          </span>
        </div>
      </div>
    </Link>
  );
}
