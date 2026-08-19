"use client";

import React, { useEffect, useState } from "react";
import { Header } from "../../components/layout/Header";
import { WatchCard } from "../../components/dashboard/WatchCard";
import { EmptyState } from "../../components/common/EmptyState";
import { useUser } from "../../lib/userContext";
import { WatchSummary } from "../../types";
import { api } from "../../lib/api";
import { Search, Eye, Filter, Plus } from "lucide-react";
import Link from "next/link";

export default function WatchesPage() {
  const { userId, loading: userLoading } = useUser();
  const [watches, setWatches] = useState<WatchSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterHealth, setFilterHealth] = useState<string>("all");

  const loadWatches = async () => {
    if (!userId) return;
    try {
      setLoading(true);
      const res = await api.getWatches(userId);
      setWatches(res);
    } catch (err) {
      console.error("Failed to load watches:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (userId) {
      loadWatches();
    }
  }, [userId]);

  const filteredWatches = watches.filter((w) => {
    const matchesSearch =
      w.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.domain.toLowerCase().includes(searchQuery.toLowerCase()) ||
      w.url.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesHealth =
      filterHealth === "all" || w.health_status === filterHealth;

    return matchesSearch && matchesHealth;
  });

  return (
    <div className="flex-1 flex flex-col min-h-full">
      <Header
        title="Active Radar Watches"
        subtitle="Manage all persistent web scraping and threshold triggers"
        onRefresh={loadWatches}
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
              placeholder="Search watches by title, domain, or URL..."
              className="w-full pl-10 pr-4 py-2 rounded-xl bg-space-950/80 border border-space-750 text-white text-xs placeholder-slate-500 focus:outline-none focus:border-radar-cyan"
            />
          </div>

          <div className="flex items-center gap-1.5 overflow-x-auto">
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
                className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-colors whitespace-nowrap ${
                  filterHealth === f.id
                    ? "bg-radar-cyan text-space-950 font-bold shadow-glow"
                    : "bg-space-850 hover:bg-space-800 text-slate-400 hover:text-slate-200 border border-space-700/60"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Watches Grid */}
        {loading || userLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div
                key={i}
                className="h-56 rounded-2xl bg-space-900/60 border border-space-750 animate-pulse p-5"
              />
            ))}
          </div>
        ) : filteredWatches.length === 0 ? (
          <EmptyState
            icon={Eye}
            title={
              searchQuery || filterHealth !== "all"
                ? "No Matching Watches"
                : "No Active Watches"
            }
            description={
              searchQuery || filterHealth !== "all"
                ? "Try clearing your search query or changing your health filter."
                : "You haven't created any Radar Watches yet. Create your first watch to monitor web prices and inventory."
            }
            actionText="Create New Watch"
            onAction={() => {
              window.location.href = "/";
            }}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredWatches.map((watch) => (
              <WatchCard key={watch.id} watch={watch} onRefresh={loadWatches} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
