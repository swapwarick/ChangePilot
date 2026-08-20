"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import {
  Download,
  FileText,
  FileJson,
  FileSpreadsheet,
  BookOpen,
  ChevronDown,
  Loader2,
  AlertCircle,
  X,
} from "lucide-react";
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

/** Max time (ms) to wait for the backend before aborting */
const FETCH_TIMEOUT_MS = 30_000;

/** Max number of automatic retries on network errors (e.g. cold-start on Render free tier) */
const MAX_RETRIES = 2;

/** Delay between retries in ms */
const RETRY_DELAY_MS = 2_500;

// ---------------------------------------------------------------------------
// Global error toast — rendered at app root via ExportErrorToast component,
// bypassing any overflow-clipped table containers.
// ---------------------------------------------------------------------------

type ToastState = { id: string; message: string } | null;
let _setGlobalToast: ((s: ToastState) => void) | null = null;

function showGlobalToast(message: string) {
  if (_setGlobalToast) {
    const id = Math.random().toString(36).slice(2);
    _setGlobalToast({ id, message });
  }
}

/**
 * Mount this once at the app root (e.g. in AppProviders) to display export
 * errors in a fixed-position overlay above all content.
 */
export function ExportErrorToast() {
  const [toast, setToast] = useState<ToastState>(null);
  _setGlobalToast = setToast;

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 8_000);
    return () => clearTimeout(t);
  }, [toast]);

  if (!toast) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="fixed bottom-5 right-5 z-[9999] flex min-w-[280px] max-w-sm items-start gap-3 rounded-xl border border-red-500/30 bg-red-950/90 px-4 py-3 text-sm text-red-300 shadow-2xl backdrop-blur-sm animate-in fade-in slide-in-from-bottom-4"
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0 text-red-400" />
      <div className="flex-1 leading-snug">
        <p className="font-medium text-red-200">Export failed</p>
        <p className="mt-0.5 text-xs text-red-400">{toast.message}</p>
      </div>
      <button
        onClick={() => setToast(null)}
        className="ml-1 rounded opacity-70 hover:opacity-100 transition-opacity"
        aria-label="Dismiss"
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Fetch helper with timeout + retry for Render free-tier cold-starts
// ---------------------------------------------------------------------------

async function fetchWithRetry(
  url: string,
  init: RequestInit,
  retries = MAX_RETRIES
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    const res = await fetch(url, { ...init, signal: controller.signal });
    clearTimeout(timer);
    return res;
  } catch (err: any) {
    clearTimeout(timer);
    const isNetworkErr =
      err?.name === "TypeError" ||
      err?.name === "AbortError" ||
      err?.message?.toLowerCase().includes("failed to fetch") ||
      err?.message?.toLowerCase().includes("network");

    if (isNetworkErr && retries > 0) {
      await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
      return fetchWithRetry(url, init, retries - 1);
    }
    throw err;
  }
}

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
  const [dropdownPos, setDropdownPos] = useState<{ top: number; left: number } | null>(null);
  const buttonGroupRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);

  // Only render portal on the client (avoid SSR mismatch)
  useEffect(() => { setMounted(true); }, []);

  // Close dropdown when clicking outside both the button and the portal dropdown
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      const inButton = buttonGroupRef.current?.contains(target);
      const inDropdown = dropdownRef.current?.contains(target);
      if (!inButton && !inDropdown) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  // Close dropdown on scroll/resize since the portal position would be stale
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  const toggleOpen = () => {
    if (open) { setOpen(false); return; }
    if (buttonGroupRef.current) {
      const rect = buttonGroupRef.current.getBoundingClientRect();
      // Position dropdown below and right-aligned to the button group
      setDropdownPos({
        top: rect.bottom + 6,
        left: Math.max(8, rect.right - 224), // 224px = w-56
      });
    }
    setOpen(true);
  };

  const handleExport = useCallback(
    async (option: ExportOption) => {
      if (exporting) return;
      setOpen(false);
      setExporting(option.format);

      try {
        const url = new URL(
          `${getApiBaseUrl()}/analysis/${analysisId}/export/${option.format}`
        );
        url.searchParams.set("repository_id", repositoryId);

        const res = await fetchWithRetry(url.toString(), {
          method: "GET",
          headers: authHeader(),
        });

        if (!res.ok) {
          let detail = `Server returned ${res.status}`;
          try {
            const body = await res.json();
            detail = body.detail || detail;
          } catch {
            // ignore JSON parse error on non-JSON error responses
          }
          throw new Error(detail);
        }

        // Stream response → blob → anchor download
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
        setTimeout(() => URL.revokeObjectURL(objectUrl), 5_000);
      } catch (err: any) {
        const isNetwork =
          err?.name === "TypeError" ||
          err?.name === "AbortError" ||
          err?.message?.toLowerCase().includes("failed to fetch") ||
          err?.message?.toLowerCase().includes("network");

        showGlobalToast(
          isNetwork
            ? "Could not reach the API. The server may be starting up — please retry in a moment."
            : err?.message || "Export failed. Please try again."
        );
      } finally {
        setExporting(null);
      }
    },
    [analysisId, repositoryId, repositoryName, exporting]
  );

  const isLoading = exporting !== null;
  const isDisabled = disabled || isLoading;

  // Dropdown rendered via portal to break out of overflow-x:auto table containers
  const dropdown =
    open && !isDisabled && dropdownPos && mounted
      ? createPortal(
          <div
            ref={dropdownRef}
            role="menu"
            aria-label="Export format options"
            style={{ top: dropdownPos.top, left: dropdownPos.left }}
            className="fixed z-[9998] w-56 rounded-xl border border-border bg-popover shadow-2xl animate-in fade-in slide-in-from-top-2"
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
                      <div className="text-sm font-medium leading-none">{option.label}</div>
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
                Exports are scoped to this analysis. Risk scores are never re-computed.
              </p>
            </div>
          </div>,
          document.body
        )
      : null;

  return (
    <>
      <div className="flex items-center" ref={buttonGroupRef}>
        {/* Split button */}
        <div className="flex items-stretch rounded-md shadow-xs">
          {/* Left: trigger icon + label */}
          <Button
            id="export-results-trigger"
            variant="outline"
            size="sm"
            disabled={isDisabled}
            onClick={toggleOpen}
            className="flex items-center gap-2 rounded-r-none border-r-0 px-3 font-medium text-xs"
            aria-haspopup="menu"
            aria-expanded={open}
          >
            {isLoading ? (
              <Loader2 className="size-3.5 animate-spin text-primary" />
            ) : (
              <Download className="size-3.5" />
            )}
            {isLoading ? `Exporting ${exporting?.toUpperCase()}…` : "Export Results"}
          </Button>

          {/* Right: chevron */}
          <Button
            variant="outline"
            size="sm"
            disabled={isDisabled}
            onClick={toggleOpen}
            className="rounded-l-none border-l px-2"
            aria-label="Choose export format"
          >
            <ChevronDown
              className={`size-3.5 transition-transform duration-150 ${open ? "rotate-180" : ""}`}
            />
          </Button>
        </div>
      </div>

      {/* Portal renders dropdown at document.body — breaks out of overflow-clipped containers */}
      {dropdown}
    </>
  );
}
