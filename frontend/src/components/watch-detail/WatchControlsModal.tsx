"use client";

import React, { useState } from "react";
import { X, Save, Trash2, Loader2, Clock, AlertTriangle, Sliders } from "lucide-react";
import { Watch, WatchOverview } from "../../types";
import { api } from "../../lib/api";

interface WatchControlsModalProps {
  overview: WatchOverview;
  isOpen: boolean;
  onClose: () => void;
  onUpdated: () => void;
  onDeleted: () => void;
}

export function WatchControlsModal({
  overview,
  isOpen,
  onClose,
  onUpdated,
  onDeleted,
}: WatchControlsModalProps) {
  const { watch } = overview;
  const initialThreshold =
    watch.monitoring_spec?.rules?.find((r) => r.type === "price_below")?.value ||
    watch.monitoring_spec?.rules?.[0]?.value ||
    "";
  const initialCadence = watch.schedule?.cadence || "custom";

  const [cadence, setCadence] = useState<string>(initialCadence);
  const [cadenceMinutes, setCadenceMinutes] = useState<number>(
    watch.monitoring_spec?.cadence_minutes || 30
  );
  const [threshold, setThreshold] = useState<string | number>(initialThreshold);
  const [status, setStatus] = useState<string>(watch.status);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setError(null);

      // Build updated rules
      const updatedRules = (watch.monitoring_spec?.rules || []).map((rule) => {
        if (rule.type === "price_below" || rule.type === "price_above") {
          return {
            ...rule,
            value: Number(threshold) || rule.value,
          };
        }
        return rule;
      });

      const updatePayload = {
        status: status as any,
        monitoring_spec: {
          ...watch.monitoring_spec,
          cadence_minutes: cadenceMinutes,
          rules: updatedRules,
        },
        schedule: {
          cadence: cadence as any,
          timezone: watch.schedule?.timezone || "Asia/Karachi",
        },
      };

      await api.updateWatch(watch.id, updatePayload);
      onUpdated();
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to update Watch");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(`Are you sure you want to delete "${watch.title}"?`)) {
      return;
    }
    try {
      setDeleting(true);
      setError(null);
      await api.deleteWatch(watch.id);
      onDeleted();
    } catch (err: any) {
      setError(err?.message || "Failed to delete Watch");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-space-950/80 backdrop-blur-sm animate-fadeIn">
      <div className="relative w-full max-w-lg rounded-3xl bg-space-900 border border-space-700 shadow-2xl p-6 md:p-8 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-space-750 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-radar-cyan/10 border border-radar-cyan/30 text-radar-cyan">
              <Sliders className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white">Configure Watch</h3>
              <p className="text-xs text-slate-400">Modify cadence, threshold, and status</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-space-800 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-4">
          {/* Status (Active / Paused) */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Monitoring State
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setStatus("active")}
                className={`py-2 px-3 rounded-xl text-xs font-semibold border transition-all ${
                  status === "active"
                    ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-300 shadow-glow-emerald"
                    : "bg-space-850 border-space-750 text-slate-400 hover:text-slate-200"
                }`}
              >
                Active
              </button>
              <button
                type="button"
                onClick={() => setStatus("paused")}
                className={`py-2 px-3 rounded-xl text-xs font-semibold border transition-all ${
                  status === "paused"
                    ? "bg-slate-500/20 border-slate-500/40 text-slate-200"
                    : "bg-space-850 border-space-750 text-slate-400 hover:text-slate-200"
                }`}
              >
                Paused
              </button>
            </div>
          </div>

          {/* Cadence */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Monitoring Cadence
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: "Every 30m", cadence: "custom", minutes: 30 },
                { label: "Hourly", cadence: "hourly", minutes: 60 },
                { label: "Daily", cadence: "daily", minutes: 1440 },
              ].map((c, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    setCadence(c.cadence);
                    setCadenceMinutes(c.minutes);
                  }}
                  className={`py-2 px-3 rounded-xl text-xs font-semibold border transition-all ${
                    (cadence === c.cadence && (cadence !== "custom" || cadenceMinutes === c.minutes))
                      ? "bg-radar-cyan/15 border-radar-cyan/40 text-radar-cyan shadow-glow"
                      : "bg-space-850 border-space-750 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          {/* Target Price Threshold */}
          {initialThreshold !== "" && (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Target Price Threshold (PKR)
              </label>
              <input
                type="number"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                placeholder="2500"
                className="w-full px-3.5 py-2.5 rounded-xl bg-space-950/80 border border-space-750 text-white text-sm focus:outline-none focus:border-radar-cyan"
              />
            </div>
          )}

          {/* Buttons */}
          <div className="flex items-center justify-between gap-3 pt-4 border-t border-space-750">
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting || saving}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-rose-400 hover:bg-rose-500/10 border border-rose-500/20 hover:border-rose-500/40 transition-colors disabled:opacity-40"
            >
              {deleting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              <span>Delete Watch</span>
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white bg-space-850 hover:bg-space-800 border border-space-750 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="flex items-center gap-1.5 px-5 py-2 rounded-xl bg-radar-cyan text-space-950 font-bold text-xs hover:bg-cyan-300 transition-colors shadow-glow disabled:opacity-50"
              >
                {saving ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Saving...</span>
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4" />
                    <span>Save Changes</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
