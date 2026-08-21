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
  Cloud,
  Check,
  Zap,
} from "lucide-react";
import { api } from "../../lib/api";
import { useUser } from "../../lib/userContext";
import { Watch, WatchPlanPreviewResponse } from "../../types";
import { formatCadence, formatCurrency } from "../../lib/utils";

interface CreateWatchHeroProps {
  onWatchCreated?: (watch: Watch) => void;
}

const SAMPLE_CHIPS = [
  {
    label: "Alert below Rs 2,500",
    instruction: "Watch this Daraz chair every 30 minutes and alert me when it drops below Rs 2,500",
    url: "https://www.daraz.pk/products/boss-hb-8043a-high-back-ergonomic-chair-boss-mesh-chair-hb-8043a-i456382103-s2188258284.html",
  },
  {
    label: "Any Price Drop",
    instruction: "Tell me whenever the price drops on this item",
    url: "https://www.daraz.pk/products/a4tech-op-720-optical-mouse-usb-wired-1000-dpi-i429780182-s2046200236.html",
  },
  {
    label: "Back in Stock Alert",
    instruction: "Watch every 30 minutes and alert me when it comes back in stock",
    url: "https://www.daraz.pk/products/m10-tws-wireless-earbuds-bluetooth-51-digital-display-touch-control-i424756858-s2014169992.html",
  },
  {
    label: "Rs 5,000 Target + 30m Scan",
    instruction: "Watch this every 30 minutes and alert if price drops below 5000",
    url: "https://www.daraz.pk/products/rgb-mechanical-gaming-keyboard-blue-switches-i430292834-s2049924821.html",
  },
];

const CORE_LOOP_STEPS = [
  { step: "1", title: "Tell it what matters", desc: "Natural language goal & URL" },
  { step: "2", title: "Monitors 24/7", desc: "Bright Data Scraper Studio" },
  { step: "3", title: "Meaningful change", desc: "Deterministic thresholds" },
  { step: "4", title: "You get the signal", desc: "Surfaced when you return" },
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
      setErrorMessage("Please describe what Web Radar should watch for you.");
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
      {/* Background Glows */}
      <div className="absolute top-0 right-0 -mt-16 -mr-16 w-96 h-96 rounded-full bg-radar-cyan/10 blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-1/3 -mb-16 w-80 h-80 rounded-full bg-radar-indigo/10 blur-3xl pointer-events-none" />

      <div className="relative z-10 space-y-6">
        {/* Top Header: Badge + Headline */}
        <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
          <div className="max-w-2xl">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-radar-indigo/15 border border-radar-indigo/30 text-indigo-300 text-xs font-semibold uppercase tracking-wider">
                <Sparkles className="h-3.5 w-3.5 text-radar-indigo" />
                <span>AI Natural-Language Watch Planner</span>
              </div>

              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-radar-cyan/10 border border-radar-cyan/25 text-radar-cyan text-xs font-mono">
                <Cloud className="h-3.5 w-3.5 text-radar-cyan" />
                <span>Powered by Bright Data Scraper Studio</span>
              </div>
            </div>

            <h2 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-white tracking-tight leading-tight">
              What should I watch for you?
            </h2>
            <p className="text-sm text-slate-300 mt-2 leading-relaxed max-w-xl">
              Give Web Radar a page and tell it what matters. It monitors in the background, detects meaningful changes, and repairs broken scrapers when sites change.
            </p>
          </div>

          {/* 2. Visual Core Loop Mini-Stepper */}
          <div className="hidden lg:block p-3.5 rounded-2xl bg-space-950/70 border border-space-750 max-w-xs flex-shrink-0">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2.5 flex items-center gap-1.5">
              <Zap className="h-3.5 w-3.5 text-amber-400" />
              <span>How Web Radar Works</span>
            </div>
            <div className="space-y-1.5 text-[11px]">
              {CORE_LOOP_STEPS.map((s, idx) => (
                <div key={idx} className="flex items-center gap-2 text-slate-300">
                  <span className="flex-shrink-0 h-4 w-4 rounded-full bg-space-800 border border-space-700 text-radar-cyan text-[10px] font-bold flex items-center justify-center">
                    {s.step}
                  </span>
                  <span className="font-semibold text-white">{s.title}:</span>
                  <span className="text-slate-400 text-[10px] truncate">{s.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Input Form */}
        <form onSubmit={handlePreview} className="space-y-4">
          <div className="space-y-3">
            {/* Instruction Textarea */}
            <div className="relative rounded-2xl bg-space-950/90 border border-space-700 focus-within:border-radar-cyan/80 focus-within:ring-2 focus-within:ring-radar-cyan/20 transition-all p-3.5">
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  Monitoring Goal & Conditions
                </label>
                <span className="text-[10px] text-slate-500 font-mono">
                  Natural Language (e.g. price drops below 2500, stock status, 30m)
                </span>
              </div>
              <textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                rows={2}
                placeholder="e.g. Watch this Daraz chair every 30 minutes and alert me when it drops below Rs 2,500..."
                className="w-full bg-transparent text-slate-100 text-sm placeholder-slate-500 focus:outline-none resize-none leading-relaxed"
              />
            </div>

            {/* URL Input */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <div className="flex-1 relative rounded-xl bg-space-950/90 border border-space-700 focus-within:border-radar-cyan/80 focus-within:ring-2 focus-within:ring-radar-cyan/20 transition-all px-3.5 py-2.5 flex items-center gap-2.5">
                <Globe className="h-4 w-4 text-radar-cyan flex-shrink-0" />
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="Target URL (e.g. https://www.daraz.pk/products/office-chair...)"
                  className="w-full bg-transparent text-slate-100 text-xs placeholder-slate-500 focus:outline-none font-mono"
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
                    <span>Interpreting Plan...</span>
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
              <span className="font-semibold text-slate-300">Quick Templates:</span>
              <span className="text-[11px] text-slate-500">(Click to load a live Daraz item with target rule)</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_CHIPS.map((chip, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleChipClick(chip)}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-space-800/90 hover:bg-space-750 border border-space-700/80 text-slate-300 hover:text-white transition-all hover:border-radar-cyan/50 hover:shadow-sm"
                >
                  {chip.label}
                </button>
              ))}
            </div>
          </div>
        </form>

        {/* Error Message */}
        {errorMessage && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2.5 animate-fadeIn">
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
          <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm flex items-center justify-between gap-3 animate-fadeIn">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="h-5 w-5 text-emerald-400 flex-shrink-0" />
              <div>
                <p className="font-semibold text-white">
                  Watch Activated & Persistent
                </p>
                <p className="text-xs text-emerald-300/90">
                  <strong>{successWatch.title}</strong> is now monitored by Bright Data Scraper Studio.
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
          <div className="p-5 md:p-6 rounded-2xl bg-space-950/95 border border-radar-cyan/40 shadow-glow animate-fadeIn space-y-4">
            {previewResult.status === "ready" && previewResult.plan && (
              <div>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-space-700/60 pb-3 mb-4">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-radar-emerald animate-ping" />
                    <span className="text-xs font-bold uppercase tracking-wider text-radar-emerald">
                      Interpreted Monitoring Plan (Ready for Confirmation)
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs font-mono text-radar-cyan bg-radar-cyan/10 px-2 py-0.5 rounded border border-radar-cyan/20">
                    <Cloud className="h-3 w-3" />
                    <span>Bright Data Custom Collector: {previewResult.plan.collector_id}</span>
                  </div>
                </div>

                {/* Plan Highlights Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div className="space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Target Monitored Product
                    </span>
                    <h4 className="text-base font-bold text-white leading-snug">
                      {previewResult.plan.title}
                    </h4>
                    <p className="text-xs text-slate-400 flex items-center gap-1 font-mono truncate max-w-md">
                      <Globe className="h-3.5 w-3.5 text-radar-cyan flex-shrink-0" />
                      <span className="truncate">{previewResult.plan.url}</span>
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2.5 md:justify-end text-xs">
                    <div className="px-3 py-2 rounded-xl bg-space-900 border border-space-750 flex items-center gap-2 text-slate-300">
                      <Clock className="h-4 w-4 text-radar-cyan" />
                      <div>
                        <div className="text-[10px] uppercase text-slate-400 font-mono">Cadence</div>
                        <strong className="text-white font-mono">
                          {formatCadence(
                            previewResult.plan.schedule.cadence,
                            previewResult.plan.schedule.cadence_minutes
                          )}
                        </strong>
                      </div>
                    </div>
                    <div className="px-3 py-2 rounded-xl bg-space-900 border border-space-750 flex items-center gap-2 text-slate-300">
                      <Shield className="h-4 w-4 text-radar-emerald" />
                      <div>
                        <div className="text-[10px] uppercase text-slate-400 font-mono">Timezone</div>
                        <strong className="text-white font-mono">
                          {previewResult.plan.schedule.timezone}
                        </strong>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Rules List */}
                <div className="p-4 rounded-xl bg-space-900 border border-space-750 mb-5 space-y-2">
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-radar-indigo" />
                    <span>Deterministic Alert Condition</span>
                  </div>
                  <div className="space-y-2">
                    {(previewResult.plan?.monitoring_spec?.rules || []).map((rule, idx) => (
                      <div
                        key={idx}
                        className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2.5 rounded-lg bg-space-950/70 border border-space-750 text-xs font-mono"
                      >
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded bg-radar-cyan/15 text-radar-cyan font-bold uppercase text-[10px]">
                            {rule.type}
                          </span>
                          <span className="text-slate-300">
                            Evaluated against <strong className="text-white font-sans">{rule.field}</strong>
                          </span>
                        </div>
                        <div className="text-right">
                          {rule.type === "price_below" || rule.type === "price_above" ? (
                            <span className="text-emerald-400 font-bold text-sm">
                              Threshold: {formatCurrency(rule.value, rule.currency || "PKR")}
                            </span>
                          ) : (
                            <span className="text-radar-cyan font-semibold">
                              Trigger on stock status transition
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Confirm Actions */}
                <div className="flex items-center justify-between gap-3 pt-2">
                  <button
                    type="button"
                    onClick={handleClear}
                    className="px-4 py-2.5 rounded-xl text-xs font-medium text-slate-400 hover:text-white bg-space-900 hover:bg-space-850 border border-space-750 transition-colors"
                  >
                    Cancel
                  </button>

                  <button
                    type="button"
                    onClick={handleConfirmCreate}
                    disabled={creating}
                    className="flex items-center gap-2 px-6 py-3 rounded-xl bg-radar-emerald hover:bg-emerald-400 text-space-950 font-bold text-xs transition-all shadow-glow-emerald disabled:opacity-50"
                  >
                    {creating ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Activating Watch in Neon DB...</span>
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
              <div className="p-3 space-y-3">
                <div className="flex items-center gap-2 text-amber-400 text-xs font-bold uppercase tracking-wider">
                  <AlertCircle className="h-4 w-4" />
                  <span>Clarification Needed</span>
                </div>
                <h4 className="text-sm font-semibold text-white leading-relaxed">
                  {previewResult.clarification.question}
                </h4>
                <p className="text-xs text-slate-400">
                  {previewResult.clarification.reason}
                </p>
                <div className="flex items-center gap-2 pt-1">
                  <span className="text-[11px] text-slate-500 font-mono">Missing parameters:</span>
                  {(previewResult.clarification.missing || []).map((m, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 text-[11px] font-mono font-semibold"
                    >
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {previewResult.status === "unsupported" && (
              <div className="p-3 space-y-2">
                <div className="flex items-center gap-2 text-rose-400 text-xs font-bold uppercase tracking-wider">
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
