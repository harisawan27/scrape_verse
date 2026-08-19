"use client";

import React from "react";
import Link from "next/link";
import {
  Sparkles,
  TrendingDown,
  TrendingUp,
  PackageCheck,
  Zap,
  ArrowRight,
  Clock,
  ExternalLink,
  BellRing,
} from "lucide-react";
import { AlertEvent } from "../../types";
import { formatCurrency, formatRelativeTime, getEventTypeLabel } from "../../lib/utils";

interface WhileYouWereAwayProps {
  events: AlertEvent[];
  loading?: boolean;
}

export function WhileYouWereAway({ events, loading }: WhileYouWereAwayProps) {
  if (loading) {
    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="h-5 w-44 bg-space-800 animate-pulse rounded-lg" />
          <div className="h-4 w-20 bg-space-800 animate-pulse rounded-lg" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-32 rounded-2xl bg-space-900/60 border border-space-750 animate-pulse p-4"
            />
          ))}
        </div>
      </div>
    );
  }

  if (!events || events.length === 0) {
    return null; // Don't take up space if no events yet, dashboard empty state will explain
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex items-center justify-center h-6 w-6 rounded-lg bg-radar-emerald/15 text-radar-emerald">
            <BellRing className="h-3.5 w-3.5" />
          </div>
          <h3 className="text-base font-bold text-white tracking-tight">
            While You Were Away
          </h3>
          <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-radar-emerald/15 text-radar-emerald border border-radar-emerald/30">
            {events.length} New Signal{events.length === 1 ? "" : "s"}
          </span>
        </div>

        <Link
          href="/activity"
          className="text-xs font-medium text-slate-400 hover:text-radar-cyan flex items-center gap-1 transition-colors"
        >
          <span>View All Activity</span>
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {events.slice(0, 3).map((event) => {
          const typeInfo = getEventTypeLabel(event.event_type);
          const prevPrice = event.details?.previous_value;
          const currPrice = event.details?.current_value;
          const hasPriceDiff = prevPrice !== undefined && currPrice !== undefined;
          const priceDropped = hasPriceDiff && currPrice < prevPrice;

          return (
            <Link
              key={event.id}
              href={`/watches/${event.watch_id}`}
              className="group relative rounded-2xl p-4 bg-gradient-to-br from-space-850 to-space-900 border border-space-700/80 hover:border-radar-cyan/50 transition-all duration-200 hover:shadow-glow flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2.5">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider border ${typeInfo.color}`}
                  >
                    {typeInfo.label}
                  </span>
                  <span className="text-[11px] text-slate-400 flex items-center gap-1 font-mono">
                    <Clock className="h-3 w-3 text-slate-500" />
                    {formatRelativeTime(event.created_at)}
                  </span>
                </div>

                <h4 className="text-sm font-semibold text-white group-hover:text-radar-cyan transition-colors line-clamp-1 mb-1">
                  {event.watch_title || "Monitored Product"}
                </h4>

                <p className="text-xs text-slate-400 line-clamp-2 mb-3 leading-relaxed">
                  {event.summary}
                </p>
              </div>

              {/* Price Delta Pill */}
              {hasPriceDiff && (
                <div className="mt-2 pt-2.5 border-t border-space-750 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5 font-mono">
                    <span className="text-slate-500 line-through text-[11px]">
                      {formatCurrency(prevPrice)}
                    </span>
                    <span className="text-slate-400">→</span>
                    <span className="font-bold text-white">
                      {formatCurrency(currPrice)}
                    </span>
                  </div>

                  {priceDropped && (
                    <span className="inline-flex items-center gap-1 text-[11px] font-bold text-radar-emerald bg-radar-emerald/10 px-1.5 py-0.5 rounded">
                      <TrendingDown className="h-3 w-3" />
                      <span>
                        -
                        {Math.round(
                          ((prevPrice - currPrice) / prevPrice) * 100
                        )}
                        %
                      </span>
                    </span>
                  )}
                </div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
