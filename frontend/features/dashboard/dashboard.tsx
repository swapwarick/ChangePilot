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
  Sun
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { analyses, providers } from "./data";
import { DependencyGraph } from "./dependency-graph";

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

function Donut({ score = 0.72 }: { score?: number }) {
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
          <div className="text-xs uppercase text-muted-foreground">Project context</div>
          <button className="mt-2 flex h-9 w-full items-center justify-between rounded-md border border-border bg-background px-3 text-left text-sm">
            All repositories
            <ChevronDown data-icon="inline-end" />
          </button>
          <div className="mt-6 flex items-center gap-3">
            <div className="grid size-9 place-items-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
              AS
            </div>
            <div>
              <div className="font-medium">Alex Smith</div>
              <div className="text-xs text-muted-foreground">Staff Engineer</div>
            </div>
          </div>
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
            <Button>
              <Plus data-icon="inline-start" />
              New analysis
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
          <div className="mb-4 flex flex-col items-start justify-between gap-3 xl:flex-row">
            <div>
              <h1 className="text-2xl font-semibold">Dashboard</h1>
              <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
                AI-explained change impact analysis across your software ecosystem.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <RefreshCcw data-icon="inline-start" />
              Updated 2m ago
              <Button variant="outline">
                Last 7 days
                <ChevronDown data-icon="inline-end" />
              </Button>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
            <Card className="xl:col-span-2">
              <CardHeader>
                <div>
                  <CardTitle>Repository risk overview</CardTitle>
                  <CardDescription>128 repositories scored with deterministic evidence.</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 lg:grid-cols-[420px_repeat(4,1fr)]">
                  <div className="flex items-center gap-8">
                    <Donut score={0.5} />
                    <div className="flex flex-col gap-3">
                      {[
                        ["Low risk", "64", "bg-primary"],
                        ["Medium risk", "37", "bg-warning"],
                        ["High risk", "19", "bg-orange-500"],
                        ["Critical risk", "8", "bg-destructive"]
                      ].map(([label, value, color]) => (
                        <div className="flex items-center gap-3" key={label}>
                          <span className={`size-2.5 rounded-full ${color}`} />
                          <span className="min-w-28 text-muted-foreground">{label}</span>
                          <span className="font-semibold">{value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  {[
                    ["High & critical", "27", "21% of repos"],
                    ["Analyses (7d)", "142", "+18%"],
                    ["Mean risk score", "0.42", "-0.08"],
                    ["Policy violations", "23", "+5"]
                  ].map(([label, value, detail]) => (
                    <div className="rounded-md border border-border bg-background p-4" key={label}>
                      <div className="text-xs text-muted-foreground">{label}</div>
                      <div className="mt-4 text-2xl font-semibold">{value}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{detail}</div>
                      <div className="mt-5 h-8 rounded-sm bg-gradient-to-r from-primary/25 via-warning/20 to-destructive/20" />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Recent analyses</CardTitle>
                <Button size="sm" variant="outline">
                  All repositories
                  <ChevronDown data-icon="inline-end" />
                </Button>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto"><Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Analysis</TableHead>
                      <TableHead>Repository</TableHead>
                      <TableHead>Risk</TableHead>
                      <TableHead>Top risk</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Time</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {analyses.map((analysis) => (
                      <TableRow key={analysis.id}>
                        <TableCell className="font-medium">{analysis.subject}</TableCell>
                        <TableCell className="text-muted-foreground">{analysis.repository}</TableCell>
                        <TableCell>
                          <Badge variant={levelVariant(analysis.level)}>{analysis.score.toFixed(2)}</Badge>
                        </TableCell>
                        <TableCell>{analysis.topRisk}</TableCell>
                        <TableCell>
                          <Badge variant="success">Completed</Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{analysis.createdAt}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table></div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Dependency graph preview</CardTitle>
                  <CardDescription>Impacted nodes from the latest high-risk pull request.</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <DependencyGraph />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Deterministic risk breakdown</CardTitle>
                  <CardDescription>Weighted signals calculated without AI input.</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-5 lg:grid-cols-[170px_1fr]">
                  <Donut />
                  <div className="flex flex-col gap-3">
                    {[
                      ["Data consistency", 0.28, "High"],
                      ["External dependencies", 0.18, "High"],
                      ["Performance", 0.12, "Medium"],
                      ["Security", 0.08, "Medium"],
                      ["Test coverage", 0.04, "Low"]
                    ].map(([label, value, impact]) => (
                      <div className="grid grid-cols-[1fr_80px_80px] items-center gap-3" key={label}>
                        <span>{label}</span>
                        <span className="text-muted-foreground">{Number(value).toFixed(2)}</span>
                        <Badge variant={impact === "High" ? "warning" : impact === "Medium" ? "secondary" : "success"}>
                          {impact}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>AI provider status</CardTitle>
                  <CardDescription>Fallback-ready provider health for explanation tasks.</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto"><Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Provider</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>Latency</TableHead>
                      <TableHead>Success</TableHead>
                      <TableHead>Tokens (7d)</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {providers.map((provider) => (
                      <TableRow key={provider.id}>
                        <TableCell className="font-medium">{provider.name}</TableCell>
                        <TableCell className="text-muted-foreground">{provider.model}</TableCell>
                        <TableCell>{provider.latencyMs} ms</TableCell>
                        <TableCell>
                          <Badge variant="success">{provider.successRate}%</Badge>
                        </TableCell>
                        <TableCell>{(provider.usageTokens7d / 1_000_000).toFixed(1)}M</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table></div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>
    </main>
  );
}


