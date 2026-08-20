"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { Header } from "../components/layout/Header";
import { CreateWatchHero } from "../components/dashboard/CreateWatchHero";
import { WhileYouWereAway } from "../components/dashboard/WhileYouWereAway";
import { WatchCard } from "../components/dashboard/WatchCard";
import { EmptyState } from "../components/common/EmptyState";
import { useUser } from "../lib/userContext";
import { AlertEvent, HealthStatus, Watch, WatchSummary } from "../types";
import { api } from "../lib/api";
import { Eye, Filter, Loader2, Radar, Sparkles } from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const { user, userId, isAuthenticated, loading: userLoading } = useUser();
  const [watches, setWatches] = useState<WatchSummary[]>([]);
  const [activity, setActivity] = useState<AlertEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterHealth, setFilterHealth] = useState<string>("all");

  // Protect route
  useEffect(() => {
    if (!userLoading && !isAuthenticated) {
      router.replace("/sign-in");
    }
  }, [isAuthenticated, userLoading, router]);

  const loadData = useCallback(async (showLoading = true) => {
    if (!userId && !isAuthenticated) return;
    try {
      if (showLoading) setLoading(true);
      const [watchesRes, activityRes] = await Promise.all([
        api.getWatches(userId || undefined).catch(() => []),
        api.getActivity(userId || undefined, 10).catch(() => []),
      ]);
      setWatches(watchesRes);
      setActivity(activityRes);
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [userId, isAuthenticated]);

  // Initial load
  useEffect(() => {
    if (isAuthenticated) {
      loadData(true);
    }
  }, [isAuthenticated, loadData]);

  // Live background polling (5 seconds for watches, 8 seconds for activity)
  useEffect(() => {
    if (!isAuthenticated) return;

    const interval = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        loadData(false);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [isAuthenticated, loadData]);

  const handleWatchCreated = (newWatch: Watch) => {
    loadData(false);
  };

  const filteredWatches = watches.filter((w) => {
    if (filterHealth === "all") return true;
    return w.health_status === filterHealth;
  });

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

  return (
    <div className="flex-1 flex flex-col min-h-full">
      <Header
        title="Monitoring Command Center"
        subtitle="Autonomous web observation & semantic change intelligence"
        onRefresh={() => loadData(true)}
      />

      <div className="flex-1 p-6 md:p-8 space-y-8 max-w-7xl mx-auto w-full">
        {/* 1. Natural Language Watch Creation Hero */}
        <CreateWatchHero onWatchCreated={handleWatchCreated} />

        {/* 2. While You Were Away (Recent Semantic Alerts) */}
        <WhileYouWereAway events={activity} loading={loading} />

        {/* 3. Active Watches Section */}
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-space-700/60 pb-3">
            <div className="flex items-center gap-2.5">
              <div className="flex items-center justify-center h-6 w-6 rounded-lg bg-radar-cyan/15 text-radar-cyan">
                <Eye className="h-3.5 w-3.5" />
              </div>
              <h3 className="text-base font-bold text-white tracking-tight">
                Active Radar Watches
              </h3>
              <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-space-800 text-slate-300 border border-space-700">
                {watches.length}
              </span>
            </div>

            {/* Health Filter Chips */}
            {watches.length > 0 && (
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
                {[
                  { id: "all", label: "All" },
                  { id: "healthy", label: "Healthy" },
                  { id: "running", label: "Running" },
                  { id: "repairing", label: "Self-Healing" },
                  { id: "failed", label: "Failed" },
                  { id: "paused", label: "Paused" },
                ].map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setFilterHealth(f.id)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                      filterHealth === f.id
                        ? "bg-radar-cyan text-space-950 font-bold"
                        : "bg-space-850 hover:bg-space-800 text-slate-400 hover:text-slate-200 border border-space-700/60"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-56 rounded-2xl bg-space-900/60 border border-space-750 animate-pulse p-5"
                />
              ))}
            </div>
          ) : filteredWatches.length === 0 ? (
            watches.length === 0 ? (
              <EmptyState
                icon={Radar}
                title="No Active Watches Yet"
                description="Use the AI Natural-Language Planner above to tell Web Radar what product and price to watch. It will monitor continuously while you're away."
                actionText="Try Example: Price below Rs 2,500"
                onAction={() => {
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              />
            ) : (
              <div className="p-8 rounded-2xl bg-space-900/40 border border-space-750 text-center">
                <p className="text-sm text-slate-400">
                  No Watches match the &quot;{filterHealth}&quot; filter.
                </p>
              </div>
            )
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredWatches.map((watch) => (
                <WatchCard key={watch.id} watch={watch} onRefresh={() => loadData(false)} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
