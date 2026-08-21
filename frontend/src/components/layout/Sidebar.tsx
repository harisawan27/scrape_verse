"use client";

import React, { useState } from "react";
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
  LogOut,
  Settings,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useUser } from "../../lib/userContext";

function GoogleIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24">
      <path
        fill="#4285F4"
        d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.27 21.43 7.35 24 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 10.03 0 12s.45 3.82 1.25 5.42l4.03-3.15Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.35 0 3.27 2.57 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98Z"
      />
    </svg>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { user, isAuthenticated, loading, linkGoogleAccount, signOut } = useUser();
  const [linkingGoogle, setLinkingGoogle] = useState(false);

  // Hide sidebar on auth pages or when completely unauthenticated
  if (pathname === "/sign-in" || pathname === "/sign-up" || (!loading && !isAuthenticated)) {
    return null;
  }

  const handleLinkGoogle = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      setLinkingGoogle(true);
      await linkGoogleAccount();
    } catch (err) {
      console.error("Failed to initiate Google link:", err);
      setLinkingGoogle(false);
    }
  };

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
    {
      label: "Settings",
      href: "/settings",
      icon: Settings,
      active: pathname.startsWith("/settings"),
    },
  ];

  const displayName = user?.name || user?.email?.split("@")[0] || "User";
  const userInitials = displayName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

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
              <span className="font-extrabold text-base tracking-tight text-white group-hover:text-radar-cyan transition-colors">
                Web Radar
              </span>
              <span className="px-1.5 py-0.2 rounded text-[9px] font-bold uppercase tracking-wider bg-radar-cyan/15 text-radar-cyan border border-radar-cyan/30">
                PRO
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono">Autonomous Monitor</p>
          </div>
        </Link>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 px-3 py-4 space-y-6 overflow-y-auto">
        <div className="space-y-1">
          <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Observation
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all group relative",
                  item.active
                    ? "bg-radar-cyan/15 text-radar-cyan border border-radar-cyan/30 shadow-glow"
                    : "text-slate-400 hover:text-slate-200 hover:bg-space-850/80 border border-transparent"
                )}
              >
                <Icon
                  className={cn(
                    "h-4 w-4 transition-transform group-hover:scale-110",
                    item.active ? "text-radar-cyan" : "text-slate-400 group-hover:text-slate-200"
                  )}
                />
                <span>{item.label}</span>
                {item.active && (
                  <span className="absolute right-2.5 h-1.5 w-1.5 rounded-full bg-radar-cyan shadow-[0_0_6px_#06b6d4]" />
                )}
              </Link>
            );
          })}
        </div>

        {/* Quick Actions */}
        <div className="px-3 space-y-2">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Action Center
          </div>
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

      {/* User Session Footer — connects directly to /settings */}
      <div className="p-4 border-t border-space-700/50 bg-space-950/40">
        <div className="flex items-center justify-between gap-2">
          <Link
            href="/settings"
            className="flex items-center gap-2.5 overflow-hidden flex-1 min-w-0 group hover:opacity-90 transition-opacity"
            title="Open Account Settings"
          >
            {user?.image ? (
              <div className="h-8 w-8 rounded-lg overflow-hidden border border-cyan-400/50 shrink-0">
                <img
                  src={user.image}
                  alt={displayName}
                  className="h-full w-full object-cover"
                />
              </div>
            ) : (
              <div className="h-8 w-8 rounded-lg bg-space-800 border border-space-700 flex items-center justify-center text-xs font-bold text-cyan-400 shrink-0 group-hover:border-cyan-400 transition-colors">
                {userInitials || "WR"}
              </div>
            )}
            <div className="overflow-hidden min-w-0">
              <p className="text-xs font-medium text-white truncate group-hover:text-cyan-400 transition-colors">
                {displayName}
              </p>
              <p className="text-[10px] text-emerald-400 font-mono flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                Settings
              </p>
            </div>
          </Link>
          {isAuthenticated && (
            <button
              onClick={signOut}
              title="Sign Out"
              className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-950/30 border border-transparent hover:border-red-900/40 transition-colors shrink-0 cursor-pointer"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
