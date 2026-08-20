/**
 * ChangePilot A/B Experiment Definitions
 *
 * All active experiments are declared here.
 * Each experiment has:
 *  - A stable id (never change once launched)
 *  - A trafficSplit: % of users seeing variant B
 *  - variantA: control (existing UI)
 *  - variantB: challenger (new UI)
 */

import type { Experiment } from "./ab-testing";

// ---------------------------------------------------------------------------
// Experiment 1: Dashboard Header Layout
// ---------------------------------------------------------------------------
// Control A: Compact top-bar with sidebar icon-only nav on mobile
// Variant B: Full sidebar always visible with section labels

export type HeaderLayoutVariant = "compact_topbar" | "full_sidebar";

export const EXPERIMENT_HEADER_LAYOUT: Experiment<HeaderLayoutVariant> = {
  id: "header_layout",
  name: "Dashboard Header Layout",
  trafficSplit: 50,
  variantA: {
    label: "Control: Compact Topbar",
    description: "Current layout — sidebar collapses on smaller screens, topbar stays compact.",
    value: "compact_topbar",
  },
  variantB: {
    label: "Variant B: Full Sidebar",
    description: "Sidebar always expanded with section labels and repo picker prominently visible.",
    value: "full_sidebar",
  },
};

// ---------------------------------------------------------------------------
// Experiment 2: Risk Score Display
// ---------------------------------------------------------------------------
// Control A: Donut chart (current conic-gradient circle)
// Variant B: Horizontal progress bar with segmented color blocks

export type RiskDisplayVariant = "donut" | "progress_bar";

export const EXPERIMENT_RISK_DISPLAY: Experiment<RiskDisplayVariant> = {
  id: "risk_display",
  name: "Risk Score Display",
  trafficSplit: 50,
  variantA: {
    label: "Control: Donut Chart",
    description: "Conic-gradient circle ring with score centered inside.",
    value: "donut",
  },
  variantB: {
    label: "Variant B: Progress Bar",
    description: "Segmented horizontal bar (low → critical) with numeric score callout.",
    value: "progress_bar",
  },
};

// ---------------------------------------------------------------------------
// Experiment 3: Recent Analysis Runs Display
// ---------------------------------------------------------------------------
// Control A: Compact table (current)
// Variant B: Card grid with risk badge, score indicator, and one-click export

export type AnalysisDisplayVariant = "table" | "card_grid";

export const EXPERIMENT_ANALYSIS_DISPLAY: Experiment<AnalysisDisplayVariant> = {
  id: "analysis_display",
  name: "Recent Analysis Runs Display",
  trafficSplit: 50,
  variantA: {
    label: "Control: Compact Table",
    description: "Dense table with columns for ID, trigger, score, level, modules, and export.",
    value: "table",
  },
  variantB: {
    label: "Variant B: Card Grid",
    description: "Expanded cards with risk gauge, module tags, and prominent export button.",
    value: "card_grid",
  },
};

// ---------------------------------------------------------------------------
// Experiment 4: Onboarding CTA
// ---------------------------------------------------------------------------
// Control A: Current "Scan Repository / Local Folder" button in topbar
// Variant B: Hero-style prominent CTA banner when no analyses exist

export type OnboardingCTAVariant = "button" | "hero_banner";

export const EXPERIMENT_ONBOARDING_CTA: Experiment<OnboardingCTAVariant> = {
  id: "onboarding_cta",
  name: "Onboarding Call to Action",
  trafficSplit: 50,
  variantA: {
    label: "Control: Topbar Button",
    description: "\"Scan Repository\" button in the top navigation bar.",
    value: "button",
  },
  variantB: {
    label: "Variant B: Hero Banner",
    description: "Large gradient hero banner with description, icons, and a prominent CTA when no analyses exist.",
    value: "hero_banner",
  },
};

// ---------------------------------------------------------------------------
// All experiments registry (for devtools)
// ---------------------------------------------------------------------------

export const ALL_EXPERIMENTS = [
  EXPERIMENT_HEADER_LAYOUT,
  EXPERIMENT_RISK_DISPLAY,
  EXPERIMENT_ANALYSIS_DISPLAY,
  EXPERIMENT_ONBOARDING_CTA,
] as const;
