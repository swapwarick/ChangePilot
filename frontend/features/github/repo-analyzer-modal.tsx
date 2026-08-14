"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  Search,
  GitBranch,
  GitCommit,
  Play,
  Github,
  ShieldAlert,
  Loader2,
  CheckCircle2,
  Folder,
  FolderCode,
  HardDrive,
  Sparkles,
  FileCode,
  Layers,
  FolderSearch,
  Check,
  ChevronRight,
  ChevronUp,
  Clock,
  GitFork,
  X,
  FolderOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { GitRepositoryInfo, GitBranchInfo, GitCommitInfo } from "@/types/api";
import { getApiBaseUrl } from "@/lib/api-config";

interface RepoAnalyzerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onJobStarted: (jobId: string, repoId: string) => void;
}

interface LocalRepoInfo {
  valid: boolean;
  path: string;
  name: string;
  is_git: boolean;
  default_branch: string;
  branches: { name: string; is_current: boolean }[];
  commits: { sha: string; short_sha: string; message: string; author: string; date: string }[];
  file_count: number;
  error?: string;
}

interface DirectoryEntry {
  name: string;
  path: string;
  is_git: boolean;
  has_children: boolean;
}

interface BrowseResponse {
  current_path: string;
  parent_path: string | null;
  entries: DirectoryEntry[];
}

const RECENT_FOLDERS_KEY = "changepilot_recent_folders";
const MAX_RECENT = 6;

export function RepoAnalyzerModal({ isOpen, onClose, onJobStarted }: RepoAnalyzerModalProps) {
  const [scanMode, setScanMode] = useState<"local" | "github">("local");

  // Local scanning state
  const [localPath, setLocalPath] = useState<string>("");
  const [localInfo, setLocalInfo] = useState<LocalRepoInfo | null>(null);
  const [loadingLocal, setLoadingLocal] = useState(false);
  const [localHeadCommit, setLocalHeadCommit] = useState<string>("");
  const [localBaseCommit, setLocalBaseCommit] = useState<string>("");

  // Folder browser state
  const [showBrowser, setShowBrowser] = useState(false);
  const [browseData, setBrowseData] = useState<BrowseResponse | null>(null);
  const [browseLoading, setBrowseLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<DirectoryEntry[] | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [recentFolders, setRecentFolders] = useState<string[]>([]);
  const searchDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  // GitHub scanning state
  const [token, setToken] = useState<string>("");
  const [githubUser, setGithubUser] = useState<any>(null);
  const [repositories, setRepositories] = useState<GitRepositoryInfo[]>([]);
  const [githubSearchQuery, setGithubSearchQuery] = useState("");
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
    // Auto-fetch local workspace on mount
    fetchCurrentWorkspace();
    // Load recent folders
    const saved = localStorage.getItem(RECENT_FOLDERS_KEY);
    if (saved) setRecentFolders(JSON.parse(saved));
  }, []);

  const saveRecentFolder = useCallback((path: string) => {
    setRecentFolders((prev) => {
      const next = [path, ...prev.filter((p) => p !== path)].slice(0, MAX_RECENT);
      localStorage.setItem(RECENT_FOLDERS_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const browseDirectory = async (path?: string) => {
    setBrowseLoading(true);
    setSearchResults(null);
    setSearchQuery("");
    try {
      const targetPath = path && path.trim() ? path.trim() : undefined;
      const url = targetPath
        ? `${getApiBaseUrl()}/local/browse?path=${encodeURIComponent(targetPath)}`
        : `${getApiBaseUrl()}/local/browse`;

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);

      try {
        const res = await fetch(url, { signal: controller.signal });
        clearTimeout(timeoutId);
        if (res.ok) {
          setBrowseData(await res.json());
          return;
        }
      } catch (fetchErr) {
        clearTimeout(timeoutId);
      }

      if (targetPath) {
        // Fallback to root drives if target path failed or timed out
        const rootController = new AbortController();
        const rootTimeoutId = setTimeout(() => rootController.abort(), 3000);
        try {
          const rootRes = await fetch(`${getApiBaseUrl()}/local/browse`, { signal: rootController.signal });
          clearTimeout(rootTimeoutId);
          if (rootRes.ok) setBrowseData(await rootRes.json());
        } catch (err) {
          clearTimeout(rootTimeoutId);
        }
      }
    } catch (e) {
    } finally {
      setBrowseLoading(false);
    }
  };

  const handleSearch = useCallback((q: string) => {
    setSearchQuery(q);
    if (searchDebounce.current) clearTimeout(searchDebounce.current);
    if (!q.trim()) { setSearchResults(null); return; }
    searchDebounce.current = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const root = browseData?.current_path || undefined;
        const url = root
          ? `${getApiBaseUrl()}/local/search?query=${encodeURIComponent(q)}&root=${encodeURIComponent(root)}`
          : `${getApiBaseUrl()}/local/search?query=${encodeURIComponent(q)}`;
        const res = await fetch(url);
        if (res.ok) setSearchResults(await res.json());
      } catch (e) {} finally { setSearchLoading(false); }
    }, 300);
  }, [browseData]);

  const selectFolder = (path: string) => {
    setLocalPath(path);
    setShowBrowser(false);
    setSearchQuery("");
    setSearchResults(null);
    inspectLocalPath(path);
    saveRecentFolder(path);
  };

  const fetchCurrentWorkspace = async () => {
    try {
      const res = await fetch(`${getApiBaseUrl()}/local/workspace`);
      if (res.ok) {
        const data = await res.json();
        if (data.path) {
          setLocalPath(data.path);
          inspectLocalPath(data.path);
        }
      }
    } catch (err) {}
  };

  const inspectLocalPath = async (targetPath: string) => {
    if (!targetPath || !targetPath.trim()) return;
    setLoadingLocal(true);
    setError(null);
    try {
      const res = await fetch(`${getApiBaseUrl()}/local/info?path=${encodeURIComponent(targetPath.trim())}`);
      if (res.ok) {
        const info: LocalRepoInfo = await res.json();
        setLocalInfo(info);
        if (!info.valid) {
          setError(info.error || "Directory does not exist or is invalid.");
        } else if (info.commits.length > 0) {
          setLocalHeadCommit(info.commits[0].sha);
          setLocalBaseCommit(info.commits.length > 1 ? info.commits[1].sha : `${info.commits[0].sha}~1`);
        } else {
          setLocalHeadCommit("HEAD");
          setLocalBaseCommit("empty");
        }
      } else {
        const errData = await res.json().catch(() => ({ detail: null }));
        setError(errData.detail || "Failed to inspect local directory path.");
        setLocalInfo(null);
      }
    } catch (err: any) {
      setError(`Local Inspect Error: ${err.message}`);
      setLocalInfo(null);
    } finally {
      setLoadingLocal(false);
    }
  };

  const fetchGithubUser = async (t: string) => {
    try {
      const res = await fetch(`${getApiBaseUrl()}/github/user`, {
        headers: { Authorization: t }
      });
      if (res.ok) {
        const data = await res.json();
        setGithubUser(data);
        localStorage.setItem("changepilot_github_token", t);
      } else {
        const errData = await res.json().catch(() => ({ detail: null }));
        setError(errData.detail || "GitHub Auth failed. Please check your Personal Access Token.");
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
      const res = await fetch(`${getApiBaseUrl()}/github/repositories?query=${encodeURIComponent(query)}`, {
        headers: { Authorization: t }
      });
      if (res.ok) {
        const data = await res.json();
        setRepositories(data);
      } else {
        const errData = await res.json().catch(() => ({ detail: null }));
        setError(errData.detail || "Failed to fetch repositories.");
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
      const res = await fetch(`${getApiBaseUrl()}/github/repositories/${owner}/${repo}/branches`, {
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
      const res = await fetch(`${getApiBaseUrl()}/github/repositories/${owner}/${repo}/commits?branch=${branch}`, {
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

  const handleStartLocalAnalysis = async () => {
    if (!localInfo || !localInfo.valid) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${getApiBaseUrl()}/jobs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          repository_url: localInfo.path,
          owner: "local",
          repo_name: localInfo.name,
          base_ref: localBaseCommit || (localInfo.is_git ? "main~1" : "empty"),
          head_ref: localHeadCommit || (localInfo.is_git ? "main" : "HEAD")
        })
      });

      if (res.ok) {
        const job = await res.json();
        onJobStarted(job.id, `local-${localInfo.name}`.toLowerCase());
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

  const handleStartGithubAnalysis = async () => {
    if (!selectedRepo || !headCommit) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${getApiBaseUrl()}/jobs`, {
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
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border pb-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-lg bg-primary/10 text-primary">
              {scanMode === "local" ? <HardDrive className="size-5" /> : <Github className="size-5" />}
            </div>
            <div>
              <h2 className="text-lg font-semibold">Select Repository or Folder to Analyze</h2>
              <p className="text-xs text-muted-foreground">Scan local directory paths directly from disk or connect GitHub cloud repos.</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>✕</Button>
        </div>

        {/* Tab Switcher */}
        <div className="flex rounded-lg border border-border bg-muted/30 p-1 mb-4">
          <button
            onClick={() => { setScanMode("local"); setError(null); }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 text-xs font-semibold rounded-md transition-all ${
              scanMode === "local" ? "bg-background shadow-xs text-foreground" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <FolderCode className="size-4 text-emerald-500" /> Local Folder / Local Repo
          </button>
          <button
            onClick={() => { setScanMode("github"); setError(null); }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 text-xs font-semibold rounded-md transition-all ${
              scanMode === "github" ? "bg-background shadow-xs text-foreground" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Github className="size-4 text-primary" /> GitHub Cloud
          </button>
        </div>

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
            <ShieldAlert className="size-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Local Folder / Repo Mode */}
        {scanMode === "local" && (
          <div className="space-y-3">
            {/* Path input row */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  <HardDrive className="size-3.5" /> Local Directory Path
                </label>
                <button
                  onClick={fetchCurrentWorkspace}
                  className="text-[11px] text-primary hover:underline flex items-center gap-1"
                >
                  <Sparkles className="size-3" /> Auto-Detect Workspace
                </button>
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="e.g. C:\Users\YourName\Desktop\MyProject"
                  value={localPath}
                  onChange={(e) => setLocalPath(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && inspectLocalPath(localPath)}
                  className="flex-1 h-10 rounded-md border border-border bg-background px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowBrowser((v) => {
                      if (!v) browseDirectory(localPath);
                      return !v;
                    });
                  }}
                  className="gap-1.5 shrink-0"
                >
                  <FolderOpen className="size-4" /> Browse
                </Button>
                <Button onClick={() => inspectLocalPath(localPath)} disabled={loadingLocal || !localPath.trim()}>
                  {loadingLocal ? <Loader2 className="size-4 animate-spin" /> : <FolderSearch className="size-4" />}
                  Inspect
                </Button>
              </div>
            </div>

            {/* Folder Browser Panel */}
            {showBrowser && (
              <div className="rounded-lg border border-border bg-background shadow-inner overflow-hidden animate-in fade-in slide-in-from-top-1 duration-200">
                {/* Search bar */}
                <div className="flex items-center gap-2 px-3 py-2 border-b border-border bg-muted/20">
                  <Search className="size-3.5 text-muted-foreground shrink-0" />
                  <input
                    autoFocus
                    type="text"
                    placeholder="Search folders by name…"
                    value={searchQuery}
                    onChange={(e) => handleSearch(e.target.value)}
                    className="flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
                  />
                  {searchQuery && (
                    <button onClick={() => { setSearchQuery(""); setSearchResults(null); }} className="text-muted-foreground hover:text-foreground">
                      <X className="size-3.5" />
                    </button>
                  )}
                  {(searchLoading || browseLoading) && <Loader2 className="size-3.5 animate-spin text-muted-foreground shrink-0" />}
                </div>

                {/* Breadcrumb path */}
                {!searchQuery && browseData?.current_path && (
                  <div className="flex items-center gap-1 px-3 py-1.5 border-b border-border/50 bg-muted/10 overflow-x-auto">
                    {browseData.parent_path != null && (
                      <button
                        onClick={() => browseDirectory(browseData.parent_path!)}
                        className="flex items-center gap-1 text-[11px] text-primary hover:underline shrink-0"
                      >
                        <ChevronUp className="size-3" /> Up
                      </button>
                    )}
                    <span className="text-[11px] font-mono text-muted-foreground truncate">{browseData.current_path}</span>
                  </div>
                )}

                {/* Directory listing */}
                <div className="max-h-48 overflow-y-auto divide-y divide-border/40">
                  {/* Search results */}
                  {searchQuery && (
                    searchLoading ? (
                      <div className="py-6 text-center text-xs text-muted-foreground">Searching…</div>
                    ) : !searchResults || searchResults.length === 0 ? (
                      <div className="py-6 text-center text-xs text-muted-foreground">No folders found matching "{searchQuery}"</div>
                    ) : (
                      searchResults.map((entry) => (
                        <div
                          key={entry.path}
                          onClick={() => selectFolder(entry.path)}
                          className="flex items-center gap-2 px-3 py-2 hover:bg-muted/50 cursor-pointer group transition-colors"
                        >
                          {entry.is_git
                            ? <GitFork className="size-3.5 text-emerald-500 shrink-0" />
                            : <Folder className="size-3.5 text-muted-foreground shrink-0" />
                          }
                          <div className="min-w-0">
                            <div className="text-xs font-medium truncate">{entry.name}</div>
                            <div className="text-[10px] font-mono text-muted-foreground truncate">{entry.path}</div>
                          </div>
                          {entry.is_git && <Badge className="ml-auto shrink-0 text-[9px] bg-emerald-500/10 text-emerald-600 border-emerald-500/30">Git</Badge>}
                        </div>
                      ))
                    )
                  )}

                  {/* Browse tree */}
                  {!searchQuery && (
                    browseLoading ? (
                      <div className="py-6 text-center text-xs text-muted-foreground">Loading…</div>
                    ) : !browseData || browseData.entries.length === 0 ? (
                      <div className="py-6 text-center text-xs text-muted-foreground">No folders found</div>
                    ) : (
                      browseData.entries.map((entry) => (
                        <div key={entry.path} className="flex items-center group hover:bg-muted/50 transition-colors">
                          <button
                            onClick={() => selectFolder(entry.path)}
                            className="flex-1 flex items-center gap-2 px-3 py-2 text-left cursor-pointer"
                          >
                            {entry.is_git
                              ? <GitFork className="size-3.5 text-emerald-500 shrink-0" />
                              : <Folder className="size-3.5 text-muted-foreground shrink-0" />
                            }
                            <span className="text-xs truncate">{entry.name}</span>
                            {entry.is_git && <Badge className="ml-1 shrink-0 text-[9px] bg-emerald-500/10 text-emerald-600 border-emerald-500/30">Git</Badge>}
                          </button>
                          {entry.has_children && (
                            <button
                              onClick={(e) => { e.stopPropagation(); browseDirectory(entry.path); }}
                              className="px-2.5 py-1.5 text-muted-foreground hover:text-primary hover:bg-muted/80 rounded transition-colors flex items-center gap-1 shrink-0 mr-1"
                              title={`Open ${entry.name}`}
                            >
                              <span className="text-[10px] hidden group-hover:inline">Open</span>
                              <ChevronRight className="size-3.5" />
                            </button>
                          )}
                        </div>
                      ))
                    )
                  )}
                </div>
              </div>
            )}

            {/* Recent folders */}
            {!showBrowser && recentFolders.length > 0 && !localInfo && (
              <div>
                <div className="flex items-center gap-1.5 mb-1.5">
                  <Clock className="size-3 text-muted-foreground" />
                  <span className="text-[11px] font-medium text-muted-foreground">Recently Used</span>
                </div>
                <div className="space-y-1">
                  {recentFolders.map((p) => (
                    <button
                      key={p}
                      onClick={() => selectFolder(p)}
                      className="w-full text-left flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-mono text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors border border-transparent hover:border-border"
                    >
                      <Folder className="size-3.5 shrink-0" />
                      <span className="truncate">{p}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {localInfo && localInfo.valid && (
              <div className="rounded-lg border border-border bg-muted/20 p-4 space-y-3 animate-in fade-in duration-200">
                <div className="flex items-center justify-between border-b border-border/60 pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-sm">{localInfo.name}</h3>
                      {localInfo.is_git ? (
                        <Badge variant="outline" className="border-emerald-500 text-emerald-600 bg-emerald-500/10 text-[10px]">
                          Git Repository
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="text-[10px]">
                          Local Plain Folder
                        </Badge>
                      )}
                    </div>
                    <p className="text-[11px] font-mono text-muted-foreground truncate max-w-md mt-0.5">{localInfo.path}</p>
                  </div>
                  <div className="text-right text-xs">
                    <div className="font-bold text-foreground">{localInfo.file_count}</div>
                    <div className="text-[10px] text-muted-foreground">Source Files</div>
                  </div>
                </div>

                {localInfo.is_git && localInfo.commits.length > 0 && (
                  <div className="grid grid-cols-2 gap-3 pt-1">
                    <div>
                      <label className="text-[11px] font-medium text-muted-foreground flex items-center gap-1 mb-1">
                        <GitBranch className="size-3" /> Branch
                      </label>
                      <select
                        value={localInfo.default_branch}
                        disabled
                        className="h-8 w-full rounded-md border border-border bg-background px-2 text-xs font-mono"
                      >
                        {localInfo.branches.map((b) => (
                          <option key={b.name} value={b.name}>
                            {b.is_current ? `* ${b.name} (active)` : b.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="text-[11px] font-medium text-muted-foreground flex items-center gap-1 mb-1">
                        <GitCommit className="size-3" /> Commit to Analyze
                      </label>
                      <select
                        value={localHeadCommit}
                        onChange={(e) => setLocalHeadCommit(e.target.value)}
                        className="h-8 w-full rounded-md border border-border bg-background px-2 text-xs font-mono"
                      >
                        {localInfo.commits.map((c) => (
                          <option key={c.sha} value={c.sha}>
                            [{c.short_sha}] {c.message.slice(0, 30)}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}

                <Button
                  className="w-full mt-2 flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white"
                  onClick={handleStartLocalAnalysis}
                  disabled={submitting}
                >
                  {submitting ? (
                    <>
                      <Loader2 className="size-4 animate-spin" /> Running Local AST Worker...
                    </>
                  ) : (
                    <>
                      <Play className="size-4 fill-white" /> Scan & Analyze Local Folder
                    </>
                  )}
                </Button>
              </div>
            )}
          </div>
        )}


        {/* GitHub Cloud Mode */}
        {scanMode === "github" && (
          <>
            {!githubUser ? (
              <div className="space-y-4 py-2">
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
                        value={githubSearchQuery}
                        onChange={(e) => {
                          setGithubSearchQuery(e.target.value);
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
                      onClick={handleStartGithubAnalysis}
                      disabled={submitting || !headCommit}
                    >
                      {submitting ? (
                        <>
                          <Loader2 className="size-4 animate-spin" /> Starting Async Analysis Worker...
                        </>
                      ) : (
                        <>
                          <Play className="size-4" /> Run Remote GitHub Analysis
                        </>
                      )}
                    </Button>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
