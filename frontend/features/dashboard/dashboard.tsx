"use client";

import { useState, useEffect, useMemo } from "react";
import {
  Activity,
  Bell,
  Boxes,
  CircleHelp,
  GitPullRequest,
  LayoutDashboard,
  Network,
  Plus,
  RefreshCcw,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  Github,
  AlertTriangle,
  FileCode,
  FolderCode,
  Layers,
  CheckCircle2,
  AlertCircle,
  Sliders,
  Shield,
  FileText,
  Cpu,
  ArrowUpRight,
  Copy,
  Check,
  GitCommit,
  GitBranch,
  Play,
  Download,
  Upload,
  GitCompare,
  Trash2,
  Save,
  ShieldAlert,
  X
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Switch } from "@/components/ui/switch";
import dynamic from "next/dynamic";

const DependencyGraph = dynamic(
  () => import("./dependency-graph").then((m) => ({ default: m.DependencyGraph })),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[520px] items-center justify-center rounded-xl border border-border/80 bg-muted/20 text-xs text-muted-foreground">
        Loading graph…
      </div>
    ),
  }
);
import { RepoAnalyzerModal } from "@/features/github/repo-analyzer-modal";
import { JobProgressBanner } from "@/features/analysis/job-progress-banner";
import { AIProviderSettings } from "@/features/providers/provider-settings";
import { UserMenu } from "@/components/user-menu";
import { AIProviderConfig, ChangeAnalysisResult, PolicyComparisonResult, PolicyRuleConfig, RepoKnowledgeGraph, RiskPolicy } from "@/types/api";
import { getApiBaseUrl } from "@/lib/api-config";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard },
  { label: "Analyses", icon: Activity },
  { label: "Pull Requests", icon: GitPullRequest },
  { label: "Services", icon: Boxes },
  { label: "Dependencies", icon: Network },
  { label: "Risk Policies", icon: ShieldCheck },
  { label: "AI Insights", icon: Sparkles },
  { label: "Settings", icon: Settings }
];

function levelVariant(level: string) {
  if (level === "critical") return "destructive";
  if (level === "high") return "warning";
  if (level === "medium") return "warning";
  return "success";
}

function Donut({ score = 0 }: { score?: number }) {
  const normScore = score > 1 ? score / 100 : score;
  const displayVal = score > 1 ? Math.round(score) : Math.round(score * 100);
  const degrees = Math.round(normScore * 360);
  return (
    <div
      className="grid size-32 place-items-center rounded-full"
      style={{
        background: `conic-gradient(hsl(var(--destructive)) 0 ${degrees * 0.28}deg, #f97316 ${degrees * 0.28}deg ${degrees * 0.65}deg, hsl(var(--warning)) ${degrees * 0.65}deg ${degrees}deg, hsl(var(--muted)) ${degrees}deg 360deg)`
      }}
    >
      <div className="grid size-24 place-items-center rounded-full bg-surface text-center">
        <div>
          <div className="text-2xl font-semibold">{displayVal}/100</div>
          <div className="text-[11px] text-muted-foreground">Risk score</div>
        </div>
      </div>
    </div>
  );
}

export function Dashboard() {
  const [activeTab, setActiveTab] = useState<string>("Dashboard");
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeRepoId, setActiveRepoId] = useState<string | null>(null);
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<string | null>(null);
  const [repositories, setRepositories] = useState<any[]>([]);
  const [providers, setProviders] = useState<AIProviderConfig[]>([]);
  const [analyses, setAnalyses] = useState<ChangeAnalysisResult[]>([]);
  const [knowledgeGraph, setKnowledgeGraph] = useState<RepoKnowledgeGraph | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const [pullRequests, setPullRequests] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [repoLoading, setRepoLoading] = useState(false);
  const [simBaseBranch, setSimBaseBranch] = useState("main");
  const [simHeadBranch, setSimHeadBranch] = useState("main");
  const [simulatingPr, setSimulatingPr] = useState(false);
  const [simulateError, setSimulateError] = useState<string | null>(null);

  // Enterprise Risk Policy Engine State
  const [allPolicies, setAllPolicies] = useState<RiskPolicy[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState<RiskPolicy | null>(null);
  const [editingRules, setEditingRules] = useState<PolicyRuleConfig[]>([]);
  const [policyCategoryFilter, setPolicyCategoryFilter] = useState("all");
  const [policySearchQuery, setPolicySearchQuery] = useState("");
  const [policySaving, setPolicySaving] = useState(false);
  const [policyMessage, setPolicyMessage] = useState<string | null>(null);

  // Custom Rule Modal State
  const [isAddRuleOpen, setIsAddRuleOpen] = useState(false);
  const [newRuleName, setNewRuleName] = useState("");
  const [newRuleSignal, setNewRuleSignal] = useState("");
  const [newRuleCategory, setNewRuleCategory] = useState("security");
  const [newRuleDesc, setNewRuleDesc] = useState("");
  const [newRuleWeight, setNewRuleWeight] = useState(0.20);
  const [newRuleMarkers, setNewRuleMarkers] = useState("");
  const [newRuleExts, setNewRuleExts] = useState("");
  const [newRuleRec, setNewRuleRec] = useState("");

  // Policy Comparison Modal State
  const [isCompareOpen, setIsCompareOpen] = useState(false);
  const [comparePolicyAId, setComparePolicyAId] = useState<string>("");
  const [comparePolicyBId, setComparePolicyBId] = useState<string>("");
  const [comparisonData, setComparisonData] = useState<PolicyComparisonResult | null>(null);

  const fetchPolicies = async () => {
    try {
      const res = await fetch(`${getApiBaseUrl()}/risk-policies`);
      if (res.ok) {
        const list: RiskPolicy[] = await res.json();
        setAllPolicies(list);
        if (list.length > 0) {
          const active = list.find((p) => p.is_active) || list[0];
          if (!selectedPolicy) {
            setSelectedPolicy(active);
            setEditingRules(active.rules);
          }
        }
      }
    } catch (err) {
      console.warn("Fetch policies notice:", err);
    }
  };

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const repoRes = await fetch(`${getApiBaseUrl()}/repositories`);
      if (repoRes.ok) {
        const repoData = await repoRes.json();
        setRepositories(repoData);
        if (repoData.length > 0 && !activeRepoId) {
          setActiveRepoId(repoData[0].id);
        }
      }

      const provRes = await fetch(`${getApiBaseUrl()}/ai-providers`);
      if (provRes.ok) {
        setProviders(await provRes.json());
      }

      await fetchPolicies();
    } catch (err: any) {
      console.warn("Dashboard fetch notice:", err?.message || err);
    } finally {
      setLoading(false);
    }
  };

  const fetchRepoData = async (repoId: string, repoList: any[] = repositories, silent = false) => {
    if (!silent) {
      // 1. Immediately flush all stale state to prevent cross-repo contamination
      setAnalyses([]);
      setKnowledgeGraph(null);
      setPullRequests([]);
      setBranches([]);
      setSelectedAnalysisId(null);
      setRepoLoading(true);
    }

    try {
      // 2. Fetch Analyses for active repository only
      const anlRes = await fetch(`${getApiBaseUrl()}/analysis?repository_id=${repoId}`);
      if (anlRes.ok) {
        setAnalyses(await anlRes.json());
      }

      // 3. Fetch Knowledge Graph for active repository only
      const kgRes = await fetch(`${getApiBaseUrl()}/jobs/repositories/${repoId}/knowledge-graph`);
      if (kgRes.ok) {
        setKnowledgeGraph(await kgRes.json());
      }

      // 4. Fetch PRs and Branches based on repository type (GitHub vs Local)
      const repoObj = repoList.find((r) => r.id === repoId);
      if (repoObj) {
        if (repoObj.source === "local" || repoObj.owner === "local" || !repoObj.owner) {
          try {
            const localPath = repoObj.url || repoObj.name;
            const infoRes = await fetch(`${getApiBaseUrl()}/local/info?path=${encodeURIComponent(localPath)}`);
            if (infoRes.ok) {
              const info = await infoRes.json();
              if (info.branches && info.branches.length > 0) {
                setBranches(info.branches);
              }
            }
          } catch (localErr) {}
        } else if (repoObj.source === "github" && repoObj.owner) {
          try {
            const token = localStorage.getItem("github_token") || localStorage.getItem("changepilot_github_token") || "";
            if (token) {
              const headers: Record<string, string> = { Authorization: token };
              const prRes = await fetch(`${getApiBaseUrl()}/github/repositories/${repoObj.owner}/${repoObj.name}/pulls`, { headers });
              if (prRes.ok) setPullRequests(await prRes.json());

              const brRes = await fetch(`${getApiBaseUrl()}/github/repositories/${repoObj.owner}/${repoObj.name}/branches`, { headers });
              if (brRes.ok) setBranches(await brRes.json());
            }
          } catch (gitErr) {}
        }
      }
    } catch (err: any) {
      console.warn("Repo fetch notice:", err?.message || err);
    } finally {
      if (!silent) {
        setRepoLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  useEffect(() => {
    if (activeRepoId) {
      fetchRepoData(activeRepoId, repositories);
    }
  }, [activeRepoId]);

  const latestAnalysis = (selectedAnalysisId && analyses.find((a) => a.id === selectedAnalysisId)) || (analyses.length > 0 ? analyses[0] : null);
  const healthMetrics = knowledgeGraph?.health_metrics;

  const discoveredModules = useMemo(() => {
    const nodes = knowledgeGraph?.nodes || latestAnalysis?.dependency_graph?.nodes || [];
    const modMap = new Map<string, { name: string; files: number; imports: number; kind: string }>();
    nodes.forEach((n) => {
      const modName = n.module || (n.path && n.path.includes("/") ? n.path.split("/")[0] : "root");
      const existing = modMap.get(modName) || { name: modName, files: 0, imports: 0, kind: n.kind };
      existing.files += 1;
      existing.imports += (n.fan_out || 0);
      modMap.set(modName, existing);
    });
    return Array.from(modMap.values());
  }, [knowledgeGraph, latestAnalysis]);

  const handleSimulatePr = async () => {
    if (!activeRepoId) return;
    const repoObj = repositories.find((r) => r.id === activeRepoId);
    if (!repoObj) return;

    setSimulatingPr(true);
    setSimulateError(null);
    try {
      const token = localStorage.getItem("github_token") || "";
      const repoUrl = repoObj.url || (repoObj.source === "local" ? repoObj.name : `https://github.com/${repoObj.owner || "local"}/${repoObj.name}`);
      const ownerName = repoObj.owner || (repoObj.source === "local" ? "local" : "github");

      const res = await fetch(`${getApiBaseUrl()}/jobs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: token
        },
        body: JSON.stringify({
          repository_url: repoUrl,
          owner: ownerName,
          repo_name: repoObj.name,
          base_ref: simBaseBranch || "main",
          head_ref: simHeadBranch || "HEAD"
        })
      });

      if (res.ok) {
        const job = await res.json();
        setActiveJobId(job.id);
      } else {
        const errData = await res.json().catch(() => ({ detail: null }));
        setSimulateError(errData.detail || "PR Simulation job creation failed. Please check repository & branch references.");
      }
    } catch (err: any) {
      setSimulateError(`PR Simulation error: ${err?.message || err}`);
    } finally {
      setSimulatingPr(false);
    }
  };

  const handleSelectPolicy = (polId: string) => {
    const target = allPolicies.find((p) => p.id === polId);
    if (target) {
      setSelectedPolicy(target);
      setEditingRules([...target.rules]);
    }
  };

  const handleSaveCurrentPolicy = async () => {
    if (!selectedPolicy) return;
    setPolicySaving(true);
    try {
      const updatedPolicy: RiskPolicy = {
        ...selectedPolicy,
        rules: editingRules
      };
      const res = await fetch(`${getApiBaseUrl()}/risk-policies/${selectedPolicy.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updatedPolicy)
      });

      if (res.ok) {
        const saved = await res.json();
        setSelectedPolicy(saved);
        setPolicyMessage("Policy rules saved successfully!");
        setTimeout(() => setPolicyMessage(null), 3000);
        await fetchPolicies();
      }
    } catch (err) {
      console.error("Save policy error:", err);
    } finally {
      setPolicySaving(false);
    }
  };

  const handleActivateCurrentPolicy = async () => {
    if (!selectedPolicy) return;
    try {
      const res = await fetch(`${getApiBaseUrl()}/risk-policies/${selectedPolicy.id}/activate`, {
        method: "PUT"
      });
      if (res.ok) {
        const activated = await res.json();
        setSelectedPolicy(activated);
        setPolicyMessage(`Policy "${activated.name}" (${activated.version}) is now active!`);
        setTimeout(() => setPolicyMessage(null), 3000);
        await fetchPolicies();
      }
    } catch (err) {
      console.error("Activate policy error:", err);
    }
  };

  const handleCloneNewVersion = async () => {
    if (!selectedPolicy) return;
    try {
      const parts = selectedPolicy.version.split(".");
      const major = parseInt(parts[0] || "1");
      const minor = parseInt(parts[1] || "0") + 1;
      const newVer = `${major}.${minor}.0`;

      const res = await fetch(`${getApiBaseUrl()}/risk-policies`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: `${selectedPolicy.name} (${newVer})`,
          version: newVer,
          description: `Cloned version from ${selectedPolicy.version}`,
          clone_from_id: selectedPolicy.id
        })
      });

      if (res.ok) {
        const cloned: RiskPolicy = await res.json();
        await fetchPolicies();
        setSelectedPolicy(cloned);
        setEditingRules(cloned.rules);
        setPolicyMessage(`Created new policy version ${newVer}!`);
        setTimeout(() => setPolicyMessage(null), 3000);
      }
    } catch (err) {
      console.error("Clone version error:", err);
    }
  };

  const handleAddCustomRuleSubmit = () => {
    if (!newRuleName || !newRuleSignal) return;

    const customRule: PolicyRuleConfig = {
      signal: newRuleSignal.trim().toLowerCase().replace(/\s+/g, "_"),
      name: newRuleName.trim(),
      category: newRuleCategory,
      description: newRuleDesc || "Custom organization risk rule.",
      weight: parseFloat(newRuleWeight.toString()) || 0.20,
      enabled: true,
      threshold: "1 file",
      recommendation: newRuleRec || "Verify custom compliance requirements.",
      path_markers: newRuleMarkers ? newRuleMarkers.split(",").map((s) => s.trim()).filter(Boolean) : [],
      extensions: newRuleExts ? newRuleExts.split(",").map((s) => s.trim()).filter(Boolean) : [],
      custom: true
    };

    setEditingRules([customRule, ...editingRules]);
    setIsAddRuleOpen(false);
    setNewRuleName("");
    setNewRuleSignal("");
    setNewRuleDesc("");
    setNewRuleMarkers("");
    setNewRuleExts("");
    setNewRuleRec("");
  };

  const handleExportPolicyJson = () => {
    if (!selectedPolicy) return;
    const policyToExport = { ...selectedPolicy, rules: editingRules };
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(policyToExport, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `risk-policy-${selectedPolicy.version}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleImportPolicyJson = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileReader = new FileReader();
    if (e.target.files && e.target.files[0]) {
      fileReader.readAsText(e.target.files[0], "UTF-8");
      fileReader.onload = async (event) => {
        try {
          const parsed = JSON.parse(event.target?.result as string);
          const res = await fetch(`${getApiBaseUrl()}/risk-policies/import`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(parsed)
          });
          if (res.ok) {
            const imported: RiskPolicy = await res.json();
            await fetchPolicies();
            setSelectedPolicy(imported);
            setEditingRules(imported.rules);
            setPolicyMessage(`Successfully imported policy "${imported.name}"!`);
            setTimeout(() => setPolicyMessage(null), 3000);
          }
        } catch (err) {
          alert("Invalid Risk Policy JSON format");
        }
      };
    }
  };

  const handleCompareSubmit = async () => {
    if (!comparePolicyAId || !comparePolicyBId) return;
    try {
      const res = await fetch(`${getApiBaseUrl()}/risk-policies/compare?policy_a=${comparePolicyAId}&policy_b=${comparePolicyBId}`);
      if (res.ok) {
        setComparisonData(await res.json());
      }
    } catch (err) {
      console.error("Compare policies error:", err);
    }
  };

  useEffect(() => {
    // Only poll silently if there's an active job running that might produce/update an AI report
    if (latestAnalysis && !latestAnalysis.ai_report && activeJobId) {
      const interval = setInterval(() => {
        if (activeRepoId) fetchRepoData(activeRepoId, repositories, true);
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [latestAnalysis?.id, latestAnalysis?.ai_report, activeRepoId, activeJobId]);

  const handleCopyReport = () => {
    if (latestAnalysis?.ai_report) {
      navigator.clipboard.writeText(latestAnalysis.ai_report);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <main className="flex min-h-screen flex-col text-sm lg:grid lg:grid-cols-[210px_1fr]">
      {/* Sidebar Navigation */}
      <aside className="hidden min-h-screen flex-col border-r border-border bg-surface/88 lg:flex">
        <div className="flex h-16 items-center gap-3 border-b border-border px-5">
          <div className="grid size-8 place-items-center rounded-md bg-primary text-primary-foreground">
            <Network data-icon="inline-start" />
          </div>
          <div className="text-lg font-semibold">ChangePilot</div>
        </div>

        <nav className="flex flex-1 flex-col gap-1 p-3">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.label;
            return (
              <button
                key={item.label}
                onClick={() => setActiveTab(item.label)}
                className={`flex items-center gap-3 rounded-md px-3 py-2 text-left font-medium transition-colors ${
                  isActive
                    ? "bg-primary/10 text-primary font-semibold"
                    : "text-muted-foreground hover:bg-surface-elevated hover:text-foreground"
                }`}
              >
                <Icon className="size-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="border-t border-border p-4">
          <div className="text-xs uppercase text-muted-foreground">Active Repository</div>
          <select
            value={activeRepoId || ""}
            onChange={(e) => setActiveRepoId(e.target.value)}
            className="mt-2 flex h-9 w-full items-center justify-between rounded-md border border-border bg-background px-3 text-left text-sm"
          >
            {repositories.length === 0 ? (
              <option value="">No repositories connected</option>
            ) : (
              repositories.map((repo) => (
                <option key={repo.id} value={repo.id}>{repo.name}</option>
              ))
            )}
          </select>
        </div>
      </aside>

      {/* Main Content Area */}
      <section className="min-w-0">
        <header className="flex min-h-16 flex-col items-stretch justify-between gap-3 border-b border-border bg-surface/80 px-4 py-3 backdrop-blur sm:flex-row sm:items-center sm:px-5">
          <div className="flex h-10 w-full items-center gap-2 rounded-md border border-border bg-background px-3 text-muted-foreground sm:max-w-[520px]">
            <Search className="size-4" />
            <span className="text-sm">Search services, repositories, analyses...</span>
            <kbd className="ml-auto rounded-sm border border-border px-1.5 py-0.5 text-xs">⌘ K</kbd>
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button onClick={() => setIsModalOpen(true)} className="flex items-center gap-2 bg-gradient-to-r from-emerald-600 to-indigo-600 hover:from-emerald-700 hover:to-indigo-700 text-white shadow-xs">
              <FolderCode className="size-4" />
              Scan Repository / Local Folder
            </Button>
            <Button aria-label="Notifications" size="icon" variant="ghost">
              <Bell className="size-4" />
            </Button>
            <Button aria-label="Help" size="icon" variant="ghost">
              <CircleHelp className="size-4" />
            </Button>
            <UserMenu />
          </div>
        </header>

        <div className="p-5">
          {activeJobId && (
            <JobProgressBanner
              jobId={activeJobId}
              onJobComplete={(anlId) => {
                if (activeRepoId) fetchRepoData(activeRepoId, repositories, true);
              }}
            />
          )}

          {repoLoading && (
            <div className="mb-4 flex items-center gap-3 rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-3.5 text-xs text-indigo-700 dark:text-indigo-300 animate-pulse">
              <RefreshCcw className="size-4 animate-spin shrink-0 text-indigo-500" />
              <span>Switching workspace context... Loading knowledge graph & analysis for <strong className="text-foreground">{activeRepoId}</strong></span>
            </div>
          )}

          {/* TAB 1: DASHBOARD */}
          {activeTab === "Dashboard" && (
            <div className="space-y-4">
              <div className="flex flex-col items-start justify-between gap-3 xl:flex-row">
                <div>
                  <h1 className="text-2xl font-semibold">Repository Knowledge Graph</h1>
                  <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
                    Real code analysis, AST dependency graphing, deterministic risk scoring, and repo health metrics.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                  <RefreshCcw className="size-4 cursor-pointer hover:text-foreground" onClick={fetchDashboardData} />
                  <Button variant="outline" size="sm" onClick={() => setIsModalOpen(true)}>
                    <Plus className="size-4 mr-1" /> New Analysis Job
                  </Button>
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
                <Card className="xl:col-span-2">
                  <CardHeader>
                    <div>
                      <CardTitle>Deterministic Risk & Repository Health</CardTitle>
                      <CardDescription>
                        {activeRepoId ? `Repository ${activeRepoId} persistent analysis` : "Connect a repository to analyze"}
                      </CardDescription>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid gap-4 lg:grid-cols-[420px_repeat(4,1fr)]">
                      <div className="flex items-center gap-8">
                        <Donut score={latestAnalysis?.risk.score || 0} />
                        <div className="flex flex-col gap-3">
                          <div className="flex items-center gap-3">
                            <span className="size-2.5 rounded-full bg-primary" />
                            <span className="min-w-28 text-muted-foreground">Risk Level</span>
                            {latestAnalysis ? (
                              <Badge variant={levelVariant(latestAnalysis.risk.level || "low")}>
                                {latestAnalysis.risk.level?.toUpperCase() || "LOW"}
                              </Badge>
                            ) : (
                              <Badge variant="outline">UNSCANNED</Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="size-2.5 rounded-full bg-warning" />
                            <span className="min-w-28 text-muted-foreground">Confidence</span>
                            <span className="font-semibold">
                              {latestAnalysis ? `${((latestAnalysis.risk.confidence || 0) * 100).toFixed(0)}%` : "--"}
                            </span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="size-2.5 rounded-full bg-emerald-500" />
                            <span className="min-w-28 text-muted-foreground">Health Score</span>
                            <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                              {healthMetrics?.health_score !== undefined ? `${healthMetrics.health_score} / 100` : "N/A"}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Widget 1: Health Score & Parsed Metrics */}
                      <div className="rounded-md border border-border bg-background p-4">
                        <div className="text-xs text-muted-foreground">Repository Health</div>
                        <div className="mt-2 text-3xl font-bold text-emerald-600 dark:text-emerald-400">
                          {healthMetrics?.health_score !== undefined ? `${healthMetrics.health_score}%` : "N/A"}
                        </div>
                        <div className="mt-1 text-[11px] text-muted-foreground">
                          {healthMetrics ? `${healthMetrics.total_files || 0} files • ${healthMetrics.total_classes || 0} classes • ${healthMetrics.total_functions || 0} fns` : "No repository scanned"}
                        </div>
                        <div className="mt-4 h-2 rounded-full bg-muted overflow-hidden">
                          <div
                            className="h-full bg-emerald-500 transition-all duration-500"
                            style={{ width: `${healthMetrics?.health_score !== undefined ? healthMetrics.health_score : 0}%` }}
                          />
                        </div>
                      </div>

                      {/* Widget 2: Circular Dependencies */}
                      <div className="rounded-md border border-border bg-background p-4">
                        <div className="text-xs text-muted-foreground">Circular Dependencies</div>
                        <div className="mt-2 text-2xl font-semibold text-amber-600 dark:text-amber-400">
                          {healthMetrics ? healthMetrics.circular_dependencies.length : "--"}
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">Cycle import loops detected</div>
                        <div className="mt-4 text-[10px] text-muted-foreground truncate">
                          {healthMetrics
                            ? healthMetrics.circular_dependencies.length
                              ? `Loop: ${healthMetrics.circular_dependencies[0].join(" ➔ ")}`
                              : "No circular import loops"
                            : "Connect a repository"}
                        </div>
                      </div>

                      {/* Widget 3: Potential Test Gaps */}
                      <div className="rounded-md border border-border bg-background p-4">
                        <div className="text-xs text-muted-foreground">Potential Test Gaps</div>
                        <div className="mt-2 text-2xl font-semibold text-rose-600 dark:text-rose-400">
                          {healthMetrics ? (healthMetrics.potential_test_gaps?.length ?? healthMetrics.test_coverage_gaps?.length ?? 0) : "--"}
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">Source modules lacking tests</div>
                        <div className="mt-4 text-[10px] text-muted-foreground truncate">
                          {healthMetrics
                            ? (healthMetrics.potential_test_gaps || healthMetrics.test_coverage_gaps || []).length
                              ? `Gap: ${(healthMetrics.potential_test_gaps || healthMetrics.test_coverage_gaps || [])[0]}`
                              : "No test gaps detected"
                            : "Connect a repository"}
                        </div>
                      </div>

                      {/* Widget 4: Architectural Violations */}
                      <div className="rounded-md border border-border bg-background p-4">
                        <div className="text-xs text-muted-foreground">Layering Violations</div>
                        <div className="mt-2 text-2xl font-semibold text-indigo-600 dark:text-indigo-400">
                          {healthMetrics ? healthMetrics.architectural_violations.length : "--"}
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">Cross-layer policy breaches</div>
                        <div className="mt-4 text-[10px] text-muted-foreground truncate">
                          {healthMetrics
                            ? healthMetrics.architectural_violations.length
                              ? healthMetrics.architectural_violations[0].rule
                              : "No policy violations"
                            : "Connect a repository"}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Additional Enterprise Analytics Widgets */}
                {healthMetrics && (
                  <div className="xl:col-span-2 grid gap-4 lg:grid-cols-3">
                    {/* Widget 5: Highest Fan-Out Files (High Coupling) */}
                    <Card>
                      <CardHeader className="py-3">
                        <CardTitle className="text-sm">Highest Fan-Out Files (Tight Coupling)</CardTitle>
                      </CardHeader>
                      <CardContent className="py-2">
                        {healthMetrics.high_fan_out_files && healthMetrics.high_fan_out_files.length > 0 ? (
                          <div className="space-y-2">
                            {healthMetrics.high_fan_out_files.slice(0, 5).map((f, idx) => (
                              <div key={idx} className="flex items-center justify-between text-xs font-mono p-1.5 rounded border bg-muted/20">
                                <span className="truncate max-w-[200px]" title={f.path}>{f.path}</span>
                                <Badge variant="secondary">{f.count} imports</Badge>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="py-4 text-center text-xs text-muted-foreground">No high fan-out files detected.</div>
                        )}
                      </CardContent>
                    </Card>

                    {/* Widget 6: Most Imported Files (Highest Fan-In / Centrality) */}
                    <Card>
                      <CardHeader className="py-3">
                        <CardTitle className="text-sm">Most Imported Files (High Centrality)</CardTitle>
                      </CardHeader>
                      <CardContent className="py-2">
                        {healthMetrics.high_fan_in_files && healthMetrics.high_fan_in_files.length > 0 ? (
                          <div className="space-y-2">
                            {healthMetrics.high_fan_in_files.slice(0, 5).map((f, idx) => (
                              <div key={idx} className="flex items-center justify-between text-xs font-mono p-1.5 rounded border bg-muted/20">
                                <span className="truncate max-w-[200px]" title={f.path}>{f.path}</span>
                                <Badge variant="outline">{f.count} dependents</Badge>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="py-4 text-center text-xs text-muted-foreground">No high fan-in files detected.</div>
                        )}
                      </CardContent>
                    </Card>

                    {/* Widget 7: God Classes & Dead Code Candidates */}
                    <Card>
                      <CardHeader className="py-3">
                        <CardTitle className="text-sm">God Classes & Unused Exports</CardTitle>
                      </CardHeader>
                      <CardContent className="py-2">
                        <div className="space-y-2 text-xs">
                          <div>
                            <span className="font-medium text-muted-foreground">God Classes ({healthMetrics.god_classes?.length || 0}):</span>
                            <div className="font-mono text-[11px] truncate text-amber-600 mt-0.5">
                              {healthMetrics.god_classes?.[0] || "None detected"}
                            </div>
                          </div>
                          <div>
                            <span className="font-medium text-muted-foreground">Dead Code Candidates ({healthMetrics.dead_code_symbols?.length || 0}):</span>
                            <div className="font-mono text-[11px] truncate text-muted-foreground mt-0.5">
                              {healthMetrics.dead_code_symbols?.[0] || "None detected"}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                <Card>
                  <CardHeader>
                    <CardTitle>Recent Repository Analyses</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {analyses.length === 0 ? (
                      <div className="py-8 text-center text-xs text-muted-foreground">
                        No analyses performed yet. Click <strong>Connect & Analyze Repo</strong> to analyze a repository.
                      </div>
                    ) : (
                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Commit SHA</TableHead>
                              <TableHead>Risk Score</TableHead>
                              <TableHead>Level</TableHead>
                              <TableHead>Impacted Modules</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {analyses.map((anl) => (
                              <TableRow
                                key={anl.id}
                                onClick={() => setSelectedAnalysisId(anl.id)}
                                className={`cursor-pointer transition-colors ${
                                  latestAnalysis?.id === anl.id ? "bg-muted/80 font-medium" : "hover:bg-muted/40"
                                }`}
                              >
                                <TableCell className="font-mono text-xs font-medium">{anl.id}</TableCell>
                                <TableCell className="font-semibold">{anl.risk.score.toFixed(2)}</TableCell>
                                <TableCell>
                                  <Badge variant={levelVariant(anl.risk.level)}>{anl.risk.level}</Badge>
                                </TableCell>
                                <TableCell className="text-xs text-muted-foreground">
                                  {anl.impacted_modules.join(", ") || "Root"}
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card className="xl:col-span-2">
                  <CardHeader>
                    <div>
                      <CardTitle>Knowledge Graph Structure</CardTitle>
                      <CardDescription>Visual AST graph parsed from Tree-Sitter & Neo4j engine.</CardDescription>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <DependencyGraph
                      nodes={knowledgeGraph?.nodes || latestAnalysis?.dependency_graph?.nodes || []}
                      edges={knowledgeGraph?.edges || latestAnalysis?.dependency_graph?.edges || []}
                      graphHealth={latestAnalysis?.dependency_graph?.graph_health}
                    />
                  </CardContent>
                </Card>

                <Card className="xl:col-span-2">
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle>AI Report & Evidence Breakdown</CardTitle>
                      <CardDescription>Asynchronously generated AI summary grounded in real AST signals.</CardDescription>
                    </div>
                    {latestAnalysis?.ai_report && (
                      <Button variant="outline" size="sm" onClick={handleCopyReport} className="flex items-center gap-1.5">
                        {copied ? <Check className="size-3.5 text-emerald-500" /> : <Copy className="size-3.5" />}
                        {copied ? "Copied" : "Copy Report"}
                      </Button>
                    )}
                  </CardHeader>
                  <CardContent>
                    {latestAnalysis ? (
                      <div className="space-y-4">
                        <div className="rounded-md border border-border bg-muted/20 p-4 text-xs whitespace-pre-wrap font-mono">
                          {latestAnalysis.ai_report || "AI report is generating in background..."}
                        </div>

                        <div className="mt-4">
                          <h4 className="text-sm font-semibold mb-2">Deterministic Evidence Rules Triggered</h4>
                          <div className="space-y-2">
                            {latestAnalysis.risk.evidence.map((ev, idx) => (
                              <div key={idx} className="flex items-center justify-between rounded-md border border-border bg-background p-3 text-xs">
                                <div>
                                  <span className="font-semibold text-primary">{ev.signal}</span>
                                  <p className="text-muted-foreground mt-0.5">{ev.description}</p>
                                </div>
                                <Badge variant="outline">Weight: {ev.weight}</Badge>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="py-8 text-center text-xs text-muted-foreground">
                        Connect and run analysis to view AI reports and deterministic evidence breakdown.
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {/* TAB 2: ANALYSES */}
          {activeTab === "Analyses" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-semibold">Repository Analysis History</h1>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Historical AST analysis runs, risk evaluations, and file diff inspection for {activeRepoId || "active repository"}.
                  </p>
                </div>
                <Button variant="outline" size="sm" onClick={() => setIsModalOpen(true)}>
                  <Plus className="size-4 mr-1" /> New Analysis Job
                </Button>
              </div>

              <div className="grid gap-4 lg:grid-cols-3">
                <Card className="lg:col-span-1">
                  <CardHeader>
                    <CardTitle>Analysis Runs</CardTitle>
                    <CardDescription>Select a run to inspect changed files & evidence.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {analyses.length === 0 ? (
                      <div className="py-8 text-center text-xs text-muted-foreground">No analysis runs recorded yet.</div>
                    ) : (
                      analyses.map((anl) => (
                        <div
                          key={anl.id}
                          onClick={() => setSelectedAnalysisId(anl.id)}
                          className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors ${
                            latestAnalysis?.id === anl.id ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40"
                          }`}
                        >
                          <div>
                            <div className="font-mono text-xs font-semibold text-foreground flex items-center gap-2">
                              <GitCommit className="size-3.5 text-primary" /> {anl.id}
                            </div>
                            <div className="text-[11px] text-muted-foreground mt-1">
                              {anl.changed_files.length} files changed · {anl.impacted_modules.join(", ") || "Root"}
                            </div>
                          </div>
                          <Badge variant={levelVariant(anl.risk.level)}>{anl.risk.score.toFixed(2)}</Badge>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>

                <Card className="lg:col-span-2">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle>Analysis Run Detail ({latestAnalysis?.id || "None"})</CardTitle>
                        <CardDescription>Changed files, evidence rules, and AI summary breakdown.</CardDescription>
                      </div>
                      {latestAnalysis && (
                        <Badge variant={levelVariant(latestAnalysis.risk.level)}>
                          Risk: {latestAnalysis.risk.level.toUpperCase()} ({latestAnalysis.risk.score.toFixed(2)})
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    {latestAnalysis ? (
                      <div className="space-y-6">
                        <div>
                          <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-2">Changed Files in Commit Set ({latestAnalysis.changed_files.length})</h4>
                          <div className="max-h-48 overflow-y-auto space-y-1 rounded-md border border-border bg-background p-2">
                            {latestAnalysis.changed_files.map((file, idx) => (
                              <div key={idx} className="flex items-center gap-2 text-xs font-mono p-1 hover:bg-muted/50 rounded">
                                <FileCode className="size-3.5 text-primary shrink-0" />
                                <span className="truncate">{file}</span>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div>
                          <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-2">Deterministic Signals Triggered</h4>
                          <div className="space-y-2">
                            {latestAnalysis.risk.evidence.map((ev, idx) => (
                              <div key={idx} className="rounded-md border border-border bg-background p-3 text-xs flex items-start justify-between">
                                <div>
                                  <div className="font-semibold text-primary">{ev.signal}</div>
                                  <div className="text-muted-foreground mt-0.5">{ev.description}</div>
                                </div>
                                <Badge variant="outline">Weight: {ev.weight}</Badge>
                              </div>
                            ))}
                          </div>
                        </div>

                        <div>
                          <h4 className="text-xs font-semibold uppercase text-muted-foreground mb-2">AI Explanation Report</h4>
                          <div className="rounded-md border border-border bg-muted/20 p-4 text-xs whitespace-pre-wrap font-mono">
                            {latestAnalysis.ai_report || "No AI report available for this run."}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="py-12 text-center text-xs text-muted-foreground">Select an analysis run from the left panel to inspect details.</div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {/* TAB 3: PULL REQUESTS */}
          {activeTab === "Pull Requests" && (
            <div className="space-y-4">
              <div>
                <h1 className="text-2xl font-semibold">Pull Request Risk & Change Impact Gates</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Automated risk gate evaluation for open pull requests and proposed feature branch merges.
                </p>
              </div>

              <div className="grid gap-4 lg:grid-cols-3">
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <CardTitle>Active Pull Request Risk Checks</CardTitle>
                    <CardDescription>Continuous integration risk status grounded in AST dependency graphs.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {pullRequests.length === 0 ? (
                        <div className="py-8 text-center text-xs text-muted-foreground">
                          No pull requests found for {activeRepoId || "this repository"}. Connect a GitHub token or submit a new analysis job.
                        </div>
                      ) : (
                        pullRequests.map((pr) => (
                          <div key={pr.id || pr.number} className="rounded-lg border border-border bg-background p-4 flex items-center justify-between gap-4">
                            <div className="flex items-start gap-3">
                              <div className="grid size-9 place-items-center rounded-md bg-primary/10 text-primary shrink-0 mt-0.5">
                                <GitPullRequest className="size-4" />
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <span className="font-semibold text-foreground">#{pr.number} {pr.title}</span>
                                  <Badge variant={pr.state === "open" ? "success" : "secondary"}>{pr.state?.toUpperCase()}</Badge>
                                </div>
                                <div className="text-xs text-muted-foreground mt-1 flex items-center gap-3">
                                  <span>Head: <code className="text-primary">{pr.head_ref || "branch"}</code></span>
                                  <span>Base: <code className="text-muted-foreground">{pr.base_ref || "main"}</code></span>
                                  <span>Author: {pr.user}</span>
                                </div>
                              </div>
                            </div>

                            <div className="text-right shrink-0">
                              <a href={pr.html_url} target="_blank" rel="noreferrer" className="text-xs text-primary underline">
                                View on GitHub
                              </a>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Simulate Branch Risk Gate</CardTitle>
                    <CardDescription>Test change impact before opening a PR.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div>
                      <label className="text-xs font-medium text-muted-foreground">Base Branch</label>
                      <select
                        value={simBaseBranch}
                        onChange={(e) => setSimBaseBranch(e.target.value)}
                        className="mt-1 flex h-9 w-full rounded-md border border-border bg-background px-3 text-xs outline-none"
                      >
                        {branches.length === 0 ? (
                          <option value="main">main</option>
                        ) : (
                          branches.map((b) => (
                            <option key={b.name} value={b.name}>
                              {b.name} {b.is_default ? "(default)" : ""}
                            </option>
                          ))
                        )}
                      </select>
                    </div>

                    <div>
                      <label className="text-xs font-medium text-muted-foreground">Target / Head Branch</label>
                      <select
                        value={simHeadBranch}
                        onChange={(e) => setSimHeadBranch(e.target.value)}
                        className="mt-1 flex h-9 w-full rounded-md border border-border bg-background px-3 text-xs outline-none"
                      >
                        {branches.length === 0 ? (
                          <option value="feature">feature branch</option>
                        ) : (
                          branches.map((b) => (
                            <option key={b.name} value={b.name}>
                              {b.name}
                            </option>
                          ))
                        )}
                      </select>
                    </div>

                    <Button
                      onClick={handleSimulatePr}
                      disabled={simulatingPr}
                      className="w-full flex items-center justify-center gap-2 mt-4"
                      size="sm"
                    >
                      {simulatingPr ? (
                        <RefreshCcw className="size-3.5 animate-spin" />
                      ) : (
                        <Play className="size-3.5" />
                      )}
                      {simulatingPr ? "Simulating PR Blast Radius..." : "Simulate PR Blast Radius"}
                    </Button>
                    {simulateError && (
                      <div className="mt-2 rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive flex items-center gap-2">
                        <ShieldAlert className="size-3.5 shrink-0" />
                        <span>{simulateError}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {/* TAB 4: SERVICES */}
          {activeTab === "Services" && (
            <div className="space-y-4">
              <div>
                <h1 className="text-2xl font-semibold">Architectural Services & Module Inventory</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Discovered module boundaries, API endpoints, and architectural isolation metrics for {activeRepoId || "active repository"}.
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {discoveredModules.length === 0 ? (
                  <div className="md:col-span-2 lg:col-span-3 py-12 text-center text-xs text-muted-foreground">
                    No module inventory discovered yet for active repository. Run an analysis job to parse AST boundaries.
                  </div>
                ) : (
                  discoveredModules.map((mod) => (
                    <Card key={mod.name}>
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between">
                          <div className="grid size-9 place-items-center rounded-md bg-primary/10 text-primary">
                            <Boxes className="size-4" />
                          </div>
                          <Badge variant={mod.imports > 15 ? "warning" : "secondary"}>
                            {mod.kind?.toUpperCase() || "MODULE"}
                          </Badge>
                        </div>
                        <CardTitle className="mt-3 text-base font-mono truncate" title={mod.name}>{mod.name}</CardTitle>
                        <CardDescription>AST parsed architecture boundary</CardDescription>
                      </CardHeader>
                      <CardContent className="text-xs space-y-2 border-t border-border pt-3">
                        <div className="flex justify-between text-muted-foreground">
                          <span>AST Files:</span>
                          <span className="font-semibold text-foreground">{mod.files}</span>
                        </div>
                        <div className="flex justify-between text-muted-foreground">
                          <span>Outbound Fan-Out:</span>
                          <span className="font-semibold text-foreground">{mod.imports}</span>
                        </div>
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </div>
          )}

          {/* TAB 5: DEPENDENCIES */}
          {activeTab === "Dependencies" && (
            <div className="space-y-4">
              <div>
                <h1 className="text-2xl font-semibold">Dependency Matrix & Graph Inspector</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Complete internal AST import curves, external package dependencies, circular imports, and orphan modules.
                </p>
              </div>

              <div className="grid gap-4 lg:grid-cols-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs uppercase text-muted-foreground">AST Graph Nodes</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{healthMetrics?.total_files || 129}</div>
                    <div className="text-xs text-muted-foreground mt-1">Parsed code files</div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs uppercase text-muted-foreground">Circular Imports</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-emerald-500">{healthMetrics?.circular_dependencies.length || 0}</div>
                    <div className="text-xs text-muted-foreground mt-1">Cycle import loops</div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs uppercase text-muted-foreground">Potential Orphan Candidates</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-warning">
                      {healthMetrics?.potential_orphan_candidates?.length ?? healthMetrics?.orphan_modules?.length ?? 0}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">Unreferenced source files</div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs uppercase text-muted-foreground">Potential Test Gaps</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-warning">
                      {healthMetrics?.potential_test_gaps?.length ?? healthMetrics?.test_coverage_gaps?.length ?? 0}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">Missing unit test specs</div>
                  </CardContent>
                </Card>
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Potential Orphan Candidates (Unreferenced Source Files)</CardTitle>
                    <CardDescription>Source files that are not imported by any other module in the codebase.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="max-h-64 overflow-y-auto space-y-1 text-xs font-mono">
                      {(healthMetrics?.potential_orphan_candidates || healthMetrics?.orphan_modules || []).map((item, idx) => (
                        <div key={idx} className="p-2 rounded border border-border bg-background flex items-center justify-between">
                          <span className="truncate">{item}</span>
                          <Badge variant="outline">Orphan</Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Potential Test Gaps</CardTitle>
                    <CardDescription>Source modules lacking associated unit test specs.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="max-h-64 overflow-y-auto space-y-1 text-xs font-mono">
                      {(healthMetrics?.potential_test_gaps || healthMetrics?.test_coverage_gaps || []).map((item, idx) => (
                        <div key={idx} className="p-2 rounded border border-border bg-background flex items-center justify-between">
                          <span className="truncate">{item}</span>
                          <Badge variant="warning">Potential Gap</Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {/* TAB 6: RISK POLICIES */}
          {activeTab === "Risk Policies" && (
            <div className="space-y-4">
              {/* Header Title & Actions */}
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h1 className="text-2xl font-semibold flex items-center gap-2">
                    <ShieldCheck className="size-6 text-indigo-500" />
                    Enterprise Risk Policy Management
                  </h1>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Configure scoring weights, customize enterprise security signals, version policies, and compare rule diffs.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {/* Policy Version Selector */}
                  {allPolicies.length > 0 && selectedPolicy && (
                    <select
                      value={selectedPolicy.id}
                      onChange={(e) => handleSelectPolicy(e.target.value)}
                      className="h-9 rounded-md border border-border bg-background px-3 text-xs font-semibold outline-none"
                    >
                      {allPolicies.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.version}) {p.is_active ? "★ ACTIVE" : ""}
                        </option>
                      ))}
                    </select>
                  )}

                  {selectedPolicy && !selectedPolicy.is_active && (
                    <Button size="sm" variant="outline" onClick={handleActivateCurrentPolicy} className="text-xs">
                      Set Active
                    </Button>
                  )}

                  <Button size="sm" variant="outline" onClick={handleCloneNewVersion} className="flex items-center gap-1.5 text-xs">
                    <Layers className="size-3.5 text-purple-500" /> Clone Version
                  </Button>

                  <Button size="sm" variant="outline" onClick={() => setIsAddRuleOpen(true)} className="flex items-center gap-1.5 text-xs">
                    <Plus className="size-3.5 text-emerald-500" /> Custom Rule
                  </Button>

                  <Button size="sm" variant="outline" onClick={() => setIsCompareOpen(true)} className="flex items-center gap-1.5 text-xs">
                    <GitCompare className="size-3.5 text-blue-500" /> Compare
                  </Button>

                  <Button size="sm" variant="outline" onClick={handleExportPolicyJson} className="flex items-center gap-1.5 text-xs">
                    <Download className="size-3.5" /> Export
                  </Button>

                  <label className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-background text-xs font-medium cursor-pointer hover:bg-muted transition-colors">
                    <Upload className="size-3.5 text-indigo-500" /> Import
                    <input type="file" accept=".json" onChange={handleImportPolicyJson} className="hidden" />
                  </label>

                  <Button size="sm" onClick={handleSaveCurrentPolicy} disabled={policySaving} className="flex items-center gap-1.5 text-xs">
                    <Save className="size-3.5" /> {policySaving ? "Saving..." : "Save Policy"}
                  </Button>
                </div>
              </div>

              {/* Status Message Notification */}
              {policyMessage && (
                <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-700 dark:text-emerald-300 animate-in fade-in duration-200">
                  <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
                  <span>{policyMessage}</span>
                </div>
              )}

              {/* Active Policy Status Bar */}
              {selectedPolicy && (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/80 bg-muted/40 p-4">
                  <div className="flex items-center gap-3">
                    <div className="grid size-10 place-items-center rounded-lg bg-indigo-500/10 text-indigo-500">
                      <Shield className="size-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-foreground text-sm">{selectedPolicy.name}</span>
                        <Badge variant={selectedPolicy.is_active ? "success" : "secondary"}>
                          {selectedPolicy.is_active ? "ACTIVE ENGINE POLICY" : "DRAFT VERSION"}
                        </Badge>
                        <span className="font-mono text-xs text-muted-foreground">v{selectedPolicy.version}</span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">{selectedPolicy.description}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-xs font-mono text-muted-foreground">
                    <span>Total Rules: <strong className="text-foreground">{editingRules.length}</strong></span>
                    <span>Active Rules: <strong className="text-emerald-600">{editingRules.filter((r) => r.enabled).length}</strong></span>
                  </div>
                </div>
              )}

              {/* Filter Controls & Search */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  {["all", "security", "database", "api", "infrastructure", "architecture", "testing"].map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setPolicyCategoryFilter(cat)}
                      className={`px-3 py-1 rounded-md text-xs font-medium capitalize transition-all ${
                        policyCategoryFilter === cat
                          ? "bg-primary text-primary-foreground shadow-xs font-semibold"
                          : "bg-muted/70 text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs shadow-2xs">
                  <Search className="size-3.5 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Search policy rules..."
                    value={policySearchQuery}
                    onChange={(e) => setPolicySearchQuery(e.target.value)}
                    className="bg-transparent outline-none w-44 text-xs placeholder:text-muted-foreground"
                  />
                </div>
              </div>

              {/* Editable Rules Table */}
              <Card>
                <CardHeader className="py-4">
                  <CardTitle className="text-sm">Configurable Static Analysis Rules ({editingRules.length})</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="divide-y divide-border">
                    {editingRules
                      .filter((r) => {
                        if (policyCategoryFilter !== "all" && r.category.toLowerCase() !== policyCategoryFilter.toLowerCase()) return false;
                        if (policySearchQuery.trim()) {
                          const q = policySearchQuery.toLowerCase();
                          return r.name.toLowerCase().includes(q) || r.signal.toLowerCase().includes(q) || r.description.toLowerCase().includes(q);
                        }
                        return true;
                      })
                      .map((rule, idx) => (
                        <div key={rule.signal} className={`p-4 flex flex-col md:flex-row md:items-center justify-between gap-4 transition-colors ${!rule.enabled ? "opacity-50 bg-muted/20" : "hover:bg-muted/30"}`}>
                          <div className="flex items-start gap-3 min-w-0 flex-1">
                            <div className="grid size-9 place-items-center rounded-md bg-muted text-muted-foreground shrink-0 mt-0.5">
                              <Shield className="size-4 text-indigo-500" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-semibold text-foreground text-sm">{rule.name}</span>
                                <Badge variant="outline" className="uppercase text-[9px]">{rule.category}</Badge>
                                {rule.custom && <Badge variant="warning" className="text-[9px]">CUSTOM</Badge>}
                              </div>
                              <p className="text-xs text-muted-foreground mt-0.5">{rule.description}</p>

                              {(rule.path_markers?.length || rule.extensions?.length) ? (
                                <div className="flex items-center gap-2 mt-1.5 text-[10px] font-mono text-muted-foreground">
                                  {rule.path_markers && rule.path_markers.length > 0 && (
                                    <span>Paths: <code className="text-primary">{rule.path_markers.join(", ")}</code></span>
                                  )}
                                  {rule.extensions && rule.extensions.length > 0 && (
                                    <span>Exts: <code className="text-purple-500">{rule.extensions.join(", ")}</code></span>
                                  )}
                                </div>
                              ) : null}
                            </div>
                          </div>

                          <div className="flex items-center gap-6 shrink-0">
                            {/* Interactive Weight Slider & Numeric Input */}
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground w-12 text-right">Weight:</span>
                              <input
                                type="range"
                                min="0.01"
                                max="0.50"
                                step="0.01"
                                value={rule.weight}
                                onChange={(e) => {
                                  const val = parseFloat(e.target.value);
                                  const updated = [...editingRules];
                                  const targetIdx = updated.findIndex((r) => r.signal === rule.signal);
                                  if (targetIdx !== -1) {
                                    updated[targetIdx].weight = val;
                                    setEditingRules(updated);
                                  }
                                }}
                                className="w-24 accent-primary cursor-pointer"
                              />
                              <input
                                type="number"
                                step="0.01"
                                min="0.00"
                                max="1.00"
                                value={rule.weight}
                                onChange={(e) => {
                                  const val = parseFloat(e.target.value) || 0;
                                  const updated = [...editingRules];
                                  const targetIdx = updated.findIndex((r) => r.signal === rule.signal);
                                  if (targetIdx !== -1) {
                                    updated[targetIdx].weight = val;
                                    setEditingRules(updated);
                                  }
                                }}
                                className="w-16 h-8 rounded border border-border bg-background px-2 text-xs font-mono font-bold text-center"
                              />
                            </div>

                            {/* Enable Toggle Switch */}
                            <Switch
                              checked={rule.enabled}
                              onCheckedChange={(checked) => {
                                const updated = [...editingRules];
                                const targetIdx = updated.findIndex((r) => r.signal === rule.signal);
                                if (targetIdx !== -1) {
                                  updated[targetIdx].enabled = checked;
                                  setEditingRules(updated);
                                }
                              }}
                            />

                            {/* Remove button for custom rules */}
                            {rule.custom && (
                              <button
                                onClick={() => {
                                  setEditingRules(editingRules.filter((r) => r.signal !== rule.signal));
                                }}
                                className="text-muted-foreground hover:text-red-500 transition-colors p-1"
                                title="Remove custom rule"
                              >
                                <Trash2 className="size-4" />
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                  </div>
                </CardContent>
              </Card>

              {/* MODAL 1: ADD CUSTOM ENTERPRISE RULE */}
              {isAddRuleOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
                  <div className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-2xl space-y-4">
                    <div className="flex items-center justify-between border-b pb-3">
                      <h3 className="text-base font-semibold">Add Custom Enterprise Risk Rule</h3>
                      <button onClick={() => setIsAddRuleOpen(false)}><X className="size-4" /></button>
                    </div>

                    <div className="space-y-3 text-xs">
                      <div>
                        <label className="font-medium text-muted-foreground">Rule Name</label>
                        <input
                          type="text"
                          placeholder="e.g. Sensitive Payment Gateway Mutation"
                          value={newRuleName}
                          onChange={(e) => {
                            setNewRuleName(e.target.value);
                            setNewRuleSignal(e.target.value.toLowerCase().replace(/[^a-z0-9]/g, "_"));
                          }}
                          className="mt-1 flex h-9 w-full rounded border border-border bg-background px-3 text-xs"
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="font-medium text-muted-foreground">Signal Code</label>
                          <input
                            type="text"
                            placeholder="payment_gateway_change"
                            value={newRuleSignal}
                            onChange={(e) => setNewRuleSignal(e.target.value)}
                            className="mt-1 flex h-9 w-full rounded border border-border bg-background px-3 text-xs font-mono"
                          />
                        </div>
                        <div>
                          <label className="font-medium text-muted-foreground">Category</label>
                          <select
                            value={newRuleCategory}
                            onChange={(e) => setNewRuleCategory(e.target.value)}
                            className="mt-1 flex h-9 w-full rounded border border-border bg-background px-3 text-xs"
                          >
                            <option value="security">Security</option>
                            <option value="database">Database</option>
                            <option value="api">API</option>
                            <option value="infrastructure">Infrastructure</option>
                            <option value="architecture">Architecture</option>
                            <option value="testing">Testing</option>
                          </select>
                        </div>
                      </div>

                      <div>
                        <label className="font-medium text-muted-foreground">Description</label>
                        <textarea
                          placeholder="Explain what risk signal this rule detects..."
                          value={newRuleDesc}
                          onChange={(e) => setNewRuleDesc(e.target.value)}
                          className="mt-1 flex h-16 w-full rounded border border-border bg-background p-2 text-xs"
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="font-medium text-muted-foreground">Path Markers (comma separated)</label>
                          <input
                            type="text"
                            placeholder="payment/, stripe/, checkout"
                            value={newRuleMarkers}
                            onChange={(e) => setNewRuleMarkers(e.target.value)}
                            className="mt-1 flex h-9 w-full rounded border border-border bg-background px-3 text-xs font-mono"
                          />
                        </div>
                        <div>
                          <label className="font-medium text-muted-foreground">File Extensions (comma separated)</label>
                          <input
                            type="text"
                            placeholder=".sql, .env, .stripe.ts"
                            value={newRuleExts}
                            onChange={(e) => setNewRuleExts(e.target.value)}
                            className="mt-1 flex h-9 w-full rounded border border-border bg-background px-3 text-xs font-mono"
                          />
                        </div>
                      </div>

                      <div>
                        <label className="font-medium text-muted-foreground">Scoring Weight (0.01 - 0.50)</label>
                        <input
                          type="number"
                          step="0.01"
                          min="0.01"
                          max="0.50"
                          value={newRuleWeight}
                          onChange={(e) => setNewRuleWeight(parseFloat(e.target.value) || 0.20)}
                          className="mt-1 flex h-9 w-full rounded border border-border bg-background px-3 text-xs font-mono"
                        />
                      </div>

                      <div>
                        <label className="font-medium text-muted-foreground">Actionable Recommendation</label>
                        <input
                          type="text"
                          placeholder="e.g. Require senior security architect approval."
                          value={newRuleRec}
                          onChange={(e) => setNewRuleRec(e.target.value)}
                          className="mt-1 flex h-9 w-full rounded border border-border bg-background px-3 text-xs"
                        />
                      </div>
                    </div>

                    <div className="flex items-center justify-end gap-2 border-t pt-3">
                      <Button variant="outline" size="sm" onClick={() => setIsAddRuleOpen(false)}>Cancel</Button>
                      <Button size="sm" onClick={handleAddCustomRuleSubmit}>Add Rule</Button>
                    </div>
                  </div>
                </div>
              )}

              {/* MODAL 2: COMPARE POLICY VERSIONS */}
              {isCompareOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
                  <div className="w-full max-w-2xl rounded-xl border border-border bg-card p-6 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
                    <div className="flex items-center justify-between border-b pb-3">
                      <h3 className="text-base font-semibold flex items-center gap-2">
                        <GitCompare className="size-4 text-blue-500" />
                        Compare Policy Versions Side-by-Side
                      </h3>
                      <button onClick={() => setIsCompareOpen(false)}><X className="size-4" /></button>
                    </div>

                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <label className="font-medium text-muted-foreground">Baseline Policy Version (A)</label>
                        <select
                          value={comparePolicyAId}
                          onChange={(e) => setComparePolicyAId(e.target.value)}
                          className="mt-1 flex h-9 w-full rounded border border-border bg-background px-3 text-xs"
                        >
                          <option value="">Select Version A...</option>
                          {allPolicies.map((p) => (
                            <option key={p.id} value={p.id}>{p.name} ({p.version})</option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="font-medium text-muted-foreground">Target Policy Version (B)</label>
                        <select
                          value={comparePolicyBId}
                          onChange={(e) => setComparePolicyBId(e.target.value)}
                          className="mt-1 flex h-9 w-full rounded border border-border bg-background px-3 text-xs"
                        >
                          <option value="">Select Version B...</option>
                          {allPolicies.map((p) => (
                            <option key={p.id} value={p.id}>{p.name} ({p.version})</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <Button size="sm" onClick={handleCompareSubmit} className="w-full text-xs">
                      Run Version Diff Comparison
                    </Button>

                    {comparisonData && (
                      <div className="space-y-4 pt-3 border-t">
                        <div className="flex items-center justify-between text-xs font-semibold">
                          <span>Comparing {comparisonData.policy_a_version} ➔ {comparisonData.policy_b_version}</span>
                        </div>

                        {/* Weight Changes */}
                        {comparisonData.weight_changes.length > 0 && (
                          <div>
                            <h4 className="text-xs font-semibold text-amber-600 mb-1">⚖️ Rule Weight Changes ({comparisonData.weight_changes.length})</h4>
                            <div className="space-y-1 text-xs">
                              {comparisonData.weight_changes.map((wc) => (
                                <div key={wc.signal} className="p-2 rounded border bg-muted/20 flex justify-between font-mono">
                                  <span>{wc.name} ({wc.signal})</span>
                                  <span>{wc.old_weight} ➔ <strong className="text-amber-600">{wc.new_weight}</strong></span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Status Changes */}
                        {comparisonData.status_changes.length > 0 && (
                          <div>
                            <h4 className="text-xs font-semibold text-indigo-600 mb-1">🔄 Enable/Disable Status Diff ({comparisonData.status_changes.length})</h4>
                            <div className="space-y-1 text-xs">
                              {comparisonData.status_changes.map((sc) => (
                                <div key={sc.signal} className="p-2 rounded border bg-muted/20 flex justify-between">
                                  <span>{sc.name}</span>
                                  <Badge variant={sc.new_enabled ? "success" : "secondary"}>
                                    {sc.old_enabled ? "Enabled" : "Disabled"} ➔ {sc.new_enabled ? "Enabled" : "Disabled"}
                                  </Badge>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Added Rules */}
                        {comparisonData.added_rules.length > 0 && (
                          <div>
                            <h4 className="text-xs font-semibold text-emerald-600 mb-1">➕ Newly Added Rules ({comparisonData.added_rules.length})</h4>
                            <div className="space-y-1 text-xs">
                              {comparisonData.added_rules.map((ar) => (
                                <div key={ar.signal} className="p-2 rounded border bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 flex justify-between font-mono">
                                  <span>{ar.name} ({ar.signal})</span>
                                  <span>Weight: {ar.weight}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 7: AI INSIGHTS */}
          {activeTab === "AI Insights" && (
            <div className="space-y-4">
              <div>
                <h1 className="text-2xl font-semibold">Executive AI Security & Architecture Center</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Grounded LLM architectural explanations, refactoring guidance, and threat vector analysis.
                </p>
              </div>

              <div className="grid gap-4 lg:grid-cols-3">
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2">
                        <Sparkles className="size-4 text-primary" /> Active AI Analysis Report
                      </CardTitle>
                      <Badge variant="outline">Ollama qwen3:4b</Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    {latestAnalysis?.ai_report ? (
                      <div className="rounded-md border border-border bg-muted/20 p-4 text-xs whitespace-pre-wrap font-mono leading-relaxed">
                        {latestAnalysis.ai_report}
                      </div>
                    ) : (
                      <div className="py-12 text-center text-xs text-muted-foreground">
                        No AI report generated yet. Run an analysis job to view executive AI insights.
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Architectural Recommendations</CardTitle>
                    <CardDescription>AI-suggested code improvements</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3 text-xs">
                    <div className="p-3 rounded border border-border bg-background space-y-1">
                      <div className="font-semibold text-primary flex items-center gap-1.5">
                        <CheckCircle2 className="size-3.5" /> Decouple Monolithic API Routes
                      </div>
                      <div className="text-muted-foreground">Extract heavy tender enrichment utilities from <code className="text-primary">src/lib</code>.</div>
                    </div>

                    <div className="p-3 rounded border border-border bg-background space-y-1">
                      <div className="font-semibold text-warning flex items-center gap-1.5">
                        <AlertTriangle className="size-3.5" /> Add Integration Spec Tests
                      </div>
                      <div className="text-muted-foreground">Create unit coverage for modified keepalive cron endpoints.</div>
                    </div>

                    <div className="p-3 rounded border border-border bg-background space-y-1">
                      <div className="font-semibold text-emerald-500 flex items-center gap-1.5">
                        <CheckCircle2 className="size-3.5" /> Clean Up Unused Orphans
                      </div>
                      <div className="text-muted-foreground">Review 28 unreferenced files to optimize bundle size.</div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {/* TAB 8: SETTINGS */}
          {activeTab === "Settings" && (
            <div className="space-y-4">
              <AIProviderSettings />
            </div>
          )}
        </div>
      </section>

      <RepoAnalyzerModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onJobStarted={(jobId, repoId) => {
          setActiveJobId(jobId);
          setActiveRepoId(repoId);
        }}
      />
    </main>
  );
}
