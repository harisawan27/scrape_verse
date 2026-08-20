import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { AlertEvent, WatchRule } from "../types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount: number | null | undefined, currency: string = "PKR"): string {
  if (amount === null || amount === undefined) {
    return "—";
  }
  return `${currency} ${amount.toLocaleString("en-US", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

export function formatRelativeTime(dateString: string | null | undefined): string {
  if (!dateString) return "Never";
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffSeconds < 0) return "Just now";
    if (diffSeconds < 60) return `${diffSeconds}s ago`;
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return dateString;
  }
}

export function formatCadence(cadence: string, minutes?: number): string {
  if (cadence === "custom" && minutes) {
    if (minutes < 60) return `Every ${minutes}m`;
    if (minutes % 60 === 0) return `Every ${minutes / 60}h`;
    return `Every ${minutes}m`;
  }
  if (cadence === "hourly") return "Hourly";
  if (cadence === "daily") return "Daily";
  if (cadence === "weekly") return "Weekly";
  return cadence;
}

export function formatRuleDescription(rule: WatchRule): string {
  switch (rule.type) {
    case "price_below":
      return `Alert when price drops below ${formatCurrency(rule.value, rule.currency || "PKR")}`;
    case "price_above":
      return `Alert when price rises above ${formatCurrency(rule.value, rule.currency || "PKR")}`;
    case "price_drop":
      return "Alert on any price drop";
    case "back_in_stock":
      return "Alert when product comes back in stock";
    case "availability_changed":
      return "Alert when availability changes";
    default:
      return `${rule.type} on ${rule.field}`;
  }
}

export function formatHumanEventHeadline(event: AlertEvent): string {
  const prevPrice = event.details?.previous_value;
  const currPrice = event.details?.current_value;
  const threshold = event.details?.threshold;

  switch (event.event_type) {
    case "price_threshold_crossed":
      return threshold
        ? `Price crossed your target threshold (${formatCurrency(threshold)})`
        : `Price crossed your target threshold`;
    case "price_decreased":
      if (prevPrice && currPrice) {
        const pct = Math.round(((prevPrice - currPrice) / prevPrice) * 100);
        return `Price dropped by ${pct}%`;
      }
      return "Price decreased";
    case "back_in_stock":
      return "Product is back in stock";
    case "out_of_stock":
      return "Product went out of stock";
    case "availability_changed":
      return "Stock availability changed";
    default:
      return event.summary || event.event_type.replace(/_/g, " ");
  }
}

export function getEventTypeLabel(eventType: string): { label: string; color: string } {
  switch (eventType) {
    case "price_threshold_crossed":
      return { label: "Target Crossed", color: "text-radar-emerald bg-radar-emerald/10 border-radar-emerald/30" };
    case "price_decreased":
      return { label: "Price Drop", color: "text-radar-cyan bg-radar-cyan/10 border-radar-cyan/30" };
    case "price_increased":
      return { label: "Price Increase", color: "text-radar-rose bg-radar-rose/10 border-radar-rose/30" };
    case "back_in_stock":
      return { label: "Back in Stock", color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30" };
    case "out_of_stock":
      return { label: "Out of Stock", color: "text-radar-amber bg-radar-amber/10 border-radar-amber/30" };
    case "availability_changed":
      return { label: "Availability", color: "text-amber-400 bg-amber-500/10 border-amber-500/30" };
    case "repair_started":
    case "scraper_repair":
      return { label: "Self-Healing", color: "text-radar-amber bg-radar-amber/10 border-radar-amber/30" };
    default:
      return { label: eventType.replace(/_/g, " "), color: "text-gray-300 bg-gray-800 border-gray-700" };
  }
}
