"use client";

import { useState, useRef, useEffect } from "react";
import { Download, FileText, FileJson, FileSpreadsheet, BookOpen, ChevronDown, Loader2, AlertCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getApiBaseUrl } from "@/lib/api-config";
import { authHeader } from "@/lib/auth-client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ExportFormat = "pdf" | "json" | "csv" | "markdown";

interface ExportOption {
  format: ExportFormat;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  mimeType: string;
  extension: string;
}

export interface ExportButtonProps {
  analysisId: string;
  repositoryId: string;
  repositoryName?: string;
  /** Disable all exports (e.g. while analysis is running or incomplete) */
  disabled?: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const EXPORT_OPTIONS: ExportOption[] = [
  {
    format: "pdf",
    label: "PDF",
    description: "Enterprise report with tables & charts",
    icon: FileText,
    mimeType: "application/pdf",
    extension: "pdf",
  },
  {
    format: "json",
    label: "JSON",
    description: "Complete machine-readable analysis",
    icon: FileJson,
    mimeType: "application/json",
    extension: "json",
  },
  {
    format: "csv",
    label: "CSV",
    description: "Data tables as a ZIP archive",
    icon: FileSpreadsheet,
    mimeType: "application/zip",
    extension: "zip",
  },
  {
    format: "markdown",
    label: "Markdown",
    description: "GitHub / PR-friendly report",
    icon: BookOpen,
    mimeType: "text/markdown",
    extension: "md",
  },
];

// ---------------------------------------------------------------------------
// ExportButton
// ---------------------------------------------------------------------------

export function ExportButton({
  analysisId,
  repositoryId,
  repositoryName,
  disabled = false,
}: ExportButtonProps) {
  const [open, setOpen] = useState(false);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  // Auto-dismiss error after 6s
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 6000);
    return () => clearTimeout(t);
  }, [error]);

  const handleExport = async (option: ExportOption) => {
    if (exporting) return;
    setOpen(false);
    setError(null);
    setExporting(option.format);

    try {
      const url = new URL(
        `${getApiBaseUrl()}/analysis/${analysisId}/export/${option.format}`
      );
      url.searchParams.set("repository_id", repositoryId);

      const res = await fetch(url.toString(), {
        method: "GET",
        headers: authHeader(),
      });

      if (!res.ok) {
        let detail = `Export failed (${res.status})`;
        try {
          const body = await res.json();
          detail = body.detail || detail;
        } catch {
          // ignore
        }
        throw new Error(detail);
      }

      // Stream response → blob → download
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const safeName = (repositoryName || repositoryId)
        .replace(/[^\w\-]/g, "_")
        .slice(0, 40);
      anchor.href = objectUrl;
      anchor.download = `${safeName}-${analysisId}.${option.extension}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 5000);
    } catch (err: any) {
      setError(err?.message || "Export failed. Please try again.");
    } finally {
      setExporting(null);
    }
  };

  const isLoading = exporting !== null;
  const isDisabled = disabled || isLoading;

  return (
    <div className="relative flex flex-col gap-1.5" ref={dropdownRef}>
      {/* Error banner */}
      {error && (
        <div
          role="alert"
          className="absolute bottom-full mb-2 left-0 z-50 flex min-w-[240px] max-w-xs items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-700 shadow-lg dark:text-red-400 animate-in fade-in slide-in-from-bottom-2"
        >
          <AlertCircle className="mt-0.5 size-3.5 shrink-0 text-red-500" />
          <span className="flex-1">{error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-1 rounded hover:opacity-70"
            aria-label="Dismiss error"
          >
            <X className="size-3" />
          </button>
        </div>
      )}

      {/* Split button */}
      <div className="flex items-stretch rounded-md shadow-xs">
        {/* Left: trigger icon + label */}
        <Button
          id="export-results-trigger"
          variant="outline"
          size="sm"
          disabled={isDisabled}
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-2 rounded-r-none border-r-0 px-3 font-medium text-xs"
          aria-haspopup="menu"
          aria-expanded={open}
        >
          {isLoading ? (
            <Loader2 className="size-3.5 animate-spin text-primary" />
          ) : (
            <Download className="size-3.5" />
          )}
          {isLoading
            ? `Exporting ${exporting?.toUpperCase()}…`
            : "Export Results"}
        </Button>

        {/* Right: chevron */}
        <Button
          variant="outline"
          size="sm"
          disabled={isDisabled}
          onClick={() => setOpen((v) => !v)}
          className="rounded-l-none border-l px-2"
          aria-label="Choose export format"
        >
          <ChevronDown
            className={`size-3.5 transition-transform duration-150 ${open ? "rotate-180" : ""}`}
          />
        </Button>
      </div>

      {/* Dropdown menu */}
      {open && !isDisabled && (
        <div
          role="menu"
          aria-label="Export format options"
          className="absolute top-full right-0 z-50 mt-1.5 w-56 origin-top-right rounded-xl border border-border bg-popover shadow-xl animate-in fade-in slide-in-from-top-2"
        >
          <div className="p-1">
            {EXPORT_OPTIONS.map((option) => {
              const Icon = option.icon;
              return (
                <button
                  key={option.format}
                  id={`export-format-${option.format}`}
                  role="menuitem"
                  onClick={() => handleExport(option)}
                  disabled={isLoading}
                  className="flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-accent hover:text-accent-foreground focus:outline-none focus:bg-accent disabled:pointer-events-none disabled:opacity-50"
                >
                  <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium leading-none">
                      {option.label}
                    </div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground leading-snug">
                      {option.description}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
          <div className="border-t border-border px-3 py-1.5">
            <p className="text-[10px] text-muted-foreground leading-snug">
              Exports are scoped to this analysis only. Risk scores are never re-computed.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
