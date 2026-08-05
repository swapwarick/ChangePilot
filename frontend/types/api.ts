export type RiskLevel = "low" | "medium" | "high" | "critical";

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
  description: string;
  weight: number;
  score: number;
  file_paths: string[];
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
  kind: string;
  path?: string;
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
  total_files: number;
  circular_dependencies: string[][];
  orphan_modules: string[];
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
