export type RiskLevel = "low" | "medium" | "high" | "critical";

export type AnalysisSummary = {
  id: string;
  subject: string;
  repository: string;
  trigger: "pull_request" | "release" | "scheduled" | "manual";
  score: number;
  level: RiskLevel;
  topRisk: string;
  status: "completed" | "running" | "failed";
  createdAt: string;
};

export type ProviderStatus = {
  id: string;
  name: string;
  kind: string;
  enabled: boolean;
  default: boolean;
  priority: number;
  model: string;
  status: "healthy" | "degraded" | "offline";
  latencyMs: number;
  successRate: number;
  usageTokens7d: number;
};

export type GraphNode = {
  id: string;
  label: string;
  kind: "service" | "module" | "file" | "api" | "database" | "external";
  risk: number;
  impacted: boolean;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  relationship: "imports" | "calls" | "owns" | "depends_on";
};

