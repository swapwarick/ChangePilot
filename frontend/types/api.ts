export type RiskLevel = "low" | "medium" | "high" | "critical";

export type Repository = {
  id: string;
  name: string;
  url?: string;
  owner?: string;
  default_branch: string;
  language?: string;
  source?: "github" | "local";
  stars?: number;
  open_issues?: number;
  topics?: string[];
  created_at: string;
  updated_at: string;
};

export type RepositorySummary = {
  id: string;
  name: string;
  owner?: string;
  default_branch: string;
  language?: string;
  source?: "github" | "local";
  url?: string;
  created_at?: string;
};

export type GitRepositoryInfo = {
  id?: string;
  name: string;
  full_name: string;
  owner: string;
  default_branch: string;
  language: string;
  private: boolean;
  clone_url: string;
  description?: string;
  stars_count?: number;
};

export type PullRequest = {
  id: string;
  number: number;
  title: string;
  author: string;
  source_branch: string;
  target_branch: string;
  risk_level: RiskLevel;
  risk_score: number;
  files_changed: number;
  impacted_components: number;
  created_at: string;
  is_simulated?: boolean;
};

export type Module = {
  name: string;
  files: number;
  imports: number;
  dependents: number;
  risk_tier: RiskLevel;
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

export type ImpactMetrics = {
  changed_files: number;
  direct_dependents: number;
  transitive_dependents: number;
  unique_affected_components: number;
  total_blast_radius: number;
  dependency_edges: number;
  affected_modules: string[];
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

export type OrphanCandidateDetail = {
  path: string;
  classification: string;
  incoming_imports: number;
  outgoing_imports: number;
  reason: string;
};

export type GraphHealth = {
  node_count: number;
  edge_count: number;
  valid_dependency_edge_count?: number;
  invalid_skipped_edge_count?: number;
  self_edge_count: number;
  duplicate_edge_count: number;
  total_internal_imports_attempted?: number;
  resolved_internal_imports?: number;
  resolution_rate?: number;
  unresolved_imports: number;
  graph_quality_status?: "HEALTHY" | "DEGRADED" | "POOR";
  circular_dependency_count: number;
  orphan_candidates: number;
  total_source_modules?: number;
  orphan_candidate_details?: OrphanCandidateDetail[];
  invalid_paths: number;
  warnings: string[];
};

export type GraphNode = {
  id: string;
  label: string;
  kind: string; // repository, module, folder, file, class, function, api, database, package
  path?: string;
  module?: string;
  language?: string;
  file_classification?: string;
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
  edge_type?: string;
  weight?: number;
};

export type DependencyGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  graph_health?: GraphHealth;
};

export type StatementType = "FACT" | "INFERENCE" | "RECOMMENDATION";
export type RecommendationType = "EVIDENCE_BACKED" | "POLICY_BASED" | "GENERIC_BEST_PRACTICE";

export type EvidenceStatement = {
  id: string;
  statement_type: StatementType;
  claim: string;
  source_evidence?: string;
  recommendation_type?: RecommendationType;
  traceability_ref?: string;
  affected_files?: string[];
};

export type RiskBreakdownItem = {
  rule: string;
  name?: string;
  category: string;
  points: number;
  raw_points?: number;
  evidence: string;
  affected_files: string[];
  threshold?: string;
  observed_value?: string;
  trigger?: string;
  status?: string;
  recommendation: string;
  recommendation_type?: RecommendationType;
};

export type RiskResult = {
  score: number;
  level: RiskLevel;
  confidence: number;
  evidence_completeness?: number;
  is_calibrated?: boolean;
  calibration_status?: string;
  score_description?: string;
  impact_metrics?: ImpactMetrics;
  evidence: RiskEvidence[];
  statements?: EvidenceStatement[];
  facts?: EvidenceStatement[];
  inferences?: EvidenceStatement[];
  recommendations?: EvidenceStatement[];
  potential_failure_scenarios?: string[];
  recommended_review_areas?: Array<{
    review_area: string;
    suggested_reviewer?: string | null;
    evidence?: string;
    ownership_note?: string;
  }>;
  deployment_considerations?: string[];
  reasons: string[];
  risk_breakdown?: RiskBreakdownItem[];
  audit?: Record<string, number>;
};

export type ChangeAnalysisResult = {
  id: string;
  repository_id: string;
  trigger: string;
  changed_files: string[];
  impacted_modules: string[];
  impact_metrics?: ImpactMetrics;
  dependency_graph: DependencyGraph;
  risk: RiskResult;
  ai_report?: string;
  parser_version?: string;
  graph_version?: string;
  risk_engine_version?: string;
  created_at?: string;
};

export type HealthCategoryDetail = {
  category: string;
  score: number | null;
  evidence: string[];
  deductions: number;
  recommendations: string[];
};

export type AnalysisQualityGate = {
  analysis_quality: "FULL" | "DEGRADED" | "FAILED";
  graph_status: "VALID" | "DEGRADED" | "FAILED" | "UNAVAILABLE";
  evidence_completeness: number;
  health_status: "AVAILABLE" | "DEGRADED" | "UNAVAILABLE";
  parser_health: "PASS" | "PARTIAL" | "FAIL" | "UNAVAILABLE" | "N/A";
  diff_status: string;
  inventory_status: string;
  blast_radius_status: string;
  test_analysis_status: string;
  coverage_status: string;
  warnings?: string[];
  explanation?: string;
};

export type RepoHealthMetrics = {
  status?: "AVAILABLE" | "DEGRADED" | "UNAVAILABLE";
  health_score?: number | null;
  total_files: number;
  total_classes?: number;
  total_functions?: number;
  total_dependencies?: number;
  circular_dependencies?: string[][] | null;
  orphan_modules?: string[] | null;
  potential_orphan_candidates?: string[] | null;
  total_source_modules?: number | null;
  orphan_candidate_details?: OrphanCandidateDetail[] | null;
  dead_code_symbols?: string[] | null;
  god_classes?: string[] | null;
  high_fan_out_files?: Array<{ path: string; count: number }>;
  high_fan_in_files?: Array<{ path: string; count: number }>;
  test_coverage_gaps?: string[];
  potential_test_gaps?: string[];
  architectural_violations?: Array<{ rule: string; source: string; target: string }>;
  coverage_notice?: string;
  categories?: Record<string, HealthCategoryDetail>;
  analysis_quality?: "FULL" | "DEGRADED" | "FAILED";
  quality_gate?: AnalysisQualityGate;
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
  api_key?: string;
  model: string;
  enabled: boolean;
  is_default: boolean;
  priority: number;
  task_categories: string[];
  fallback_provider_ids: string[];
  custom_headers: Record<string, string>;
  temperature: number;
  top_p?: number;
  seed?: number;
  max_tokens: number;
  timeout_seconds: number;
};

export type PolicyRuleConfig = {
  signal: string;
  name: string;
  category: "security" | "database" | "architecture" | "testing" | "infrastructure" | "api";
  weight: number;
  threshold?: string;
  enabled: boolean;
  description: string;
  recommendation: string;
  path_markers: string[];
  extensions: string[];
  file_names?: string[];
  custom?: boolean;
};

export type RiskPolicy = {
  id: string;
  name: string;
  version: string;
  description?: string;
  is_active: boolean;
  is_default: boolean;
  rules: PolicyRuleConfig[];
  created_at: string;
  updated_at: string;
};

export type PolicyComparisonResult = {
  policy_a_id: string;
  policy_b_id: string;
  policy_a_name: string;
  policy_b_name: string;
  policy_a_version: string;
  policy_b_version: string;
  score_a: number;
  score_b: number;
  level_a: RiskLevel;
  level_b: RiskLevel;
  delta_score: number;
  divergent_rules: Array<{
    signal: string;
    name: string;
    points_a: number;
    points_b: number;
    diff: number;
  }>;
  weight_changes?: Array<{
    signal: string;
    name?: string;
    old_weight: number;
    new_weight: number;
  }>;
  status_changes?: Array<{
    signal: string;
    name?: string;
    old_enabled: boolean;
    new_enabled: boolean;
  }>;
  added_rules?: Array<{
    signal: string;
    name?: string;
    category: string;
    weight: number;
  }>;
};
