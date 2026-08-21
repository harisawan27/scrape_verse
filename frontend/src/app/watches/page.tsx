"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Header } from "../../components/layout/Header";
import { WatchCard } from "../../components/dashboard/WatchCard";
import { EmptyState } from "../../components/common/EmptyState";
import { useUser } from "../../lib/userContext";
import { WatchSummary } from "../../types";
import { api } from "../../lib/api";
import { Search, Eye, Filter, Plus, Radar } from "lucide-react";
import Link from "next/link";

export default function WatchesPage() {
  const router = useRouter();
  const { userId, isAuthenticated, loading: userLoading } = useUser();
  const [watches, setWatches] = useState<WatchSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterHealth, setFilterHealth] = useState<string>("all");

  // Protect route
  useEffect(() => {
    if (!userLoading && !isAuthenticated) {
      router.replace("/sign-in");
    }
  }, [isAuthenticated, userLoading, router]);

  const loadWatches = useCallback(async (showLoading = true) => {
    if (!userId && !isAuthenticated) return;
    try {
      if (showLoading) setLoading(true);
      const res = await api.getWatches(userId || undefined);
      setWatches(Array.isArray(res) ? res : []);
    } catch (err) {
      console.error("Failed to load watches:", err);
      setWatches([]);
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [userId, isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      loadWatches(true);
    }
  }, [isAuthenticated, loadWatches]);

  // Live polling (every 5 seconds when tab is active)
  useEffect(() => {
    if (!isAuthenticated) return;

    const interval = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        loadWatches(false);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [isAuthenticated, loadWatches]);

  const safeWatches = Array.isArray(watches) ? watches : [];

  const filteredWatches = safeWatches.filter((w) => {
    if (!w) return false;
    const title = w.title || "";
    const domain = w.domain || "";
    const url = w.url || "";
    const matchesSearch =
      title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      domain.toLowerCase().includes(searchQuery.toLowerCase()) ||
      url.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesHealth =
      filterHealth === "all" || w.health_status === filterHealth;

    return matchesSearch && matchesHealth;
  });

  if (userLoading || (!isAuthenticated && userLoading)) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <Radar className="w-8 h-8 text-radar-cyan animate-spin" />
          <p className="text-xs text-slate-400 font-mono">Loading watches...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-full">
      <Header
        title="Active Radar Watches"
        subtitle="Manage all persistent web scraping and threshold triggers"
        onRefresh={() => loadWatches(true)}
      />

      <div className="flex-1 p-6 md:p-8 space-y-6 max-w-7xl mx-auto w-full">
        {/* Search & Filter Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 p-4 rounded-2xl bg-space-900/80 border border-space-700/80">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by product name, URL, or domain (e.g. priceoye.pk, daraz.pk)..."
              className="w-full pl-10 pr-4 py-2 bg-space-950/80 border border-space-700/80 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-radar-cyan/60 transition-colors"
            />
          </div>

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
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-colors ${
                  filterHealth === f.id
                    ? "bg-radar-cyan text-space-950 font-bold"
                    : "bg-space-850 hover:bg-space-800 text-slate-400 hover:text-slate-200 border border-space-700/60"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Watches Grid / Empty State */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div
                key={i}
                className="h-56 rounded-2xl bg-space-900/60 border border-space-750 animate-pulse p-5"
              />
            ))}
          </div>
        ) : filteredWatches.length === 0 ? (
          safeWatches.length === 0 ? (
            <EmptyState
              icon={Eye}
              title="No Watches Found"
              description="You haven't created any watches yet. Create your first autonomous watch from the Command Center."
              actionText="Go to Command Center"
              onAction={() => router.push("/")}
            />
          ) : (
            <div className="p-12 rounded-2xl bg-space-900/40 border border-space-750 text-center">
              <p className="text-sm text-slate-400">
                No Watches matching &quot;{searchQuery || filterHealth}&quot;
              </p>
            </div>
          )
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredWatches.map((watch) => (
              <WatchCard
                key={watch.id}
                watch={watch}
                onRefresh={() => loadWatches(false)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
