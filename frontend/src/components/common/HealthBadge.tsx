import React from "react";
import { HealthStatus } from "../../types";
import { cn } from "../../lib/utils";

interface HealthBadgeProps {
  status: HealthStatus;
  size?: "sm" | "md" | "lg";
  className?: string;
  showText?: boolean;
}

export function HealthBadge({
  status,
  size = "md",
  className,
  showText = true,
}: HealthBadgeProps) {
  const configs: Record<
    HealthStatus,
    {
      label: string;
      bg: string;
      text: string;
      border: string;
      dot: string;
      pulse: boolean;
    }
  > = {
    healthy: {
      label: "Healthy",
      bg: "bg-emerald-500/10",
      text: "text-emerald-400",
      border: "border-emerald-500/20",
      dot: "bg-emerald-400",
      pulse: false,
    },
    running: {
      label: "Running",
      bg: "bg-cyan-500/15",
      text: "text-cyan-300",
      border: "border-cyan-500/30",
      dot: "bg-cyan-400",
      pulse: true,
    },
    repairing: {
      label: "Self-Healing",
      bg: "bg-amber-500/15",
      text: "text-amber-300",
      border: "border-amber-500/30",
      dot: "bg-amber-400",
      pulse: true,
    },
    failed: {
      label: "Failed",
      bg: "bg-rose-500/10",
      text: "text-rose-400",
      border: "border-rose-500/20",
      dot: "bg-rose-400",
      pulse: false,
    },
    paused: {
      label: "Paused",
      bg: "bg-slate-500/10",
      text: "text-slate-400",
      border: "border-slate-500/20",
      dot: "bg-slate-400",
      pulse: false,
    },
  };

  const config = configs[status] || configs.healthy;

  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs gap-1.5",
    md: "px-2.5 py-1 text-xs gap-2",
    lg: "px-3 py-1.5 text-sm gap-2",
  };

  const dotSizes = {
    sm: "h-1.5 w-1.5",
    md: "h-2 w-2",
    lg: "h-2.5 w-2.5",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center font-medium rounded-full border transition-all duration-200",
        config.bg,
        config.text,
        config.border,
        sizeClasses[size],
        className
      )}
    >
      <span className="relative flex items-center justify-center">
        <span
          className={cn("rounded-full", config.dot, dotSizes[size])}
        />
        {config.pulse && (
          <span
            className={cn(
              "absolute rounded-full opacity-75 animate-ping",
              config.dot,
              dotSizes[size]
            )}
          />
        )}
      </span>
      {showText && <span>{config.label}</span>}
    </span>
  );
}
