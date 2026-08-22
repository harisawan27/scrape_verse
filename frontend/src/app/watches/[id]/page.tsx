"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
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
  Radar,
} from "lucide-react";
import { Header } from "../../../components/layout/Header";
import { WatchDetailHero } from "../../../components/watch-detail/WatchDetailHero";
import { SelfHealingBanner } from "../../../components/watch-detail/SelfHealingBanner";
import { SemanticTimeline } from "../../../components/watch-detail/SemanticTimeline";
import { RunHistory } from "../../../components/watch-detail/RunHistory";
import { WatchControlsModal } from "../../../components/watch-detail/WatchControlsModal";
import { WatchOverview, AlertEvent, WatchRun } from "../../../types";
import { api } from "../../../lib/api";
import { useUser } from "../../../lib/userContext";

export default function WatchDetailPage() {
  const params = useParams();
  const router = useRouter();
  const watchId = params.id as string;
  const { isAuthenticated, loading: userLoading } = useUser();

  const [overview, setOverview] = useState<WatchOverview | null>(null);
  const [runs, setRuns] = useState<WatchRun[]>([]);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [controlsOpen, setControlsOpen] = useState<boolean>(false);

  // Protect route
  useEffect(() => {
    if (!userLoading && !isAuthenticated) {
      router.replace("/sign-in");
    }
  }, [isAuthenticated, userLoading, router]);

  const loadWatchOverview = useCallback(async (showLoading = true) => {
    if (!watchId || !isAuthenticated) return;
    try {
      if (showLoading) setLoading(true);
      setError(null);
      const res = await api.getWatchOverview(watchId);
      setOverview(res);

      if (res.runs && res.runs.length > 0) {
        setRuns(res.runs);
      } else if (res.latest_run) {
        setRuns([res.latest_run]);
      } else {
        setRuns([]);
      }

      if (res.alerts && res.alerts.length > 0) {
        setAlerts(res.alerts);
      } else if (res.latest_event) {
        setAlerts([res.latest_event]);
      } else {
        setAlerts([]);
      }
    } catch (err: any) {
      console.error("Failed to load watch overview:", err);
      if (err?.status === 404) {
        setError("This watch does not exist or you do not have permission to view it.");
      } else {
        setError(err?.message || "Failed to load watch details");
      }
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [watchId, isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      loadWatchOverview(true);
    }
  }, [isAuthenticated, loadWatchOverview]);

  // Live polling: 3s if running/repairing, 8s if healthy
  useEffect(() => {
    if (!isAuthenticated || !overview) return;

    const isDynamic =
      overview.health_status === "running" ||
      overview.health_status === "repairing" ||
      !!overview.active_repair;

    const pollIntervalMs = isDynamic ? 3000 : 8000;

    const interval = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        loadWatchOverview(false);
      }
    }, pollIntervalMs);

    return () => clearInterval(interval);
  }, [isAuthenticated, overview, loadWatchOverview]);

  if (userLoading || (!isAuthenticated && userLoading)) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <Radar className="w-8 h-8 text-radar-cyan animate-spin" />
          <p className="text-xs text-slate-400 font-mono">Restoring Web Radar session...</p>
        </div>
      </div>
    );
  }

  if (loading && !overview) {
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
        subtitle={`Monitoring target: ${overview.watch.url}`}
        onRefresh={() => loadWatchOverview(true)}
      />

      <div className="flex-1 p-6 md:p-8 space-y-8 max-w-7xl mx-auto w-full">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Link
            href="/watches"
            className="hover:text-radar-cyan flex items-center gap-1 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>All Watches</span>
          </Link>
          <span>/</span>
          <span className="text-slate-200 truncate">{overview.watch.title}</span>
        </div>

        {/* 1. Hero Overview Card */}
        <WatchDetailHero
          overview={overview}
          onRefresh={() => loadWatchOverview(false)}
          onOpenControls={() => setControlsOpen(true)}
        />

        {/* 2. Self-Healing Banner */}
        <SelfHealingBanner
          repair={overview.active_repair}
          collectorId={overview.watch.monitoring_spec?.collector_id}
        />


        {/* 3. Diagnostic Two-Column Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
          {/* Left Column: Semantic Change Events */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 px-1">
              <div className="flex items-center justify-center h-6 w-6 rounded-lg bg-radar-cyan/15 text-radar-cyan">
                <Activity className="h-3.5 w-3.5" />
              </div>
              <h3 className="text-base font-bold text-white tracking-tight">
                Semantic Change Events
              </h3>
            </div>
            <SemanticTimeline events={alerts} />
          </div>

          {/* Right Column: Immutable Run History */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 px-1">
              <div className="flex items-center justify-center h-6 w-6 rounded-lg bg-radar-indigo/15 text-radar-indigo">
                <History className="h-3.5 w-3.5" />
              </div>
              <h3 className="text-base font-bold text-white tracking-tight">
                Execution Run History
              </h3>
            </div>
            <RunHistory runs={runs} />
          </div>

        </div>
      </div>

      {/* Watch Controls Modal */}
      <WatchControlsModal
        overview={overview}
        isOpen={controlsOpen}
        onClose={() => setControlsOpen(false)}
        onUpdated={() => {
          setControlsOpen(false);
          loadWatchOverview(false);
        }}
        onDeleted={() => {
          setControlsOpen(false);
          router.push("/watches");
        }}
      />

    </div>
  );
}
