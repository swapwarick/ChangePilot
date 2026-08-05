import type { AnalysisSummary, GraphEdge, GraphNode, ProviderStatus } from "@/types/api";

export const analyses: AnalysisSummary[] = [
  {
    id: "PR-524",
    subject: "Add caching to user service",
    repository: "user-service",
    trigger: "pull_request",
    score: 0.72,
    level: "high",
    topRisk: "Data consistency",
    status: "completed",
    createdAt: "5m ago"
  },
  {
    id: "REL-214",
    subject: "main -> v2.14.0",
    repository: "platform-api",
    trigger: "release",
    score: 0.35,
    level: "medium",
    topRisk: "Performance",
    status: "completed",
    createdAt: "22m ago"
  },
  {
    id: "PR-511",
    subject: "Update payment gateway",
    repository: "payment-service",
    trigger: "pull_request",
    score: 0.81,
    level: "critical",
    topRisk: "External dependency",
    status: "completed",
    createdAt: "1h ago"
  },
  {
    id: "PR-509",
    subject: "Refactor auth middleware",
    repository: "auth-service",
    trigger: "pull_request",
    score: 0.28,
    level: "low",
    topRisk: "Low test coverage",
    status: "completed",
    createdAt: "2h ago"
  }
];

export const providers: ProviderStatus[] = [
  {
    id: "openai-prod",
    name: "OpenAI",
    kind: "openai_compatible",
    enabled: true,
    default: true,
    priority: 1,
    model: "gpt-4o",
    status: "healthy",
    latencyMs: 812,
    successRate: 99.2,
    usageTokens7d: 12_400_000
  },
  {
    id: "anthropic-primary",
    name: "Anthropic",
    kind: "custom_rest",
    enabled: true,
    default: false,
    priority: 2,
    model: "claude-3-5-sonnet",
    status: "healthy",
    latencyMs: 766,
    successRate: 98.7,
    usageTokens7d: 8_700_000
  },
  {
    id: "local-ollama",
    name: "Local Ollama",
    kind: "ollama",
    enabled: true,
    default: false,
    priority: 3,
    model: "llama3.1",
    status: "healthy",
    latencyMs: 412,
    successRate: 99.6,
    usageTokens7d: 1_300_000
  }
];

export const graphNodes: GraphNode[] = [
  { id: "web", label: "web-frontend", kind: "service", risk: 0.22, impacted: true },
  { id: "api", label: "api-gateway", kind: "api", risk: 0.31, impacted: true },
  { id: "user", label: "user-service", kind: "service", risk: 0.72, impacted: true },
  { id: "auth", label: "auth-service", kind: "service", risk: 0.28, impacted: true },
  { id: "account", label: "account-service", kind: "service", risk: 0.36, impacted: true },
  { id: "userdb", label: "user-db", kind: "database", risk: 0.91, impacted: true },
  { id: "redis", label: "redis-cache", kind: "external", risk: 0.12, impacted: false },
  { id: "notify", label: "notification-svc", kind: "service", risk: 0.44, impacted: true },
  { id: "mail", label: "sendgrid-api", kind: "external", risk: 0.2, impacted: false }
];

export const graphEdges: GraphEdge[] = [
  { id: "e1", source: "web", target: "api", relationship: "calls" },
  { id: "e2", source: "web", target: "user", relationship: "calls" },
  { id: "e3", source: "web", target: "notify", relationship: "calls" },
  { id: "e4", source: "api", target: "auth", relationship: "depends_on" },
  { id: "e5", source: "api", target: "account", relationship: "depends_on" },
  { id: "e6", source: "user", target: "userdb", relationship: "depends_on" },
  { id: "e7", source: "user", target: "redis", relationship: "depends_on" },
  { id: "e8", source: "notify", target: "mail", relationship: "depends_on" }
];

