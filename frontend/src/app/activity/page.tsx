"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  BellRing,
  Clock,
  ExternalLink,
  Filter,
  TrendingDown,
  Sparkles,
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
  const { userId, loading: userLoading } = useUser();
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterType, setFilterType] = useState<string>("all");

  const loadActivity = async () => {
    if (!userId) return;
    try {
      setLoading(true);
      const res = await api.getActivity(userId, 100);
      setEvents(res);
    } catch (err) {
      console.error("Failed to load activity:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (userId) {
      loadActivity();
    }
  }, [userId]);

  const filteredEvents = events.filter((e) => {
    if (filterType === "all") return true;
    return e.event_type === filterType;
  });

  return (
    <div className="flex-1 flex flex-col min-h-full">
      <Header
        title="While You Were Away"
        subtitle="Semantic change alerts, threshold crossings, and inventory events"
        onRefresh={loadActivity}
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
        {loading || userLoading ? (
          <div className="space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-28 rounded-2xl bg-space-900/60 border border-space-750 animate-pulse p-4"
              />
            ))}
          </div>
        ) : filteredEvents.length === 0 ? (
          <EmptyState
            icon={BellRing}
            title={
              filterType !== "all"
                ? "No Matching Events"
                : "No Semantic Changes Yet"
            }
            description={
              filterType !== "all"
                ? "No events match the selected event type filter."
                : "When your Radar Watches detect price threshold crossings, price drops, or stock availability changes on Daraz, they will appear in this feed."
            }
            actionText="Go to Command Center"
            onAction={() => {
              window.location.href = "/";
            }}
          />
        ) : (
          <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-space-750">
            {filteredEvents.map((event) => {
              const typeInfo = getEventTypeLabel(event.event_type);
              const prevPrice = event.details?.previous_value;
              const currPrice = event.details?.current_value;
              const hasPriceDiff = prevPrice !== undefined && currPrice !== undefined;
              const isDrop = hasPriceDiff && currPrice < prevPrice;

              return (
                <div key={event.id} className="relative group">
                  {/* Timeline Bullet */}
                  <span
                    className={`absolute -left-[27px] top-4 h-3.5 w-3.5 rounded-full border-2 border-space-950 ${
                      isDrop
                        ? "bg-radar-emerald shadow-[0_0_8px_#10b981]"
                        : "bg-radar-cyan shadow-[0_0_8px_#06b6d4]"
                    }`}
                  />

                  {/* Card */}
                  <div className="rounded-2xl p-5 bg-gradient-to-r from-space-900 to-space-850 border border-space-750 hover:border-space-600 transition-all duration-200">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider border ${typeInfo.color}`}
                        >
                          {typeInfo.label}
                        </span>

                        <Link
                          href={`/watches/${event.watch_id}`}
                          className="text-xs font-semibold text-white hover:text-radar-cyan flex items-center gap-1 transition-colors"
                        >
                          <span>{event.watch_title || "Monitored Watch"}</span>
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      </div>

                      <span className="text-xs text-slate-400 flex items-center gap-1 font-mono">
                        <Clock className="h-3 w-3 text-slate-500" />
                        {formatRelativeTime(event.created_at)}
                      </span>
                    </div>

                    <p className="text-sm font-semibold text-white mb-1.5 leading-relaxed">
                      {formatHumanEventHeadline(event)}
                    </p>
                    {event.summary && event.summary !== formatHumanEventHeadline(event) && (
                      <p className="text-xs text-slate-400 mb-3 leading-relaxed">
                        {event.summary}
                      </p>
                    )}


                    {/* Price Diff Pill */}
                    {hasPriceDiff && (
                      <div className="pt-3 border-t border-space-800 flex items-center justify-between text-xs font-mono">
                        <div className="flex items-center gap-2">
                          <span className="text-slate-500 line-through">
                            {formatCurrency(prevPrice)}
                          </span>
                          <span className="text-slate-400">→</span>
                          <span className="text-base font-bold text-white">
                            {formatCurrency(currPrice)}
                          </span>
                        </div>

                        {isDrop && (
                          <span className="inline-flex items-center gap-1 text-xs font-bold text-radar-emerald bg-radar-emerald/10 px-2 py-0.5 rounded-md border border-radar-emerald/20">
                            <TrendingDown className="h-3.5 w-3.5" />
                            <span>
                              -
                              {Math.round(
                                ((prevPrice - currPrice) / prevPrice) * 100
                              )}
                              % Drop
                            </span>
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
