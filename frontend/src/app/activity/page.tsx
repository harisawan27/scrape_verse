"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Activity,
  BellRing,
  Clock,
  ExternalLink,
  Filter,
  TrendingDown,
  Sparkles,
  Radar,
} from "lucide-react";
import { Header } from "../../components/layout/Header";
import { EmptyState } from "../../components/common/EmptyState";
import { useUser } from "../../lib/userContext";
import { AlertEvent } from "../../types";
import { api } from "../../lib/api";
import {
  formatCurrency,
  formatHumanEventHeadline,
  formatRelativeTime,
  getEventTypeLabel,
} from "../../lib/utils";

export default function ActivityPage() {
  const router = useRouter();
  const { userId, isAuthenticated, loading: userLoading } = useUser();
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterType, setFilterType] = useState<string>("all");

  // Protect route
  useEffect(() => {
    if (!userLoading && !isAuthenticated) {
      router.replace("/sign-in");
    }
  }, [isAuthenticated, userLoading, router]);

  const loadActivity = useCallback(async (showLoading = true) => {
    if (!userId && !isAuthenticated) return;
    try {
      if (showLoading) setLoading(true);
      const res = await api.getActivity(userId || undefined, 100);
      setEvents(res);
    } catch (err) {
      console.error("Failed to load activity:", err);
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [userId, isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      loadActivity(true);
    }
  }, [isAuthenticated, loadActivity]);

  // Live polling (every 8 seconds when tab is active)
  useEffect(() => {
    if (!isAuthenticated) return;

    const interval = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        loadActivity(false);
      }
    }, 8000);

    return () => clearInterval(interval);
  }, [isAuthenticated, loadActivity]);

  const filteredEvents = events.filter((e) => {
    if (filterType === "all") return true;
    return e.event_type === filterType;
  });

  if (userLoading || (!isAuthenticated && userLoading)) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <Radar className="w-8 h-8 text-radar-cyan animate-spin" />
          <p className="text-xs text-slate-400 font-mono">Loading activity feed...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-full">
      <Header
        title="While You Were Away"
        subtitle="Semantic change alerts, threshold crossings, and inventory events"
        onRefresh={() => loadActivity(true)}
      />

      <div className="flex-1 p-6 md:p-8 space-y-6 max-w-5xl mx-auto w-full">
        {/* Filters */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl bg-space-900/80 border border-space-700/80">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
            <Filter className="h-4 w-4 text-radar-cyan" />
            <span>Filter By Event Type:</span>
          </div>

          <div className="flex items-center gap-1.5 overflow-x-auto">
            {[
              { id: "all", label: "All Events" },
              { id: "price_threshold_crossed", label: "Threshold Crossed" },
              { id: "price_decreased", label: "Price Decreased" },
              { id: "back_in_stock", label: "Back in Stock" },
              { id: "availability_changed", label: "Availability Changed" },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setFilterType(f.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-colors whitespace-nowrap ${
                  filterType === f.id
                    ? "bg-radar-cyan text-space-950 font-bold shadow-glow"
                    : "bg-space-850 hover:bg-space-800 text-slate-400 hover:text-slate-200 border border-space-700/60"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Activity Feed List */}
        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-28 rounded-2xl bg-space-900/60 border border-space-750 animate-pulse"
              />
            ))}
          </div>
        ) : filteredEvents.length === 0 ? (
          <EmptyState
            icon={Activity}
            title={
              filterType !== "all"
                ? "No Events Match Filter"
                : "No Activity Detected Yet"
            }
            description={
              filterType !== "all"
                ? "Try selecting 'All Events' to see alerts across other rule types."
                : "Web Radar runs server-side 24/7. When prices change, thresholds cross, or stock updates, meaningful alerts will automatically surface here."
            }
          />
        ) : (
          <div className="space-y-4">
            {filteredEvents.map((evt) => {
              const headline = formatHumanEventHeadline(evt);
              const isThreshold = evt.event_type === "price_threshold_crossed";
              const isDrop = evt.event_type === "price_decreased";
              const isStock = evt.event_type === "back_in_stock";

              return (
                <div
                  key={evt.id}
                  className={`p-5 rounded-2xl border transition-all ${
                    isThreshold
                      ? "bg-gradient-to-r from-emerald-950/20 via-space-900 to-space-900 border-emerald-500/30 hover:border-emerald-500/50"
                      : isDrop
                      ? "bg-gradient-to-r from-cyan-950/20 via-space-900 to-space-900 border-radar-cyan/30 hover:border-radar-cyan/50"
                      : isStock
                      ? "bg-gradient-to-r from-indigo-950/20 via-space-900 to-space-900 border-radar-indigo/30 hover:border-radar-indigo/50"
                      : "bg-space-900 border-space-700/80 hover:border-space-600"
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={`text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
                            isThreshold
                              ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/60"
                              : isDrop
                              ? "bg-cyan-950/60 text-cyan-300 border-cyan-800/60"
                              : isStock
                              ? "bg-indigo-950/60 text-indigo-300 border-indigo-800/60"
                              : "bg-space-800 text-slate-300 border-space-700"
                          }`}
                        >
                          {getEventTypeLabel(evt.event_type).label}
                        </span>


                        <span className="text-xs text-slate-500 flex items-center gap-1 font-mono">
                          <Clock className="h-3 w-3" />
                          {formatRelativeTime(evt.created_at)}
                        </span>
                      </div>

                      <h4 className="text-base font-bold text-white tracking-tight">
                        {headline}
                      </h4>

                      <p className="text-xs text-slate-400">
                        {evt.summary}
                      </p>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-start">
                      <Link
                        href={`/watches/${evt.watch_id}`}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-space-850 hover:bg-space-800 text-slate-200 border border-space-700 transition-colors"
                      >
                        <span>View Watch</span>
                        <ExternalLink className="h-3.5 w-3.5" />
                      </Link>
                    </div>
                  </div>

                  {/* Context Values */}
                  {evt.details && (
                    <div className="mt-3 pt-3 border-t border-space-800/80 flex items-center gap-4 text-xs text-slate-400 font-mono">
                      {evt.details.previous_value !== undefined && (
                        <span>
                          Previous:{" "}
                          <span className="text-slate-300 line-through">
                            {formatCurrency(evt.details.previous_value)}
                          </span>
                        </span>
                      )}
                      {evt.details.current_value !== undefined && (
                        <span>
                          Current:{" "}
                          <span className="text-emerald-400 font-bold">
                            {formatCurrency(evt.details.current_value)}
                          </span>
                        </span>
                      )}
                      {evt.details.threshold !== undefined && (
                        <span>
                          Target:{" "}
                          <span className="text-cyan-400 font-medium">
                            {formatCurrency(evt.details.threshold)}
                          </span>
                        </span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
