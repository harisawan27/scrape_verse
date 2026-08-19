"use client";

import React, { useState } from "react";
import {
  Sparkles,
  ArrowRight,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Shield,
  Layers,
  Globe,
  Sliders,
  X,
  ExternalLink,
} from "lucide-react";
import { api, ApiError } from "../../lib/api";
import { useUser } from "../../lib/userContext";
import { Watch, WatchPlan, WatchPlanPreviewResponse } from "../../types";
import { formatCadence, formatCurrency } from "../../lib/utils";

interface CreateWatchHeroProps {
  onWatchCreated?: (watch: Watch) => void;
}

const SAMPLE_CHIPS = [
  {
    label: "Price below Rs 2,500",
    instruction: "Alert me when this drops below Rs 2,500",
    url: "https://www.daraz.pk/products/office-chair-i111.html",
  },
  {
    label: "Any Price Drop",
    instruction: "Tell me whenever the price drops on this item",
    url: "https://www.daraz.pk/products/gaming-mouse-i222.html",
  },
  {
    label: "Back in Stock",
    instruction: "Watch every 30 minutes and alert me when it is back in stock",
    url: "https://www.daraz.pk/products/wireless-earbuds-i333.html",
  },
  {
    label: "30m Scan + Rs 4,500 Target",
    instruction: "Watch this every 30 minutes and alert if price drops below 4500",
    url: "https://www.daraz.pk/products/mechanical-keyboard-i444.html",
  },
];

export function CreateWatchHero({ onWatchCreated }: CreateWatchHeroProps) {
  const { userId } = useUser();
  const [instruction, setInstruction] = useState("");
  const [url, setUrl] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [previewResult, setPreviewResult] = useState<WatchPlanPreviewResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successWatch, setSuccessWatch] = useState<Watch | null>(null);

  const handleChipClick = (chip: (typeof SAMPLE_CHIPS)[0]) => {
    setInstruction(chip.instruction);
    setUrl(chip.url);
    setPreviewResult(null);
    setErrorMessage(null);
    setSuccessWatch(null);
  };

  const handlePreview = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!instruction.trim()) {
      setErrorMessage("Please enter an instruction of what to watch.");
      return;
    }

    try {
      setPreviewing(true);
      setErrorMessage(null);
      setSuccessWatch(null);
      const res = await api.previewWatchPlan(instruction, url);
      setPreviewResult(res);
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to generate plan preview");
    } finally {
      setPreviewing(false);
    }
  };

  const handleConfirmCreate = async () => {
    if (!userId || !previewResult?.plan) return;

    try {
      setCreating(true);
      setErrorMessage(null);
      const created = await api.createWatchFromPlan(userId, previewResult.plan);
      setSuccessWatch(created);
      setPreviewResult(null);
      setInstruction("");
      setUrl("");
      if (onWatchCreated) {
        onWatchCreated(created);
      }
    } catch (err: any) {
      setErrorMessage(err?.message || "Failed to create watch from plan");
    } finally {
      setCreating(false);
    }
  };

  const handleClear = () => {
    setInstruction("");
    setUrl("");
    setPreviewResult(null);
    setErrorMessage(null);
    setSuccessWatch(null);
  };

  return (
    <div className="relative rounded-3xl p-6 md:p-8 bg-gradient-to-b from-space-850 to-space-900 border border-space-700/80 shadow-2xl overflow-hidden">
      {/* Background Subtle Radar Wave Glow */}
      <div className="absolute top-0 right-0 -mt-16 -mr-16 w-96 h-96 rounded-full bg-radar-cyan/10 blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-1/3 -mb-16 w-80 h-80 rounded-full bg-radar-indigo/10 blur-3xl pointer-events-none" />

      <div className="relative z-10">
        {/* Hero Title */}
        <div className="max-w-2xl mb-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-radar-indigo/15 border border-radar-indigo/30 text-indigo-300 text-xs font-semibold uppercase tracking-wider mb-3">
            <Sparkles className="h-3.5 w-3.5 text-radar-indigo" />
            <span>AI Natural-Language Watch Planner</span>
          </div>
          <h2 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight leading-tight">
            What should I watch for you?
          </h2>
          <p className="text-sm text-slate-400 mt-2 leading-relaxed">
            Tell Web Radar what to monitor in plain English. It tracks the web while you&apos;re away and surfaces only meaningful price and inventory changes.
          </p>
        </div>

        {/* Input Form */}
        <form onSubmit={handlePreview} className="space-y-4">
          <div className="space-y-3">
            {/* Instruction Textarea */}
            <div className="relative rounded-2xl bg-space-950/80 border border-space-700 focus-within:border-radar-cyan/80 focus-within:ring-2 focus-within:ring-radar-cyan/20 transition-all p-3.5">
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Monitoring Goal / Condition
              </label>
              <textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                rows={2}
                placeholder="e.g. Watch this Daraz ergonomic chair every 30 minutes and alert me when it drops below Rs 2,500..."
                className="w-full bg-transparent text-slate-100 text-sm placeholder-slate-500 focus:outline-none resize-none"
              />
            </div>

            {/* URL Input */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <div className="flex-1 relative rounded-xl bg-space-950/80 border border-space-700 focus-within:border-radar-cyan/80 focus-within:ring-2 focus-within:ring-radar-cyan/20 transition-all px-3.5 py-2.5 flex items-center gap-2.5">
                <Globe className="h-4 w-4 text-slate-400 flex-shrink-0" />
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="Target URL (e.g. https://www.daraz.pk/products/office-chair...)"
                  className="w-full bg-transparent text-slate-100 text-xs placeholder-slate-500 focus:outline-none"
                />
              </div>

              {/* Action Button */}
              <button
                type="submit"
                disabled={previewing || !instruction.trim()}
                className="flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-radar-cyan to-cyan-400 hover:from-cyan-400 hover:to-cyan-300 text-space-950 font-bold text-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-glow flex-shrink-0"
              >
                {previewing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Planning...</span>
                  </>
                ) : (
                  <>
                    <span>Preview Plan</span>
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Preset Prompt Chips */}
          <div className="pt-1">
            <div className="flex items-center gap-2 text-xs text-slate-400 mb-2">
              <span>Quick templates:</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_CHIPS.map((chip, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleChipClick(chip)}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-space-800/80 hover:bg-space-750 border border-space-700/80 text-slate-300 hover:text-white transition-all hover:border-radar-cyan/40"
                >
                  {chip.label}
                </button>
              ))}
            </div>
          </div>
        </form>

        {/* Error Message */}
        {errorMessage && (
          <div className="mt-4 p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2.5 animate-fadeIn">
            <AlertCircle className="h-4 w-4 text-rose-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">{errorMessage}</div>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-rose-400 hover:text-rose-200"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Success Confirmation Banner */}
        {successWatch && (
          <div className="mt-5 p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm flex items-center justify-between gap-3 animate-fadeIn">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-5 w-5 text-emerald-400 flex-shrink-0" />
              <div>
                <p className="font-semibold text-white">
                  Watch Activated & Persistent
                </p>
                <p className="text-xs text-emerald-300/80">
                  {successWatch.title} is now actively monitored by Bright Data Scraper Studio.
                </p>
              </div>
            </div>
            <button
              onClick={() => setSuccessWatch(null)}
              className="text-xs px-3 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-200 font-medium transition-colors"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Live Plan Preview Card */}
        {previewResult && (
          <div className="mt-6 p-5 rounded-2xl bg-space-950/90 border border-radar-cyan/40 shadow-glow animate-fadeIn">
            {previewResult.status === "ready" && previewResult.plan && (
              <div>
                <div className="flex items-center justify-between border-b border-space-700/60 pb-3 mb-4">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-radar-emerald animate-ping" />
                    <span className="text-xs font-bold uppercase tracking-wider text-radar-emerald">
                      Plan Verified & Ready
                    </span>
                  </div>
                  <span className="text-xs font-mono text-slate-400">
                    Collector: {previewResult.plan.collector_id}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <h4 className="text-base font-bold text-white mb-1">
                      {previewResult.plan.title}
                    </h4>
                    <p className="text-xs text-slate-400 flex items-center gap-1">
                      <Globe className="h-3.5 w-3.5 text-radar-cyan" />
                      <span className="truncate">{previewResult.plan.url}</span>
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 md:justify-end text-xs">
                    <div className="px-3 py-1.5 rounded-lg bg-space-850 border border-space-700 flex items-center gap-1.5 text-slate-300">
                      <Clock className="h-3.5 w-3.5 text-radar-cyan" />
                      <span>
                        Cadence:{" "}
                        <strong className="text-white">
                          {formatCadence(
                            previewResult.plan.schedule.cadence,
                            previewResult.plan.schedule.cadence_minutes
                          )}
                        </strong>
                      </span>
                    </div>
                    <div className="px-3 py-1.5 rounded-lg bg-space-850 border border-space-700 flex items-center gap-1.5 text-slate-300">
                      <Shield className="h-3.5 w-3.5 text-radar-emerald" />
                      <span>
                        Timezone:{" "}
                        <strong className="text-white">
                          {previewResult.plan.schedule.timezone}
                        </strong>
                      </span>
                    </div>
                  </div>
                </div>

                {/* Rules List */}
                <div className="p-3.5 rounded-xl bg-space-900 border border-space-750 mb-5">
                  <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-radar-indigo" />
                    <span>Deterministic Alert Rules</span>
                  </div>
                  <div className="space-y-1.5">
                    {previewResult.plan.monitoring_spec.rules.map((rule, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between text-xs py-1.5 px-2.5 rounded-lg bg-space-850/60 border border-space-700/40"
                      >
                        <span className="font-mono text-radar-cyan font-medium">
                          {rule.type}
                        </span>
                        <span className="text-slate-300">
                          {rule.type === "price_below" || rule.type === "price_above" ? (
                            <span>
                              Threshold:{" "}
                              <strong className="text-white">
                                {formatCurrency(rule.value, rule.currency || "PKR")}
                              </strong>
                            </span>
                          ) : rule.type === "back_in_stock" ? (
                            <span className="text-emerald-400 font-medium">
                              Trigger on stock availability change
                            </span>
                          ) : (
                            <span className="text-slate-300">
                              Trigger on value change
                            </span>
                          )}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Confirm Actions */}
                <div className="flex items-center justify-between gap-3 pt-2">
                  <button
                    type="button"
                    onClick={handleClear}
                    className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white bg-space-850 hover:bg-space-800 border border-space-700 transition-colors"
                  >
                    Cancel
                  </button>

                  <button
                    type="button"
                    onClick={handleConfirmCreate}
                    disabled={creating}
                    className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-radar-emerald hover:bg-emerald-400 text-space-950 font-bold text-xs transition-colors shadow-glow-emerald disabled:opacity-50"
                  >
                    {creating ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Activating Watch...</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="h-4 w-4" />
                        <span>Confirm & Start Monitoring</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {previewResult.status === "needs_clarification" && previewResult.clarification && (
              <div className="p-2">
                <div className="flex items-center gap-2 text-amber-400 text-xs font-bold uppercase tracking-wider mb-2">
                  <AlertCircle className="h-4 w-4" />
                  <span>Clarification Needed</span>
                </div>
                <h4 className="text-sm font-semibold text-white mb-1">
                  {previewResult.clarification.question}
                </h4>
                <p className="text-xs text-slate-400 mb-3">
                  {previewResult.clarification.reason}
                </p>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-slate-500">Missing:</span>
                  {previewResult.clarification.missing.map((m, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 text-[11px] font-mono"
                    >
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {previewResult.status === "unsupported" && (
              <div className="p-2">
                <div className="flex items-center gap-2 text-rose-400 text-xs font-bold uppercase tracking-wider mb-2">
                  <AlertCircle className="h-4 w-4" />
                  <span>Domain Unsupported</span>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {previewResult.message ||
                    "Web Radar MVP currently supports custom Scraper Studio monitoring on Daraz (*.daraz.pk)."}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
