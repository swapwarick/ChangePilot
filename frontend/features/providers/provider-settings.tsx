"use client";

import { startTransition, useDeferredValue, useState } from "react";
import { Download, PlugZap, Plus, Search, Settings2, TestTube2, Upload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { providers as seedProviders } from "@/features/dashboard/data";

export function AIProviderSettings() {
  const [providers, setProviders] = useState(seedProviders);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);

  const filteredProviders = providers.filter((provider) =>
    `${provider.name} ${provider.kind} ${provider.model}`.toLowerCase().includes(deferredQuery.toLowerCase())
  );

  function toggleProvider(providerId: string, enabled: boolean) {
    startTransition(() => {
      setProviders((current) =>
        current.map((provider) => (provider.id === providerId ? { ...provider, enabled } : provider))
      );
    });
  }

  function setDefault(providerId: string) {
    startTransition(() => {
      setProviders((current) =>
        current.map((provider) => ({ ...provider, default: provider.id === providerId }))
      );
    });
  }

  return (
    <main className="min-h-screen bg-background p-6 text-sm">
      <div className="mx-auto flex max-w-7xl flex-col gap-5">
        <header className="flex items-start justify-between gap-4">
          <div>
            <a className="text-sm text-primary" href="/">
              ChangePilot
            </a>
            <h1 className="mt-2 text-2xl font-semibold">AI provider settings</h1>
            <p className="mt-1 max-w-2xl text-muted-foreground">
              Manage provider priority, fallbacks, local models, OpenAI-compatible endpoints, and task-level defaults.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline">
              <Upload data-icon="inline-start" />
              Import
            </Button>
            <Button variant="outline">
              <Download data-icon="inline-start" />
              Export
            </Button>
            <Button>
              <Plus data-icon="inline-start" />
              Add provider
            </Button>
          </div>
        </header>

        <section className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Configured providers</CardTitle>
                <CardDescription>Providers are evaluated by enabled state, task routing, priority, and fallback chain.</CardDescription>
              </div>
              <label className="flex h-9 w-72 items-center gap-2 rounded-md border border-border bg-surface px-3 text-muted-foreground">
                <Search data-icon="inline-start" />
                <input
                  className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none"
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search providers"
                  value={query}
                />
              </label>
            </CardHeader>
            <CardContent>
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
                            {provider.default ? <Badge>Default</Badge> : null}
                            <Badge variant={provider.status === "healthy" ? "success" : "warning"}>
                              {provider.status}
                            </Badge>
                          </div>
                          <p className="mt-1 text-muted-foreground">
                            {provider.kind} · {provider.model} · priority {provider.priority}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <Switch
                          checked={provider.enabled}
                          onCheckedChange={(enabled) => toggleProvider(provider.id, enabled)}
                        />
                        <Button size="sm" variant="outline">
                          <TestTube2 data-icon="inline-start" />
                          Test
                        </Button>
                        <Button size="sm" variant="ghost">
                          <Settings2 data-icon="inline-start" />
                          Edit
                        </Button>
                      </div>
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-4">
                      <div className="rounded-md border border-border bg-surface p-3">
                        <div className="text-xs text-muted-foreground">Timeout</div>
                        <div className="mt-1 font-medium">30s</div>
                      </div>
                      <div className="rounded-md border border-border bg-surface p-3">
                        <div className="text-xs text-muted-foreground">Retry policy</div>
                        <div className="mt-1 font-medium">2 attempts</div>
                      </div>
                      <div className="rounded-md border border-border bg-surface p-3">
                        <div className="text-xs text-muted-foreground">Fallback</div>
                        <div className="mt-1 font-medium">Next priority</div>
                      </div>
                      <div className="rounded-md border border-border bg-surface p-3">
                        <div className="text-xs text-muted-foreground">Temperature</div>
                        <div className="mt-1 font-medium">0.2</div>
                      </div>
                    </div>
                    {!provider.default ? (
                      <Button className="mt-4" onClick={() => setDefault(provider.id)} size="sm" variant="outline">
                        Select as default
                      </Button>
                    ) : null}
                  </article>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Provider contract</CardTitle>
              <CardDescription>All providers implement the same strategy interface.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-4 text-sm">
                {[
                  "OpenAI-compatible base URL and model routing",
                  "Ollama offline local model support",
                  "Custom headers and optional API keys",
                  "Runtime fallback chain without restart",
                  "Connectivity tests and model listing"
                ].map((item) => (
                  <div className="flex items-start gap-3" key={item}>
                    <span className="mt-1 size-2 rounded-full bg-primary" />
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

