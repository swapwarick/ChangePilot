"use client";

import { useState, useEffect } from "react";
import { FlaskConical, ChevronDown, ChevronUp, RotateCcw, Zap } from "lucide-react";
import {
  overrideVariant,
  clearOverride,
  resetAllExperiments,
  getAllAssignments,
  getAllOverrides,
  getABEvents,
  type ABEvent,
} from "@/lib/ab-testing";
import { ALL_EXPERIMENTS } from "@/lib/ab-experiments";

/**
 * ABDevTools — floating developer panel for inspecting and overriding A/B variants.
 * Only renders in non-production environments (or when ?ab_devtools=1 is in the URL).
 */
export function ABDevTools() {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<"experiments" | "events">("experiments");
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [events, setEvents] = useState<ABEvent[]>([]);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // Show only in dev mode or when ?ab_devtools=1 is in URL
    const isDev = process.env.NODE_ENV === "development";
    const forced = typeof window !== "undefined" &&
      new URLSearchParams(window.location.search).get("ab_devtools") === "1";
    setVisible(isDev || forced);
  }, []);

  useEffect(() => {
    if (!open) return;
    setAssignments(getAllAssignments());
    setOverrides(getAllOverrides());
    setEvents(getABEvents().slice(-30).reverse());
  }, [open]);

  if (!visible) return null;

  return (
    <div className="fixed bottom-4 left-4 z-[9999] flex flex-col items-start">
      {/* Toggle button */}
      <button
        onClick={() => setOpen((v) => !v)}
        title="A/B Testing DevTools"
        className="flex items-center gap-2 rounded-full border border-violet-500/60 bg-violet-950/90 px-3 py-1.5 text-xs font-semibold text-violet-300 shadow-lg backdrop-blur hover:bg-violet-900/90 transition-colors"
      >
        <FlaskConical className="size-3.5" />
        A/B DevTools
        {open ? <ChevronDown className="size-3" /> : <ChevronUp className="size-3" />}
      </button>

      {/* Panel */}
      {open && (
        <div className="mb-2 w-[420px] order-first rounded-xl border border-violet-500/30 bg-[#0f0a1e]/95 text-xs text-violet-100 shadow-2xl backdrop-blur-md">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-violet-500/20 px-4 py-2.5">
            <div className="flex items-center gap-2 font-semibold text-violet-200">
              <FlaskConical className="size-3.5 text-violet-400" />
              A/B Testing DevTools
            </div>
            <button
              onClick={resetAllExperiments}
              title="Reset all assignments and overrides"
              className="flex items-center gap-1 rounded px-2 py-0.5 text-[10px] text-violet-400 hover:bg-violet-500/10 hover:text-violet-200 transition-colors"
            >
              <RotateCcw className="size-3" />
              Reset All
            </button>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-violet-500/20">
            {(["experiments", "events"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 py-1.5 text-[11px] font-medium capitalize transition-colors ${
                  tab === t
                    ? "border-b-2 border-violet-400 text-violet-200"
                    : "text-violet-500 hover:text-violet-300"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Experiments Tab */}
          {tab === "experiments" && (
            <div className="divide-y divide-violet-500/10 max-h-[420px] overflow-y-auto">
              {ALL_EXPERIMENTS.map((exp) => {
                const current = assignments[exp.id] || exp.variantA.value;
                const isOverridden = exp.id in overrides;

                return (
                  <div key={exp.id} className="px-4 py-3 space-y-2">
                    {/* Experiment name + status */}
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-violet-100">{exp.name}</span>
                      <div className="flex items-center gap-2">
                        {isOverridden && (
                          <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[9px] font-bold text-amber-400 uppercase tracking-wide">
                            Overridden
                          </span>
                        )}
                        <span className="text-[10px] text-violet-500">
                          {exp.trafficSplit}% → B
                        </span>
                      </div>
                    </div>

                    {/* Variant selector */}
                    <div className="grid grid-cols-2 gap-1.5">
                      {[exp.variantA, exp.variantB].map((v, i) => {
                        const isActive = current === v.value;
                        return (
                          <button
                            key={v.value}
                            onClick={() => {
                              if (isActive && isOverridden) {
                                clearOverride(exp.id);
                              } else {
                                overrideVariant(exp.id, v.value);
                              }
                            }}
                            className={`rounded-lg border p-2 text-left transition-all ${
                              isActive
                                ? "border-violet-400 bg-violet-500/20 text-violet-100"
                                : "border-violet-500/20 bg-violet-500/5 text-violet-400 hover:border-violet-500/50 hover:text-violet-200"
                            }`}
                          >
                            <div className="flex items-center gap-1.5">
                              <span
                                className={`size-1.5 rounded-full ${
                                  isActive ? "bg-violet-400" : "bg-violet-700"
                                }`}
                              />
                              <span className="text-[10px] font-bold uppercase tracking-wide">
                                {i === 0 ? "A · Control" : "B · Variant"}
                              </span>
                            </div>
                            <div className="mt-1 text-[10px] leading-snug opacity-80">
                              {v.label.split(": ")[1] || v.label}
                            </div>
                          </button>
                        );
                      })}
                    </div>

                    {/* Current value */}
                    <div className="flex items-center gap-1.5 text-[10px] text-violet-500">
                      <Zap className="size-2.5" />
                      Active:
                      <code className="rounded bg-violet-500/10 px-1 text-violet-300">
                        {current}
                      </code>
                      {isOverridden && (
                        <button
                          onClick={() => clearOverride(exp.id)}
                          className="ml-auto text-amber-400 hover:text-amber-200"
                        >
                          Clear override
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Events Tab */}
          {tab === "events" && (
            <div className="max-h-[420px] overflow-y-auto px-3 py-2 space-y-1">
              {events.length === 0 ? (
                <div className="py-6 text-center text-violet-500">No events tracked yet</div>
              ) : (
                events.map((ev, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 rounded-md px-2 py-1.5 hover:bg-violet-500/5"
                  >
                    <span className="shrink-0 rounded bg-violet-500/15 px-1.5 text-[9px] font-bold uppercase tracking-wide text-violet-400">
                      {ev.event}
                    </span>
                    <div className="min-w-0 flex-1">
                      <span className="font-mono text-violet-200">{ev.experimentId}</span>
                      <span className="mx-1 text-violet-600">/</span>
                      <span className="font-mono text-violet-400">{ev.variant}</span>
                    </div>
                    <span className="shrink-0 text-[9px] text-violet-600">
                      {new Date(ev.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}

          {/* Footer hint */}
          <div className="border-t border-violet-500/20 px-4 py-2 text-[10px] text-violet-600">
            Click a variant to override · Reload auto-applies · Add <code>?ab_devtools=1</code> to show in prod
          </div>
        </div>
      )}
    </div>
  );
}
