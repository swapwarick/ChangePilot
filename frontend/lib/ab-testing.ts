/**
 * ChangePilot A/B Testing Engine
 *
 * Lightweight, localStorage-backed experiment framework.
 * - Deterministic: same user always gets same variant (unless overridden)
 * - Persistent: variant assignment survives page refreshes
 * - Observable: events logged to console + sessionStorage for analysis
 * - Overridable: devtools panel can force any variant
 */

"use client";

import { useState, useEffect } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Experiment<V extends string> {
  /** Unique stable experiment ID, e.g. "header_layout" */
  id: string;
  /** Human-readable name */
  name: string;
  /** Percentage of traffic that sees variant B (0–100) */
  trafficSplit: number;
  /** Variant A is always the control */
  variantA: { label: string; description: string; value: V };
  variantB: { label: string; description: string; value: V };
}

export interface ABEvent {
  experimentId: string;
  variant: string;
  event: string;
  timestamp: number;
  meta?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Storage keys
// ---------------------------------------------------------------------------

const ASSIGNMENT_KEY = "cp_ab_assignments";
const OVERRIDE_KEY = "cp_ab_overrides";
const EVENTS_KEY = "cp_ab_events";

// ---------------------------------------------------------------------------
// Assignment logic
// ---------------------------------------------------------------------------

/** Deterministically derive a 0–99 bucket from the user fingerprint + experimentId */
function getBucket(experimentId: string): number {
  // Use a simple stable fingerprint: first-visit timestamp + experimentId hash
  let seed = localStorage.getItem("cp_visitor_seed");
  if (!seed) {
    seed = Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem("cp_visitor_seed", seed);
  }

  // FNV-1a-like hash of seed + experimentId
  let hash = 2166136261;
  const str = seed + experimentId;
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i);
    hash = (hash * 16777619) >>> 0;
  }
  return hash % 100;
}

function getStoredAssignments(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(ASSIGNMENT_KEY) || "{}");
  } catch {
    return {};
  }
}

function getStoredOverrides(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(OVERRIDE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveAssignments(assignments: Record<string, string>) {
  localStorage.setItem(ASSIGNMENT_KEY, JSON.stringify(assignments));
}

function saveOverrides(overrides: Record<string, string>) {
  localStorage.setItem(OVERRIDE_KEY, JSON.stringify(overrides));
}

/** Assign (or retrieve existing) variant for an experiment. Respects dev overrides. */
export function assignVariant<V extends string>(experiment: Experiment<V>): V {
  const overrides = getStoredOverrides();
  if (overrides[experiment.id]) {
    return overrides[experiment.id] as V;
  }

  const assignments = getStoredAssignments();
  if (assignments[experiment.id]) {
    return assignments[experiment.id] as V;
  }

  // First time: assign deterministically
  const bucket = getBucket(experiment.id);
  const variant =
    bucket < experiment.trafficSplit
      ? experiment.variantB.value
      : experiment.variantA.value;

  assignments[experiment.id] = variant;
  saveAssignments(assignments);
  return variant;
}

/** Force-override variant for a given experiment (devtools use) */
export function overrideVariant(experimentId: string, variant: string) {
  const overrides = getStoredOverrides();
  overrides[experimentId] = variant;
  saveOverrides(overrides);
  // Reload to apply change
  window.location.reload();
}

/** Clear override for a given experiment (revert to assigned) */
export function clearOverride(experimentId: string) {
  const overrides = getStoredOverrides();
  delete overrides[experimentId];
  saveOverrides(overrides);
  window.location.reload();
}

/** Clear ALL assignments and overrides (full reset) */
export function resetAllExperiments() {
  localStorage.removeItem(ASSIGNMENT_KEY);
  localStorage.removeItem(OVERRIDE_KEY);
  window.location.reload();
}

/** Get all current variant assignments (both assigned + overridden) */
export function getAllAssignments(): Record<string, string> {
  const assignments = getStoredAssignments();
  const overrides = getStoredOverrides();
  return { ...assignments, ...overrides };
}

/** Get all stored override keys */
export function getAllOverrides(): Record<string, string> {
  return getStoredOverrides();
}

// ---------------------------------------------------------------------------
// Event tracking
// ---------------------------------------------------------------------------

const MAX_EVENTS = 500;

export function trackABEvent(
  experimentId: string,
  variant: string,
  event: string,
  meta?: Record<string, unknown>
) {
  const ev: ABEvent = { experimentId, variant, event, timestamp: Date.now(), meta };

  // Console log for developer visibility
  console.log(`[A/B] [${experimentId}/${variant}] ${event}`, meta || "");

  // Persist to sessionStorage (in-memory for this session)
  try {
    const raw = sessionStorage.getItem(EVENTS_KEY);
    const events: ABEvent[] = raw ? JSON.parse(raw) : [];
    events.push(ev);
    if (events.length > MAX_EVENTS) events.splice(0, events.length - MAX_EVENTS);
    sessionStorage.setItem(EVENTS_KEY, JSON.stringify(events));
  } catch {
    // ignore storage errors
  }
}

export function getABEvents(): ABEvent[] {
  try {
    const raw = sessionStorage.getItem(EVENTS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// React hook
// ---------------------------------------------------------------------------

/**
 * useABTest — main hook for consuming an experiment variant in a component.
 *
 * @example
 * const { variant, track } = useABTest(EXPERIMENTS.riskDisplay);
 * // variant === "donut" | "progress_bar"
 */
export function useABTest<V extends string>(experiment: Experiment<V>): {
  variant: V;
  isControl: boolean;
  track: (event: string, meta?: Record<string, unknown>) => void;
} {
  const [variant, setVariant] = useState<V>(experiment.variantA.value);

  useEffect(() => {
    // Only runs on client after hydration
    const assigned = assignVariant(experiment);
    setVariant(assigned);
    trackABEvent(experiment.id, assigned, "impression");
  }, [experiment.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const track = (event: string, meta?: Record<string, unknown>) => {
    trackABEvent(experiment.id, variant, event, meta);
  };

  return {
    variant,
    isControl: variant === experiment.variantA.value,
    track,
  };
}
