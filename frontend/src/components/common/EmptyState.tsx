import React from "react";
import { Radar, ArrowRight } from "lucide-react";
import { cn } from "../../lib/utils";

interface EmptyStateProps {
  icon?: React.ElementType;
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
  className?: string;
}

export function EmptyState({
  icon: Icon = Radar,
  title,
  description,
  actionText,
  onAction,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center p-8 md:p-12 text-center rounded-2xl border border-dashed border-space-700 bg-space-900/40 backdrop-blur-sm",
        className
      )}
    >
      <div className="relative mb-4 flex items-center justify-center">
        <div className="h-16 w-16 rounded-2xl bg-radar-cyan/10 border border-radar-cyan/20 flex items-center justify-center text-radar-cyan">
          <Icon className="h-8 w-8" />
        </div>
        <div className="absolute -inset-1 rounded-2xl bg-radar-cyan/10 blur-sm -z-10" />
      </div>

      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-sm text-slate-400 max-w-md leading-relaxed mb-6">
        {description}
      </p>

      {actionText && onAction && (
        <button
          onClick={onAction}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-radar-cyan/20 border border-radar-cyan/40 hover:bg-radar-cyan/30 rounded-xl transition-colors duration-200"
        >
          <span>{actionText}</span>
          <ArrowRight className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
