"use client";

import React from "react";
import {
  Bell,
  TrendingDown,
  TrendingUp,
  PackageCheck,
  Clock,
  Sparkles,
  AlertTriangle,
} from "lucide-react";
import { AlertEvent } from "../../types";
import {
  formatCurrency,
  formatHumanEventHeadline,
  formatRelativeTime,
  getEventTypeLabel,
} from "../../lib/utils";



interface SemanticTimelineProps {
  events: AlertEvent[];
}

export function SemanticTimeline({ events }: SemanticTimelineProps) {
  if (!events || events.length === 0) {
    return (
      <div className="p-8 rounded-2xl bg-space-950/40 border border-space-750 text-center">
        <Sparkles className="h-8 w-8 text-slate-600 mx-auto mb-2" />
        <h4 className="text-sm font-semibold text-white mb-1">
          No Semantic Changes Yet
        </h4>
        <p className="text-xs text-slate-400 max-w-sm mx-auto">
          Web Radar evaluates each collection snapshot against your rules. When a price threshold is crossed or stock status changes, it will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-space-750">
      {events.map((event, idx) => {
        const typeInfo = getEventTypeLabel(event.event_type);
        const prevPrice = event.details?.previous_value;
        const currPrice = event.details?.current_value;
        const hasPriceDiff = prevPrice !== undefined && currPrice !== undefined;
        const isDrop = hasPriceDiff && currPrice < prevPrice;

        return (
          <div key={event.id || idx} className="relative group">
            {/* Timeline Indicator Dot */}
            <span
              className={`absolute -left-[27px] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-space-950 ${
                isDrop
                  ? "bg-radar-emerald shadow-[0_0_8px_#10b981]"
                  : "bg-radar-cyan shadow-[0_0_8px_#06b6d4]"
              }`}
            />

            {/* Event Card */}
            <div className="rounded-2xl p-4 bg-space-900/90 border border-space-750 group-hover:border-space-600 transition-colors shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider border ${typeInfo.color}`}
                >
                  {typeInfo.label}
                </span>

                <span className="text-xs text-slate-400 flex items-center gap-1 font-mono">
                  <Clock className="h-3 w-3 text-slate-500" />
                  {formatRelativeTime(event.created_at)}
                </span>
              </div>

              <h4 className="text-sm font-semibold text-white mb-1 leading-relaxed">
                {formatHumanEventHeadline(event)}
              </h4>
              {event.summary && event.summary !== formatHumanEventHeadline(event) && (
                <p className="text-xs text-slate-400 mb-2 leading-relaxed">
                  {event.summary}
                </p>
              )}


              {/* Price Change Diff Pill */}
              {hasPriceDiff && (
                <div className="mt-2.5 pt-2.5 border-t border-space-800 flex items-center justify-between text-xs font-mono">
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
  );
}
