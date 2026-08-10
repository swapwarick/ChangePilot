export type RiskLevel = "low" | "medium" | "high" | "critical";

export type PolicyRuleConfig = {
  signal: string;
  name: string;
  category: string;
  description: string;
  weight: number;
  enabled: boolean;
  threshold?: string;
  recommendation?: string;
  path_markers?: string[];
  extensions?: string[];
  custom?: boolean;
};

export type RiskPolicy = {
  id: string;
  name: string;
  organization_id: string;
  version: string;
  description: string;
  is_active: boolean;
  rules: PolicyRuleConfig[];
  created_at?: string;
  updated_at?: string;
};

export type PolicyComparisonResult = {
  policy_a_version: string;
  policy_b_version: string;
  weight_changes: Array<{ signal: string; name: string; old_weight: number; new_weight: number }>;
  status_changes: Array<{ signal: string; name: string; old_enabled: boolean; new_enabled: boolean }>;
  added_rules: Array<{ signal: string; name: string; weight: number }>;
  removed_rules: Array<{ signal: string; name: string; weight: number }>;
};

export type GitRepositoryInfo = {
  id: string;
  name: string;
  full_name: string;
  owner: string;
  private: boolean;
  html_url: string;
  clone_url: string;
  default_branch: string;
  description?: string;
  language?: string;
  updated_at?: string;
};

export type GitBranchInfo = {
  name: string;
  commit_sha: string;
  is_default: boolean;
};

export type GitCommitInfo = {
  sha: string;
  short_sha: string;
  message: string;
  author_name: string;
  author_email: string;
  committed_date: string;
};

export type AnalysisJobStatus = {
  id: string;
  repository_id: string;
  status: "PENDING" | "CLONING" | "PARSING" | "BUILDING_GRAPH" | "SCORING" | "COMPLETED" | "FAILED";
  step: string;
  progress: number;
  error?: string;
  analysis_id?: string;
};

export type RiskEvidence = {
  signal: string;
  name?: string;
  category?: string;
  description: string;
  weight: number;
  score: number;
  file_paths: string[];
  recommendation?: string;
  enabled?: boolean;
  threshold?: string;
};

export type RiskResult = {
  score: number;
  level: RiskLevel;
  confidence: number;
  evidence: RiskEvidence[];
  reasons: string[];
};

export type GraphNode = {
  id: string;
  label: string;
  kind: string; // repository, module, folder, file, class, function, api, database, package
  path?: string;
  module?: string;
  language?: string;
  fan_in?: number;
  fan_out?: number;
  blast_radius?: number;
  is_critical?: boolean;
  metadata?: Record<string, string>;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  relationship: string;
};

export type DependencyGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type ChangeAnalysisResult = {
  id: string;
  repository_id: string;
  trigger: string;
  changed_files: string[];
  impacted_modules: string[];
  dependency_graph: DependencyGraph;
  risk: RiskResult;
  ai_report?: string;
  parser_version?: string;
  graph_version?: string;
  risk_engine_version?: string;
  created_at?: string;
};

export type RepoHealthMetrics = {
  health_score?: number;
  total_files: number;
  total_classes?: number;
  total_functions?: number;
  total_dependencies?: number;
  circular_dependencies: string[][];
  orphan_modules: string[];
  dead_code_symbols?: string[];
  god_classes?: string[];
  high_fan_out_files?: Array<{ path: string; count: number }>;
  high_fan_in_files?: Array<{ path: string; count: number }>;
  test_coverage_gaps: string[];
  architectural_violations: Array<{ rule: string; source: string; target: string }>;
};

export type RepoKnowledgeGraph = {
  id: string;
  repository_id: string;
  commit_sha: string;
  graph_hash: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  health_metrics: RepoHealthMetrics;
  created_at: string;
};

export type AIProviderConfig = {
  id: string;
  name: string;
  kind: string;
  base_url?: string;
  model: string;
  enabled: boolean;
  is_default: boolean;
  priority: number;
  task_categories: string[];
  fallback_provider_ids: string[];
  custom_headers: Record<string, string>;
  temperature: number;
  max_tokens: number;
  timeout_seconds: number;
};
