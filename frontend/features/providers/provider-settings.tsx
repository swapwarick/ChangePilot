"use client";

import { useEffect, useState } from "react";
import { Download, PlugZap, Plus, Search, Settings2, TestTube2, Upload, Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { AIProviderConfig } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export function AIProviderSettings() {
  const [providers, setProviders] = useState<AIProviderConfig[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const fetchProviders = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/ai-providers`);
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

  const filteredProviders = providers.filter((provider) =>
    `${provider.name} ${provider.kind} ${provider.model}`.toLowerCase().includes(query.toLowerCase())
  );

  const toggleProvider = async (provider: AIProviderConfig, enabled: boolean) => {
    const updated = { ...provider, enabled };
    try {
      const res = await fetch(`${API_BASE}/ai-providers/${provider.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updated)
      });
      if (res.ok) {
        setProviders((curr) => curr.map((p) => (p.id === provider.id ? updated : p)));
      }
    } catch (err) {}
  };

  const setDefault = async (provider: AIProviderConfig) => {
    const updated = { ...provider, is_default: true };
    try {
      const res = await fetch(`${API_BASE}/ai-providers/${provider.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updated)
      });
      if (res.ok) {
        fetchProviders();
      }
    } catch (err) {}
  };

  const handleAddDefaultOllama = async () => {
    setSaving(true);
    const ollamaConfig: AIProviderConfig = {
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
      timeout_seconds: 120
    };

    try {
      const res = await fetch(`${API_BASE}/ai-providers/${ollamaConfig.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ollamaConfig)
      });
      if (res.ok) {
        fetchProviders();
      }
    } catch (err) {
    } finally {
      setSaving(false);
    }
  };

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
              Manage LLM provider priority, fallbacks, local models (Ollama, LM Studio), and cloud endpoints (OpenAI, OpenRouter, Groq, Gemini, Together AI).
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={handleAddDefaultOllama} disabled={saving}>
              <Plus className="size-4 mr-1" />
              Add Local Ollama
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
                  No AI providers configured in PostgreSQL database. Click <strong>Add Local Ollama</strong> to create one.
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  {filteredProviders.map((provider) => (
                    <article className="rounded-md border border-border bg-background p-4" key={provider.id}>
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex items-start gap-3">
                          <div className="grid size-10 place-items-center rounded-md bg-primary/12 text-primary">
                            <PlugZap />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <h2 className="font-semibold">{provider.name}</h2>
                              {provider.is_default && <Badge>Default</Badge>}
                              <Badge variant={provider.enabled ? "success" : "secondary"}>
                                {provider.enabled ? "Enabled" : "Disabled"}
                              </Badge>
                            </div>
                            <p className="mt-1 text-muted-foreground">
                              {provider.kind} · model: <code className="text-primary">{provider.model}</code> · priority {provider.priority}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <Switch
                            checked={provider.enabled}
                            onCheckedChange={(enabled) => toggleProvider(provider, enabled)}
                          />
                        </div>
                      </div>
                      {!provider.is_default && (
                        <Button className="mt-4" onClick={() => setDefault(provider)} size="sm" variant="outline">
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
                  "Ollama (local models like llama3, qwen, deepseek)",
                  "OpenAI-compatible endpoints (vLLM, LM Studio)",
                  "OpenRouter, Groq, Together AI, Gemini",
                  "Runtime fallback chain without app restart",
                  "Encrypted API keys & customizable temperature"
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
    </main>
  );
}
