"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { AuthProvider } from "@/lib/auth-context";
import { ExportErrorToast } from "@/features/analysis/export-button";
import { ABDevTools } from "@/components/ab-devtools";

export function AppProviders({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1
          }
        }
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
      {/* Global fixed-position toast for export errors */}
      <ExportErrorToast />
      {/* A/B Testing DevTools — only visible in dev or with ?ab_devtools=1 */}
      <ABDevTools />
    </QueryClientProvider>
  );
}

