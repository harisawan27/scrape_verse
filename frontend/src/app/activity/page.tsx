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
      setEvents(Array.isArray(res) ? res : []);
    } catch (err) {
      console.error("Failed to load activity:", err);
      setEvents([]);
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

  const safeEvents = Array.isArray(events) ? events : [];

  const filteredEvents = safeEvents.filter((e) => {
    if (!e) return false;
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
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-radar-cyan" />
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Filter by Event Type
            </span>
          </div>

          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
            {[
              { id: "all", label: "All Events" },
              { id: "semantic_change", label: "Semantic Change" },
              { id: "condition_alert", label: "Condition Alerts" },
              { id: "healed", label: "Self-Healed" },
              { id: "system", label: "System Events" },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => setFilterType(f.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-colors ${
                  filterType === f.id
                    ? "bg-radar-cyan text-space-950 font-bold"
                    : "bg-space-850 hover:bg-space-800 text-slate-400 hover:text-slate-200 border border-space-700/60"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Activity Feed */}
        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-28 rounded-2xl bg-space-900/60 border border-space-750 animate-pulse p-4"
              />
            ))}
          </div>
        ) : filteredEvents.length === 0 ? (
          safeEvents.length === 0 ? (
            <EmptyState
              icon={Activity}
              title="No Semantic Alerts Yet"
              description="Web Radar monitors your configured URLs in the background and will create a semantic intelligence card whenever prices drop or critical fields change."
              actionText="Go to Command Center"
              onAction={() => router.push("/")}
            />
          ) : (
            <div className="p-12 rounded-2xl bg-space-900/40 border border-space-750 text-center">
              <p className="text-sm text-slate-400">
                No events matching &quot;{filterType}&quot;
              </p>
            </div>
          )
        ) : (
          <div className="space-y-3">
            {filteredEvents.map((evt) => {
              const typeInfo = getEventTypeLabel(evt.event_type);
              const prevPrice = evt.details?.previous_value;
              const currPrice = evt.details?.current_value;
              const hasPriceDiff = prevPrice !== undefined && currPrice !== undefined;
              const priceDropped = hasPriceDiff && currPrice < prevPrice;
              const headline = formatHumanEventHeadline(evt);

              return (
                <Link
                  key={evt.id}
                  href={`/watches/${evt.watch_id}`}
                  className="block group rounded-2xl p-5 bg-gradient-to-br from-space-900 via-space-850 to-space-900 border border-space-750 hover:border-radar-cyan/50 transition-all duration-200 hover:shadow-glow"
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${typeInfo.color}`}
                        >
                          {typeInfo.label}
                        </span>

                        <span className="text-xs text-slate-400 font-mono">
                          {evt.watch_title || "Watch Alert"}
                        </span>
                      </div>

                      <h4 className="text-sm font-bold text-white group-hover:text-radar-cyan transition-colors">
                        {headline}
                      </h4>

                      <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                        {evt.summary}
                      </p>
                    </div>

                    <div className="flex items-center md:flex-col items-end justify-between md:justify-center gap-2 flex-shrink-0">
                      {hasPriceDiff && (
                        <div className="text-right">
                          <div className="flex items-center gap-1.5">
                            {priceDropped && (
                              <TrendingDown className="h-4 w-4 text-emerald-400" />
                            )}
                            <span className="text-sm font-bold text-white">
                              {formatCurrency(currPrice)}
                            </span>
                          </div>
                          <span className="text-[11px] text-slate-400 line-through">
                            {formatCurrency(prevPrice)}
                          </span>
                        </div>
                      )}

                      <div className="flex items-center gap-1 text-[11px] text-slate-400 font-mono">
                        <Clock className="h-3 w-3 text-slate-500" />
                        <span>{formatRelativeTime(evt.created_at)}</span>
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
