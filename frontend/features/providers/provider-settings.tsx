"use client";

import { useEffect, useState } from "react";
import { PlugZap, Plus, Search, Check, Sparkles, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { AIProviderConfig } from "@/types/api";
import { getApiBaseUrl } from "@/lib/api-config";
import { authHeader } from "@/lib/auth-client";

// ---------- preset model catalogues ----------
const GROQ_MODELS = [
  { label: "Llama 3.3 70B (free)", value: "llama-3.3-70b-versatile" },
  { label: "Llama 3.1 8B (free)", value: "llama-3.1-8b-instant" },
  { label: "Gemma 2 9B (free)", value: "gemma2-9b-it" },
  { label: "Mixtral 8x7B (free)", value: "mixtral-8x7b-32768" },
];

const NVIDIA_MODELS = [
  { label: "GLM-5.2 (z-ai, free tier)", value: "z-ai/glm-5.2", maxTokens: 16384 },
  { label: "Llama 3.1 70B (free tier)", value: "meta/llama-3.1-70b-instruct", maxTokens: 4096 },
  { label: "Llama 3.1 8B (free tier)", value: "meta/llama-3.1-8b-instruct", maxTokens: 4096 },
  { label: "Mistral NeMo (free tier)", value: "mistralai/mistral-nemo-12b-instruct", maxTokens: 4096 },
  { label: "Phi-3 Mini (free tier)", value: "microsoft/phi-3-mini-128k-instruct", maxTokens: 4096 },
];

const OPENROUTER_MODELS = [
  { label: "NVIDIA Nemotron 3.5 Lightning (free)", value: "nvidia/nemotron-3.5-lightning:free", maxTokens: 8192 },
  { label: "Llama 3.3 70B Instruct (free)", value: "meta-llama/llama-3.3-70b-instruct:free", maxTokens: 4096 },
  { label: "DeepSeek R1 Reasoning (free)", value: "deepseek/deepseek-r1:free", maxTokens: 8192 },
  { label: "DeepSeek V3 Chat (free)", value: "deepseek/deepseek-chat:free", maxTokens: 8192 },
  { label: "Qwen 2.5 Coder 32B (free)", value: "qwen/qwen-2.5-coder-32b-instruct:free", maxTokens: 4096 },
  { label: "Gemini 2.0 Flash (free)", value: "google/gemini-2.0-flash-exp:free", maxTokens: 8192 },
  { label: "Mistral 7B Instruct (free)", value: "mistralai/mistral-7b-instruct:free", maxTokens: 4096 },
];

export function AIProviderSettings() {
  const [providers, setProviders] = useState<AIProviderConfig[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);

  // modal state for cloud provider quick-add
  const [modal, setModal] = useState<null | "groq" | "nvidia" | "openrouter">(null);
  const [apiKey, setApiKey] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [customModel, setCustomModel] = useState("");

  const fetchProviders = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/ai-providers`, {
        headers: authHeader(),
      });
      if (res.ok) {
        setProviders(await res.json());
      }
    } catch (err) {
      console.error("Fetch providers error:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProviders();
  }, []);

  const openModal = (kind: "groq" | "nvidia" | "openrouter") => {
    const defaults =
      kind === "groq"
        ? GROQ_MODELS
        : kind === "nvidia"
        ? NVIDIA_MODELS
        : OPENROUTER_MODELS;
    setSelectedModel(defaults[0].value);
    setCustomModel("");
    setApiKey("");
    setModal(kind);
  };

  const closeModal = () => {
    setModal(null);
    setApiKey("");
    setSelectedModel("");
    setCustomModel("");
  };

  const filteredProviders = providers.filter((provider) =>
    `${provider.name} ${provider.kind} ${provider.model}`.toLowerCase().includes(query.toLowerCase())
  );

  const toggleProvider = async (provider: AIProviderConfig, enabled: boolean) => {
    const updated = { ...provider, enabled };
    try {
      const res = await fetch(`${getApiBaseUrl()}/ai-providers/${provider.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeader() },
        body: JSON.stringify(updated),
      });
      if (res.ok) {
        setProviders((curr) => curr.map((p) => (p.id === provider.id ? updated : p)));
      }
    } catch (err) {}
  };

  const setDefault = async (provider: AIProviderConfig) => {
    const updated = { ...provider, is_default: true };
    try {
      const res = await fetch(`${getApiBaseUrl()}/ai-providers/${provider.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeader() },
        body: JSON.stringify(updated),
      });
      if (res.ok) {
        fetchProviders();
      }
    } catch (err) {}
  };

  const handleDeleteProvider = async (providerId: string, providerName: string) => {
    if (!window.confirm(`Are you sure you want to delete AI provider "${providerName}"?`)) return;
    try {
      const res = await fetch(`${getApiBaseUrl()}/ai-providers/${providerId}`, {
        method: "DELETE",
        headers: authHeader(),
      });
      if (res.ok || res.status === 204) {
        setProviders((prev) => prev.filter((p) => p.id !== providerId));
      }
    } catch (err) {
      console.error("Delete provider error:", err);
    }
  };

  const handleAddDefaultOllama = async () => {
    setSavingId("ollama");
    const cfg: AIProviderConfig = {
      id: "ollama-local",
      name: "Ollama Local (qwen3:4b)",
      kind: "ollama",
      base_url: "http://localhost:11434",
      model: "qwen3:4b",
      enabled: true,
      is_default: providers.length === 0,
      priority: 1,
      task_categories: ["report"],
      fallback_provider_ids: [],
      custom_headers: {},
      temperature: 0.2,
      max_tokens: 1600,
      timeout_seconds: 120,
    };
    try {
      const res = await fetch(`${getApiBaseUrl()}/ai-providers/${cfg.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeader() },
        body: JSON.stringify(cfg),
      });
      if (res.ok) fetchProviders();
    } catch (err) {
    } finally {
      setSavingId(null);
    }
  };

  const handleAddCloudProvider = async () => {
    if (!modal || !apiKey.trim()) return;
    setSavingId(modal);

    const isGroq = modal === "groq";
    const isNvidia = modal === "nvidia";
    const isOpenRouter = modal === "openrouter";

    const targetModel = selectedModel === "custom" ? customModel.trim() : selectedModel;
    if (!targetModel) return;

    const list = isGroq ? GROQ_MODELS : isNvidia ? NVIDIA_MODELS : OPENROUTER_MODELS;
    const modelMeta = list.find((m) => m.value === targetModel);
    const slug = targetModel.replace(/[\/:]/g, "-");
    const id = isGroq ? `groq-${slug}` : isNvidia ? `nvidia-nim-${slug}` : `openrouter-${slug}`;

    const baseUrl = isGroq
      ? "https://api.groq.com/openai/v1"
      : isNvidia
      ? "https://integrate.api.nvidia.com/v1"
      : "https://openrouter.ai/api/v1";

    const customHeaders: Record<string, string> = isOpenRouter
      ? {
          "HTTP-Referer": "https://changepilot-frontend.onrender.com",
          "X-Title": "ChangePilot",
        }
      : {};

    const cfg: AIProviderConfig = {
      id,
      name: isGroq
        ? `Groq · ${modelMeta?.label ?? targetModel}`
        : isNvidia
        ? `Nvidia NIM · ${modelMeta?.label ?? targetModel}`
        : `OpenRouter · ${modelMeta?.label ?? targetModel}`,
      kind: isGroq ? "groq" : isNvidia ? "nvidia" : "openrouter",
      base_url: baseUrl,
      api_key: apiKey.trim(),
      model: targetModel,
      enabled: true,
      is_default: providers.length === 0,
      priority: 10,
      task_categories: ["report"],
      fallback_provider_ids: [],
      custom_headers: customHeaders,
      temperature: 0.7,
      top_p: isGroq ? undefined : 1.0,
      max_tokens: isGroq ? 4096 : ((modelMeta as any)?.maxTokens ?? 4096),
      timeout_seconds: 90,
    };

    try {
      const res = await fetch(`${getApiBaseUrl()}/ai-providers/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeader() },
        body: JSON.stringify(cfg),
      });
      if (res.ok) {
        fetchProviders();
        closeModal();
      }
    } catch (err) {
    } finally {
      setSavingId(null);
    }
  };

  const modelList =
    modal === "groq"
      ? GROQ_MODELS
      : modal === "nvidia"
      ? NVIDIA_MODELS
      : OPENROUTER_MODELS;

  return (
    <main className="min-h-screen bg-background p-6 text-sm text-foreground">
      <div className="mx-auto flex max-w-7xl flex-col gap-5">
        <header className="flex items-start justify-between gap-4">
          <div>
            <a className="text-sm text-primary hover:underline" href="/">
              ← Back to Dashboard
            </a>
            <h1 className="mt-2 text-2xl font-semibold">AI Provider Settings</h1>
            <p className="mt-1 max-w-2xl text-muted-foreground">
              Manage LLM provider priority, fallbacks, local models (Ollama, LM Studio), and cloud
              endpoints (OpenRouter, Groq, Nvidia NIM, OpenAI).
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button onClick={handleAddDefaultOllama} disabled={savingId === "ollama"} variant="outline">
              <Plus className="size-4 mr-1" />
              Add Local Ollama
            </Button>
            <Button
              onClick={() => openModal("openrouter")}
              disabled={savingId === "openrouter"}
              className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white shadow-sm"
            >
              <Sparkles className="size-4 mr-1" />
              Add OpenRouter
            </Button>
            <Button
              onClick={() => openModal("groq")}
              disabled={savingId === "groq"}
              className="bg-[#F55036] hover:bg-[#d94328] text-white"
            >
              <Plus className="size-4 mr-1" />
              Add Groq
            </Button>
            <Button
              onClick={() => openModal("nvidia")}
              disabled={savingId === "nvidia"}
              className="bg-[#76b900] hover:bg-[#5e9200] text-white"
            >
              <Plus className="size-4 mr-1" />
              Add Nvidia NIM
            </Button>
          </div>
        </header>

        <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Configured AI Providers</CardTitle>
                <CardDescription>Evaluated in priority order with fallback retry policies.</CardDescription>
              </div>
              <label className="flex h-9 w-72 items-center gap-2 rounded-md border border-border bg-surface px-3 text-muted-foreground">
                <Search className="size-4" />
                <input
                  className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none"
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search providers"
                  value={query}
                />
              </label>
            </CardHeader>
            <CardContent>
              {filteredProviders.length === 0 ? (
                <div className="py-12 text-center text-xs text-muted-foreground">
                  No AI providers configured yet. Click{" "}
                  <strong>Add Groq</strong>, <strong>Add Nvidia NIM</strong>, or{" "}
                  <strong>Add Local Ollama</strong> to get started — Groq and Nvidia NIM have
                  generous free tiers.
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {filteredProviders.map((provider) => (
                    <article
                      className="rounded-md border border-border bg-background p-4"
                      key={provider.id}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-start gap-3">
                          <div className="grid size-10 place-items-center rounded-md bg-primary/12 text-primary">
                            <PlugZap />
                          </div>
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <h2 className="font-semibold">{provider.name}</h2>
                              {provider.is_default && <Badge>Default</Badge>}
                              <Badge variant={provider.enabled ? "success" : "secondary"}>
                                {provider.enabled ? "Enabled" : "Disabled"}
                              </Badge>
                              {provider.kind === "groq" && (
                                <Badge variant="outline" className="text-xs border-[#F55036] text-[#F55036]">
                                  ☁ Groq Cloud
                                </Badge>
                              )}
                              {provider.kind === "nvidia" && (
                                <Badge variant="outline" className="text-xs border-[#76b900] text-[#76b900]">
                                  ☁ Nvidia NIM
                                </Badge>
                              )}
                              {provider.kind === "openrouter" && (
                                <Badge variant="outline" className="text-xs border-violet-500 text-violet-400">
                                  ✦ OpenRouter
                                </Badge>
                              )}
                            </div>
                            <p className="mt-1 text-muted-foreground">
                              {provider.kind} · model:{" "}
                              <code className="text-primary">{provider.model}</code> · priority{" "}
                              {provider.priority}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteProvider(provider.id, provider.name)}
                            className="text-muted-foreground hover:text-red-500 hover:bg-red-500/10 p-1.5 h-8 w-8"
                            title="Delete this AI provider"
                            aria-label={`Delete ${provider.name}`}
                          >
                            <Trash2 className="size-4" />
                          </Button>
                          <Switch
                            checked={provider.enabled}
                            onCheckedChange={(enabled) => toggleProvider(provider, enabled)}
                          />
                        </div>
                      </div>
                      {!provider.is_default && (
                        <Button
                          className="mt-4"
                          onClick={() => setDefault(provider)}
                          size="sm"
                          variant="outline"
                        >
                          Select as default
                        </Button>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Supported Providers</CardTitle>
              <CardDescription>Clean Architecture AI Strategy Contracts</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-3 text-xs text-muted-foreground">
                {[
                  "OpenRouter — 100+ models (Nemotron 3.5, Llama 3.3, DeepSeek R1, Gemini 2.0 Flash)",
                  "Groq Cloud — free tier, ultra-fast inference (Llama 3.3 70B, Gemma, Mixtral)",
                  "Nvidia NIM — free tier API endpoints (Nemotron, Llama, Mistral, Phi)",
                  "Ollama (local models like llama3, qwen, deepseek)",
                  "OpenAI-compatible endpoints (vLLM, LM Studio)",
                  "Runtime fallback chain without app restart",
                  "Encrypted API keys & customizable temperature",
                ].map((item) => (
                  <div className="flex items-center gap-2" key={item}>
                    <Check className="size-4 text-emerald-500 shrink-0" />
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>
      </div>

      {/* ── Cloud Provider Quick-Add Modal ── */}
      {modal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={(e) => e.target === e.currentTarget && closeModal()}
        >
          <div className="w-full max-w-md rounded-xl border border-border bg-background p-6 shadow-2xl">
            <h2 className="mb-1 text-lg font-semibold">
              {modal === "openrouter"
                ? "Add OpenRouter Provider"
                : modal === "groq"
                ? "Add Groq Provider"
                : "Add Nvidia NIM Provider"}
            </h2>
            <p className="mb-5 text-xs text-muted-foreground">
              {modal === "openrouter" ? (
                <>
                  Get an API key at{" "}
                  <a
                    className="text-primary underline"
                    href="https://openrouter.ai/keys"
                    rel="noreferrer"
                    target="_blank"
                  >
                    openrouter.ai/keys
                  </a>{" "}
                  — free tier models available.
                </>
              ) : modal === "groq" ? (
                <>
                  Free API key at{" "}
                  <a
                    className="text-primary underline"
                    href="https://console.groq.com/keys"
                    rel="noreferrer"
                    target="_blank"
                  >
                    console.groq.com
                  </a>{" "}
                  — no credit card required.
                </>
              ) : (
                <>
                  Free API key at{" "}
                  <a
                    className="text-primary underline"
                    href="https://build.nvidia.com"
                    rel="noreferrer"
                    target="_blank"
                  >
                    build.nvidia.com
                  </a>{" "}
                  — free tier available.
                </>
              )}
            </p>

            <label className="mb-1 block text-xs font-medium text-foreground">Model</label>
            <select
              className="mb-3 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
            >
              {modelList.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
              <option value="custom">Custom model name…</option>
            </select>

            {selectedModel === "custom" && (
              <input
                className="mb-3 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary"
                onChange={(e) => setCustomModel(e.target.value)}
                placeholder="e.g. nvidia/nemotron-3.5-lightning:free"
                type="text"
                value={customModel}
              />
            )}

            <label className="mb-1 block text-xs font-medium text-foreground">API Key</label>
            <input
              autoFocus
              className="mb-5 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary"
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={modal === "openrouter" ? "sk-or-v1-…" : modal === "groq" ? "gsk_…" : "nvapi-…"}
              type="password"
              value={apiKey}
            />

            <div className="flex justify-end gap-3">
              <Button onClick={closeModal} variant="outline" size="sm">
                Cancel
              </Button>
              <Button
                disabled={
                  !apiKey.trim() ||
                  savingId === modal ||
                  (selectedModel === "custom" && !customModel.trim())
                }
                onClick={handleAddCloudProvider}
                size="sm"
                className={
                  modal === "openrouter"
                    ? "bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white"
                    : modal === "groq"
                    ? "bg-[#F55036] hover:bg-[#d94328] text-white"
                    : "bg-[#76b900] hover:bg-[#5e9200] text-white"
                }
              >
                {savingId === modal ? "Saving…" : "Add Provider"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
