"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Loader2,
  AlertTriangle,
  History,
  Activity,
  Layers,
  Database,
  Cpu,
} from "lucide-react";
import { Header } from "../../../components/layout/Header";
import { WatchDetailHero } from "../../../components/watch-detail/WatchDetailHero";
import { SelfHealingBanner } from "../../../components/watch-detail/SelfHealingBanner";
import { SemanticTimeline } from "../../../components/watch-detail/SemanticTimeline";
import { RunHistory } from "../../../components/watch-detail/RunHistory";
import { WatchControlsModal } from "../../../components/watch-detail/WatchControlsModal";
import { WatchOverview, AlertEvent, WatchRun } from "../../../types";
import { api } from "../../../lib/api";

export default function WatchDetailPage() {
  const params = useParams();
  const router = useRouter();
  const watchId = params.id as string;

  const [overview, setOverview] = useState<WatchOverview | null>(null);
  const [runs, setRuns] = useState<WatchRun[]>([]);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [controlsOpen, setControlsOpen] = useState<boolean>(false);

  const loadWatchOverview = async () => {
    if (!watchId) return;
    try {
      setLoading(true);
      setError(null);
      const res = await api.getWatchOverview(watchId);
      setOverview(res);

      // Also gather full runs if needed
      if (res.latest_run) {
        setRuns([res.latest_run]);
      }
      if (res.latest_event) {
        setAlerts([res.latest_event]);
      }
    } catch (err: any) {
      console.error("Failed to load watch overview:", err);
      setError(err?.message || "Failed to load watch details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWatchOverview();
  }, [watchId]);

  if (loading) {
    return (
      <div className="flex-1 flex flex-col min-h-full">
        <Header title="Watch Overview" />
        <div className="flex-1 flex items-center justify-center p-12">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 text-radar-cyan animate-spin" />
            <p className="text-xs text-slate-400 font-mono">
              Loading Watch Telemetry...
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !overview) {
    return (
      <div className="flex-1 flex flex-col min-h-full">
        <Header title="Watch Not Found" />
        <div className="flex-1 flex items-center justify-center p-12">
          <div className="p-8 rounded-3xl bg-space-900 border border-space-700 text-center max-w-md">
            <AlertTriangle className="h-10 w-10 text-rose-400 mx-auto mb-3" />
            <h3 className="text-lg font-bold text-white mb-2">
              Unable to Load Watch
            </h3>
            <p className="text-xs text-slate-400 mb-6">
              {error || "The requested Watch does not exist or has been deleted."}
            </p>
            <Link
              href="/watches"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold bg-space-800 hover:bg-space-750 text-white border border-space-700 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Back to Watches</span>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-full">
      <Header
        title={overview.watch.title}
        subtitle={`Domain: ${overview.watch.url.replace(/^https?:\/\//, "").split("/")[0]}`}
        onRefresh={loadWatchOverview}
      />

      <div className="flex-1 p-6 md:p-8 space-y-8 max-w-7xl mx-auto w-full">
        {/* Back Link */}
        <div>
          <Link
            href="/watches"
            className="inline-flex items-center gap-2 text-xs font-medium text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to All Watches</span>
          </Link>
        </div>

        {/* 1. Hero State & Primary Metrics */}
        <WatchDetailHero
          overview={overview}
          onRefresh={loadWatchOverview}
          onOpenControls={() => setControlsOpen(true)}
        />

        {/* 2. Self-Healing Scraper Drift Banner (Prominent) */}
        {overview.active_repair && (
          <SelfHealingBanner repair={overview.active_repair} />
        )}

        {/* 3. Detail Columns: Semantic Events Timeline & Execution History */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left 2 Cols: Semantic Changes Timeline */}
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center justify-between border-b border-space-700/60 pb-3">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-radar-cyan" />
                <h3 className="text-base font-bold text-white">
                  Semantic Change Log
                </h3>
              </div>
              <span className="text-xs text-slate-400 font-mono">
                {overview.stats.total_events} Event{overview.stats.total_events === 1 ? "" : "s"}
              </span>
            </div>

            <SemanticTimeline
              events={overview.latest_event ? [overview.latest_event] : []}
            />
          </div>

          {/* Right Col: Run History & Collector Telemetry */}
          <div className="space-y-6">
            {/* Run Execution History */}
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b border-space-700/60 pb-3">
                <div className="flex items-center gap-2">
                  <History className="h-4 w-4 text-radar-emerald" />
                  <h3 className="text-base font-bold text-white">
                    Run History
                  </h3>
                </div>
                <span className="text-xs text-slate-400 font-mono">
                  {overview.stats.total_runs} Runs
                </span>
              </div>

              <RunHistory
                runs={overview.latest_run ? [overview.latest_run] : []}
              />
            </div>

            {/* Collector & Technical Boundaries Card */}
            <div className="p-4 rounded-2xl bg-space-900/60 border border-space-750 space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-300">
                <Cpu className="h-4 w-4 text-radar-indigo" />
                <span>Integration Boundary</span>
              </div>

              <div className="space-y-2 text-xs font-mono">
                <div className="flex items-center justify-between p-2 rounded-lg bg-space-950/60 border border-space-800">
                  <span className="text-slate-400">Scraper Studio ID:</span>
                  <span className="text-radar-cyan truncate max-w-[160px]">
                    {overview.watch.monitoring_spec?.collector_id || "c_msz0zrtw29tjzhzakl"}
                  </span>
                </div>
                <div className="flex items-center justify-between p-2 rounded-lg bg-space-950/60 border border-space-800">
                  <span className="text-slate-400">Database Engine:</span>
                  <span className="text-emerald-400">Neon PostgreSQL</span>
                </div>
                <div className="flex items-center justify-between p-2 rounded-lg bg-space-950/60 border border-space-800">
                  <span className="text-slate-400">Authoritative Source:</span>
                  <span className="text-white">Server-Side Worker</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Watch Controls Modal */}
      <WatchControlsModal
        overview={overview}
        isOpen={controlsOpen}
        onClose={() => setControlsOpen(false)}
        onUpdated={loadWatchOverview}
        onDeleted={() => {
          router.push("/watches");
        }}
      />
    </div>
  );
}
