"use client";

import { useState, useEffect } from "react";
import { Search, GitBranch, GitCommit, Play, Github, ShieldAlert, Loader2, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { GitRepositoryInfo, GitBranchInfo, GitCommitInfo } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface RepoAnalyzerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onJobStarted: (jobId: string, repoId: string) => void;
}

export function RepoAnalyzerModal({ isOpen, onClose, onJobStarted }: RepoAnalyzerModalProps) {
  const [token, setToken] = useState<string>("");
  const [githubUser, setGithubUser] = useState<any>(null);
  const [repositories, setRepositories] = useState<GitRepositoryInfo[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRepo, setSelectedRepo] = useState<GitRepositoryInfo | null>(null);
  const [branches, setBranches] = useState<GitBranchInfo[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>("main");
  const [commits, setCommits] = useState<GitCommitInfo[]>([]);
  const [headCommit, setHeadCommit] = useState<string>("");
  const [baseCommit, setBaseCommit] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const savedToken = localStorage.getItem("changepilot_github_token");
    if (savedToken) {
      setToken(savedToken);
      fetchGithubUser(savedToken);
      fetchRepositories(savedToken);
    }
  }, []);

  const fetchGithubUser = async (t: string) => {
    try {
      const res = await fetch(`${API_BASE}/github/user`, {
        headers: { Authorization: t }
      });
      if (res.ok) {
        const data = await res.json();
        setGithubUser(data);
        localStorage.setItem("changepilot_github_token", t);
      } else {
        setError("GitHub Auth failed. Please check your Personal Access Token.");
        setGithubUser(null);
      }
    } catch (err: any) {
      setError(`Auth Error: ${err.message}`);
    }
  };

  const fetchRepositories = async (t: string, query: string = "") => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/github/repositories?query=${encodeURIComponent(query)}`, {
        headers: { Authorization: t }
      });
      if (res.ok) {
        const data = await res.json();
        setRepositories(data);
      } else {
        setError("Failed to fetch repositories.");
      }
    } catch (err: any) {
      setError(`Fetch Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleConnectToken = () => {
    if (!token.trim()) return;
    fetchGithubUser(token);
    fetchRepositories(token);
  };

  const handleSelectRepo = async (repo: GitRepositoryInfo) => {
    setSelectedRepo(repo);
    setSelectedBranch(repo.default_branch || "main");
    fetchBranches(repo.owner, repo.name, token);
    fetchCommits(repo.owner, repo.name, repo.default_branch || "main", token);
  };

  const fetchBranches = async (owner: string, repo: string, t: string) => {
    try {
      const res = await fetch(`${API_BASE}/github/repositories/${owner}/${repo}/branches`, {
        headers: { Authorization: t }
      });
      if (res.ok) {
        const data = await res.json();
        setBranches(data);
      }
    } catch (err) {}
  };

  const fetchCommits = async (owner: string, repo: string, branch: string, t: string) => {
    try {
      const res = await fetch(`${API_BASE}/github/repositories/${owner}/${repo}/commits?branch=${branch}`, {
        headers: { Authorization: t }
      });
      if (res.ok) {
        const data: GitCommitInfo[] = await res.json();
        setCommits(data);
        if (data.length > 0) {
          setHeadCommit(data[0].sha);
          setBaseCommit(data.length > 1 ? data[1].sha : `${data[0].sha}~1`);
        }
      }
    } catch (err) {}
  };

  const handleStartAnalysis = async () => {
    if (!selectedRepo || !headCommit) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/jobs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: token
        },
        body: JSON.stringify({
          repository_url: selectedRepo.clone_url,
          owner: selectedRepo.owner,
          repo_name: selectedRepo.name,
          base_ref: baseCommit || `${headCommit}~1`,
          head_ref: headCommit
        })
      });
      if (res.ok) {
        const job = await res.json();
        onJobStarted(job.id, `${selectedRepo.owner}-${selectedRepo.name}`.toLowerCase());
        onClose();
      } else {
        const errData = await res.json();
        setError(`Job creation failed: ${errData.detail || "Unknown error"}`);
      }
    } catch (err: any) {
      setError(`Submit Error: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl rounded-xl border border-border bg-card p-6 shadow-2xl text-card-foreground">
        <div className="flex items-center justify-between border-b border-border pb-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
              <Github className="size-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Connect & Analyze GitHub Repository</h2>
              <p className="text-xs text-muted-foreground">Select a real repository to build knowledge graph & score change impact.</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>✕</Button>
        </div>

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
            <ShieldAlert className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!githubUser ? (
          <div className="space-y-4 py-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground">GitHub Personal Access Token (PAT)</label>
              <input
                type="password"
                placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                className="mt-1 flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <p className="mt-1 text-[11px] text-muted-foreground">
                Requires <code className="text-primary">repo</code> scope for private repositories or standard read access for public repos.
              </p>
            </div>
            <Button className="w-full" onClick={handleConnectToken} disabled={!token.trim()}>
              Authenticate with GitHub
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between rounded-md border border-border bg-muted/30 p-3">
              <div className="flex items-center gap-3">
                <img src={githubUser.avatar_url} alt={githubUser.login} className="size-8 rounded-full" />
                <div>
                  <div className="text-sm font-medium">{githubUser.name} ({githubUser.login})</div>
                  <div className="text-xs text-emerald-500 flex items-center gap-1">
                    <CheckCircle2 className="size-3" /> Connected to GitHub
                  </div>
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={() => { setGithubUser(null); localStorage.removeItem("changepilot_github_token"); }}>
                Disconnect
              </Button>
            </div>

            {!selectedRepo ? (
              <div>
                <div className="relative mb-3">
                  <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder="Search your GitHub repositories..."
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      fetchRepositories(token, e.target.value);
                    }}
                    className="flex h-9 w-full rounded-md border border-border bg-background pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div className="max-h-60 overflow-y-auto space-y-2 pr-1">
                  {loading ? (
                    <div className="py-8 text-center text-xs text-muted-foreground flex justify-center items-center gap-2">
                      <Loader2 className="size-4 animate-spin" /> Loading repositories...
                    </div>
                  ) : repositories.length === 0 ? (
                    <div className="py-8 text-center text-xs text-muted-foreground">No repositories found.</div>
                  ) : (
                    repositories.map((repo) => (
                      <div
                        key={repo.id}
                        onClick={() => handleSelectRepo(repo)}
                        className="flex items-center justify-between rounded-md border border-border p-3 hover:bg-muted/50 cursor-pointer transition-colors"
                      >
                        <div>
                          <div className="text-sm font-medium text-foreground">{repo.full_name}</div>
                          <div className="text-xs text-muted-foreground truncate max-w-md">{repo.description || "No description"}</div>
                        </div>
                        <div className="flex items-center gap-2">
                          {repo.private && <Badge variant="secondary">Private</Badge>}
                          {repo.language && <Badge variant="outline">{repo.language}</Badge>}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between rounded-md border border-border bg-muted/20 p-3">
                  <div>
                    <div className="text-xs text-muted-foreground">Selected Repository</div>
                    <div className="text-sm font-semibold">{selectedRepo.full_name}</div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => setSelectedRepo(null)}>Change Repo</Button>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                      <GitBranch className="size-3" /> Branch
                    </label>
                    <select
                      value={selectedBranch}
                      onChange={(e) => {
                        setSelectedBranch(e.target.value);
                        fetchCommits(selectedRepo.owner, selectedRepo.name, e.target.value, token);
                      }}
                      className="mt-1 h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
                    >
                      {branches.map((b) => (
                        <option key={b.name} value={b.name}>{b.name}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                      <GitCommit className="size-3" /> Head Commit
                    </label>
                    <select
                      value={headCommit}
                      onChange={(e) => setHeadCommit(e.target.value)}
                      className="mt-1 h-9 w-full rounded-md border border-border bg-background px-3 text-sm font-mono"
                    >
                      {commits.map((c) => (
                        <option key={c.sha} value={c.sha}>
                          [{c.short_sha}] {c.message.slice(0, 30)}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <Button
                  className="w-full mt-4 flex items-center justify-center gap-2"
                  onClick={handleStartAnalysis}
                  disabled={submitting || !headCommit}
                >
                  {submitting ? (
                    <>
                      <Loader2 className="size-4 animate-spin" /> Starting Async Analysis Worker...
                    </>
                  ) : (
                    <>
                      <Play className="size-4" /> Run Real Repository Analysis
                    </>
                  )}
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
