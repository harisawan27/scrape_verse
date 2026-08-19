"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Radar, RefreshCw, Zap, Plus } from "lucide-react";
import { api } from "../../lib/api";

interface HeaderProps {
  title: string;
  subtitle?: string;
  onRefresh?: () => void;
}

export function Header({ title, subtitle, onRefresh }: HeaderProps) {
  const [triggering, setTriggering] = useState(false);
  const [triggerSuccess, setTriggerSuccess] = useState<string | null>(null);

  const handleTriggerTick = async () => {
    try {
      setTriggering(true);
      setTriggerSuccess(null);
      const runs = await api.triggerSchedulerTick();
      setTriggerSuccess(`Ran ${runs.length} due check${runs.length === 1 ? "" : "s"}`);
      if (onRefresh) onRefresh();
      setTimeout(() => setTriggerSuccess(null), 3000);
    } catch (err: any) {
      console.error("Scheduler trigger failed:", err);
    } finally {
      setTriggering(false);
    }
  };

  return (
    <header className="sticky top-0 z-20 bg-space-950/80 backdrop-blur-md border-b border-space-700/50 px-6 py-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <span>{title}</span>
          </h1>
          {subtitle && (
            <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Scheduler Trigger for Demo / Judging */}
          <button
            onClick={handleTriggerTick}
            disabled={triggering}
            title="Trigger background scheduler tick immediately"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-space-850 border border-space-700 hover:border-space-600 text-slate-300 hover:text-white transition-colors"
          >
            <Zap
              className={`h-3.5 w-3.5 text-amber-400 ${
                triggering ? "animate-spin" : ""
              }`}
            />
            <span>{triggering ? "Scanning..." : triggerSuccess || "Trigger Scan"}</span>
          </button>

          {onRefresh && (
            <button
              onClick={onRefresh}
              title="Refresh data"
              className="p-2 rounded-xl bg-space-850 border border-space-700 hover:border-space-600 text-slate-300 hover:text-white transition-colors"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          )}

          <Link
            href="/"
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-radar-cyan to-cyan-500 text-space-950 font-semibold text-xs hover:opacity-95 transition-opacity shadow-glow"
          >
            <Plus className="h-4 w-4" />
            <span>Create Watch</span>
          </Link>
        </div>
      </div>
    </header>
  );
}
