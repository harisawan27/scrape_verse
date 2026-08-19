"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Radar,
  LayoutDashboard,
  Eye,
  Activity,
  PlusCircle,
  Database,
  Cloud,
  Sparkles,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useUser } from "../../lib/userContext";

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useUser();

  const navItems = [
    {
      label: "Command Center",
      href: "/",
      icon: LayoutDashboard,
      active: pathname === "/",
    },
    {
      label: "Active Watches",
      href: "/watches",
      icon: Eye,
      active: pathname.startsWith("/watches"),
    },
    {
      label: "While You Were Away",
      href: "/activity",
      icon: Activity,
      active: pathname.startsWith("/activity"),
    },
  ];

  return (
    <aside className="w-64 flex-shrink-0 bg-space-900/90 border-r border-space-700/60 flex flex-col justify-between h-screen sticky top-0 z-30 backdrop-blur-md">
      {/* Brand Header */}
      <div className="p-5 border-b border-space-700/50">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="relative flex items-center justify-center h-10 w-10 rounded-xl bg-gradient-to-br from-radar-cyan/20 to-radar-indigo/20 border border-radar-cyan/40 text-radar-cyan group-hover:border-radar-cyan/80 transition-colors">
            <Radar className="h-5 w-5 animate-pulse-slow" />
            <span className="absolute -top-1 -right-1 h-2.5 w-2.5 rounded-full bg-radar-cyan shadow-[0_0_8px_#06b6d4]" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-base font-bold tracking-tight text-white">
                Web Radar
              </span>
              <span className="text-[10px] uppercase font-semibold tracking-wider px-1.5 py-0.5 rounded bg-radar-cyan/15 text-radar-cyan border border-radar-cyan/30">
                MVP
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono">
              Persistent Web Monitoring
            </p>
          </div>
        </Link>
      </div>

      {/* Main Navigation */}
      <div className="px-3 py-4 flex-1 space-y-6 overflow-y-auto">
        <div>
          <div className="px-3 mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Control Surface
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group",
                    item.active
                      ? "bg-radar-cyan/10 text-radar-cyan border border-radar-cyan/30 shadow-[0_0_15px_rgba(6,182,212,0.15)]"
                      : "text-slate-400 hover:text-slate-200 hover:bg-space-800/60"
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4 transition-colors",
                      item.active
                        ? "text-radar-cyan"
                        : "text-slate-400 group-hover:text-slate-200"
                    )}
                  />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Quick Launch CTA */}
        <div className="p-3 rounded-2xl bg-gradient-to-b from-space-800 to-space-850 border border-space-700/80">
          <div className="flex items-center gap-2 text-xs font-semibold text-white mb-1.5">
            <Sparkles className="h-4 w-4 text-radar-indigo" />
            <span>AI Natural Planner</span>
          </div>
          <p className="text-xs text-slate-400 mb-3 leading-relaxed">
            Tell Web Radar what product and price to watch in plain English.
          </p>
          <Link
            href="/"
            className="flex items-center justify-center gap-2 w-full py-2 px-3 rounded-xl bg-radar-cyan text-space-950 font-semibold text-xs hover:bg-cyan-300 transition-colors shadow-glow"
          >
            <PlusCircle className="h-4 w-4" />
            <span>New Radar Watch</span>
          </Link>
        </div>

        {/* System Architecture Boundaries */}
        <div className="px-3 space-y-2.5">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            System Live Signals
          </div>
          <div className="space-y-1.5 text-xs">
            <div className="flex items-center justify-between p-2 rounded-lg bg-space-850/60 border border-space-700/40">
              <div className="flex items-center gap-2 text-slate-300">
                <Database className="h-3.5 w-3.5 text-emerald-400" />
                <span className="text-[11px]">Neon PostgreSQL</span>
              </div>
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_#10b981]" />
            </div>
            <div className="flex items-center justify-between p-2 rounded-lg bg-space-850/60 border border-space-700/40">
              <div className="flex items-center gap-2 text-slate-300">
                <Cloud className="h-3.5 w-3.5 text-radar-cyan" />
                <span className="text-[11px]">Bright Data Studio</span>
              </div>
              <span className="h-1.5 w-1.5 rounded-full bg-radar-cyan shadow-[0_0_6px_#06b6d4]" />
            </div>
          </div>
        </div>
      </div>

      {/* User Session Footer */}
      <div className="p-4 border-t border-space-700/50 bg-space-950/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="h-8 w-8 rounded-lg bg-space-800 border border-space-700 flex items-center justify-center text-xs font-bold text-slate-300">
              {user ? user.email.slice(0, 2).toUpperCase() : "WR"}
            </div>
            <div className="overflow-hidden">
              <p className="text-xs font-medium text-white truncate">
                {user ? user.email : "Connecting..."}
              </p>
              <p className="text-[10px] text-slate-400 font-mono">
                Authoritative Mode
              </p>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
