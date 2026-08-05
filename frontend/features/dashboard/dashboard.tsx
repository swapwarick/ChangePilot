"use client";

import { useState, useEffect } from "react";
import {
  Activity,
  Bell,
  Boxes,
  ChevronDown,
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
  Layers
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DependencyGraph } from "./dependency-graph";
import { RepoAnalyzerModal } from "@/features/github/repo-analyzer-modal";
import { JobProgressBanner } from "@/features/analysis/job-progress-banner";
import { AIProviderConfig, ChangeAnalysisResult, RepoKnowledgeGraph } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, active: true },
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
  const degrees = Math.round(score * 360);
  return (
    <div
      className="grid size-32 place-items-center rounded-full"
      style={{
        background: `conic-gradient(hsl(var(--destructive)) 0 ${degrees * 0.28}deg, #f97316 ${degrees * 0.28}deg ${degrees * 0.65}deg, hsl(var(--warning)) ${degrees * 0.65}deg ${degrees}deg, hsl(var(--muted)) ${degrees}deg 360deg)`
      }}
    >
      <div className="grid size-24 place-items-center rounded-full bg-surface text-center">
        <div>
          <div className="text-2xl font-semibold">{score.toFixed(2)}</div>
          <div className="text-[11px] text-muted-foreground">Risk score</div>
        </div>
      </div>
    </div>
  );
}

export function Dashboard() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeRepoId, setActiveRepoId] = useState<string | null>(null);
  const [repositories, setRepositories] = useState<any[]>([]);
  const [providers, setProviders] = useState<AIProviderConfig[]>([]);
  const [analyses, setAnalyses] = useState<ChangeAnalysisResult[]>([]);
  const [knowledgeGraph, setKnowledgeGraph] = useState<RepoKnowledgeGraph | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      // Fetch repositories from DB
      const repoRes = await fetch(`${API_BASE}/repositories`);
      if (repoRes.ok) {
        const repoData = await repoRes.json();
        setRepositories(repoData);
        if (repoData.length > 0 && !activeRepoId) {
          setActiveRepoId(repoData[0].id);
        }
      }

      // Fetch AI Providers
      const provRes = await fetch(`${API_BASE}/ai-providers`);
      if (provRes.ok) {
        setProviders(await provRes.json());
      }
    } catch (err) {
      console.error("Dashboard fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchRepoData = async (repoId: string) => {
    try {
      // Fetch analyses for active repo
      const anlRes = await fetch(`${API_BASE}/analysis?repository_id=${repoId}`);
      if (anlRes.ok) {
        setAnalyses(await anlRes.json());
      }

      // Fetch persistent Knowledge Graph & Health
      const kgRes = await fetch(`${API_BASE}/jobs/repositories/${repoId}/knowledge-graph`);
      if (kgRes.ok) {
        setKnowledgeGraph(await kgRes.json());
      }
    } catch (err) {}
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  useEffect(() => {
    if (activeRepoId) {
      fetchRepoData(activeRepoId);
    }
  }, [activeRepoId]);

  const latestAnalysis = analyses.length > 0 ? analyses[0] : null;
  const healthMetrics = knowledgeGraph?.health_metrics;

  return (
    <main className="flex min-h-screen flex-col text-sm lg:grid lg:grid-cols-[210px_1fr]">
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
            return (
              <a
                className={`flex h-9 items-center gap-3 rounded-md px-3 text-sm ${
                  item.active ? "bg-primary/12 text-primary" : "text-muted-foreground hover:bg-muted"
                }`}
                href={item.label === "Settings" ? "/settings/ai-providers" : "#"}
                key={item.label}
              >
                <Icon data-icon="inline-start" />
                {item.label}
              </a>
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

      <section className="min-w-0">
        <header className="flex min-h-16 flex-col items-stretch justify-between gap-3 border-b border-border bg-surface/80 px-4 py-3 backdrop-blur sm:flex-row sm:items-center sm:px-5">
          <div className="flex h-10 w-full items-center gap-2 rounded-md border border-border bg-background px-3 text-muted-foreground sm:max-w-[520px]">
            <Search data-icon="inline-start" />
            <span className="text-sm">Search services, repositories, analyses...</span>
            <kbd className="ml-auto rounded-sm border border-border px-1.5 py-0.5 text-xs">⌘ K</kbd>
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button onClick={() => setIsModalOpen(true)} className="flex items-center gap-2">
              <Github className="size-4" />
              Connect & Analyze Repo
            </Button>
            <Button aria-label="Notifications" size="icon" variant="ghost">
              <Bell />
            </Button>
            <Button aria-label="Help" size="icon" variant="ghost">
              <CircleHelp />
            </Button>
            <Button aria-label="Theme" size="icon" variant="ghost">
              <Sun />
            </Button>
          </div>
        </header>

        <div className="p-5">
          {activeJobId && (
            <JobProgressBanner
              jobId={activeJobId}
              onJobComplete={(anlId) => {
                if (activeRepoId) fetchRepoData(activeRepoId);
              }}
            />
          )}

          <div className="mb-4 flex flex-col items-start justify-between gap-3 xl:flex-row">
            <div>
              <h1 className="text-2xl font-semibold">Repository Knowledge Graph</h1>
              <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
                Real code analysis, AST dependency graphing, deterministic risk scoring, and repo health metrics.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <RefreshCcw className="size-4 cursor-pointer" onClick={fetchDashboardData} />
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
                        <Badge variant={levelVariant(latestAnalysis?.risk.level || "low")}>
                          {latestAnalysis?.risk.level?.toUpperCase() || "LOW"}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="size-2.5 rounded-full bg-warning" />
                        <span className="min-w-28 text-muted-foreground">Confidence</span>
                        <span className="font-semibold">{((latestAnalysis?.risk.confidence || 0) * 100).toFixed(0)}%</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="size-2.5 rounded-full bg-orange-500" />
                        <span className="min-w-28 text-muted-foreground">Impacted Files</span>
                        <span className="font-semibold">{latestAnalysis?.changed_files.length || 0}</span>
                      </div>
                    </div>
                  </div>
                  {[
                    ["Knowledge Graph Files", healthMetrics?.total_files || 0, "Parsed AST nodes"],
                    ["Circular Dependencies", healthMetrics?.circular_dependencies.length || 0, "Cycle import loops"],
                    ["Orphan Modules", healthMetrics?.orphan_modules.length || 0, "Unreferenced files"],
                    ["Test Coverage Gaps", healthMetrics?.test_coverage_gaps.length || 0, "Missing unit tests"]
                  ].map(([label, value, detail]) => (
                    <div className="rounded-md border border-border bg-background p-4" key={String(label)}>
                      <div className="text-xs text-muted-foreground">{String(label)}</div>
                      <div className="mt-4 text-2xl font-semibold">{String(value)}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{String(detail)}</div>
                      <div className="mt-5 h-8 rounded-sm bg-gradient-to-r from-primary/25 via-warning/20 to-destructive/20" />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

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
                  <div className="overflow-x-auto"><Table>
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
                        <TableRow key={anl.id}>
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
                  </Table></div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Knowledge Graph Structure</CardTitle>
                  <CardDescription>Visual AST graph parsed from Tree-Sitter & Neo4j engine.</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <DependencyGraph />
              </CardContent>
            </Card>

            <Card className="xl:col-span-2">
              <CardHeader>
                <div>
                  <CardTitle>AI Report & Evidence Breakdown</CardTitle>
                  <CardDescription>Asynchronously generated AI summary grounded in real AST signals.</CardDescription>
                </div>
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
