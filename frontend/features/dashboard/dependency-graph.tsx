"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import "@xyflow/react/dist/style.css";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  Handle,
  Position,
  MarkerType,
  type Edge,
  type Node,
  type NodeProps
} from "@xyflow/react";
import {
  Maximize2,
  Minimize2,
  Search,
  Layers,
  Zap,
  Box,
  FileCode,
  Folder,
  Package,
  Code2,
  GitBranch,
  X,
  Filter
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { GraphNode, GraphEdge } from "@/types/api";

interface DependencyGraphProps {
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  graphHealth?: {
    node_count?: number;
    edge_count?: number;
    self_edge_count?: number;
    duplicate_edge_count?: number;
    unresolved_imports?: number;
    circular_dependency_count?: number;
    orphan_candidates?: number;
    invalid_paths?: number;
    warnings?: string[];
  };
}

// ---- Edge type configuration ------------------------------------------------
const EDGE_TYPE_CONFIG: Record<string, { color: string; label: string; description: string; dashArray?: string }> = {
  SOURCE_IMPORT:      { color: "#6366f1", label: "IMPORTS",      description: "AST source import relationship" },
  DYNAMIC_IMPORT:     { color: "#8b5cf6", label: "DYN IMPORT",   description: "Dynamic import() relationship",   dashArray: "6 3" },
  DEPENDS_ON:         { color: "#3b82f6", label: "DEPENDS_ON",   description: "Internal/module dependency" },
  PACKAGE_DEPENDENCY: { color: "#f59e0b", label: "PACKAGE DEP",  description: "package.json / requirements dependency", dashArray: "4 2" },
  CALLS:              { color: "#10b981", label: "CALLS",         description: "Function/method call relationship" },
  TEST_REFERENCE:     { color: "#22d3ee", label: "TEST REF",      description: "Test-to-source relationship",      dashArray: "5 3" },
  ROUTE_REFERENCE:    { color: "#f97316", label: "ROUTE REF",     description: "Route-to-handler relationship" },
  CONFIG_REFERENCE:   { color: "#94a3b8", label: "CONFIG REF",    description: "Configuration relationship",       dashArray: "3 3" },
  BUILD_DEPENDENCY:   { color: "#64748b", label: "BUILD DEP",     description: "Build tool dependency",            dashArray: "2 4" },
  SELF_IMPORT:        { color: "#ef4444", label: "SELF IMPORT",   description: "Self-referencing import (ignored)" },
  IMPORTS:            { color: "#6366f1", label: "IMPORTS",       description: "AST source import relationship" },
};

const DEFAULT_EDGE_COLOR = "#6366f1";

function getEdgeConfig(edgeType?: string, relationship?: string) {
  const key = edgeType || relationship || "IMPORTS";
  return EDGE_TYPE_CONFIG[key] ?? { color: DEFAULT_EDGE_COLOR, label: key, description: key };
}

// ---- Default visible edge types (exclude package/config noise by default) ---
const DEFAULT_VISIBLE_EDGE_TYPES = new Set([
  "SOURCE_IMPORT", "IMPORTS", "DYNAMIC_IMPORT", "DEPENDS_ON", "CALLS", "TEST_REFERENCE", "ROUTE_REFERENCE",
]);

// ---- Folder metric computation (pure, runs once per graph) ------------------
interface FolderMetrics {
  fileCount: number;
  fanIn: number;   // distinct external importers
  fanOut: number;  // distinct external/internal targets from this folder
  internalDeps: number;  // edges where both src and tgt are inside folder
  externalDeps: number;  // edges where src is inside, tgt is outside
  blastRadius: number;   // nodes transitively affected by changing any file in folder
}

function computeFolderMetrics(
  folderPath: string,
  allNodes: GraphNode[],
  resolvedEdges: GraphEdge[]
): FolderMetrics {
  // Collect file node IDs that belong to this folder
  const folderNodeIds = new Set<string>(
    allNodes
      .filter((n) => n.path && n.path.startsWith(folderPath + "/"))
      .map((n) => n.id)
  );

  const fileCount = folderNodeIds.size;
  if (fileCount === 0) {
    return { fileCount: 0, fanIn: 0, fanOut: 0, internalDeps: 0, externalDeps: 0, blastRadius: 0 };
  }

  const externalImporters = new Set<string>(); // external nodes that import INTO this folder
  const externalTargets = new Set<string>();   // external nodes that this folder imports
  let internalDeps = 0;
  let externalDeps = 0;

  for (const edge of resolvedEdges) {
    const srcInFolder = folderNodeIds.has(edge.source);
    const tgtInFolder = folderNodeIds.has(edge.target);

    if (srcInFolder && tgtInFolder) {
      internalDeps++;
    } else if (srcInFolder && !tgtInFolder) {
      externalDeps++;
      externalTargets.add(edge.target);
    } else if (!srcInFolder && tgtInFolder) {
      externalImporters.add(edge.source);
    }
  }

  // Simple blast radius: BFS from all folder nodes following reverse edges
  const reverseAdj = new Map<string, Set<string>>();
  for (const edge of resolvedEdges) {
    if (!reverseAdj.has(edge.target)) reverseAdj.set(edge.target, new Set());
    reverseAdj.get(edge.target)!.add(edge.source);
  }

  const visited = new Set<string>([...folderNodeIds]);
  const queue = [...folderNodeIds];
  while (queue.length > 0) {
    const cur = queue.shift()!;
    for (const dep of reverseAdj.get(cur) ?? []) {
      if (!visited.has(dep)) {
        visited.add(dep);
        queue.push(dep);
      }
    }
  }
  const blastRadius = visited.size - fileCount; // exclude folder's own files

  return {
    fileCount,
    fanIn: externalImporters.size,
    fanOut: externalTargets.size,
    internalDeps,
    externalDeps,
    blastRadius,
  };
}

// ---- Edge type counts (for Graph Health panel) ------------------------------
function computeEdgeTypeCounts(edges: GraphEdge[]) {
  const counts: Record<string, number> = {};
  for (const e of edges) {
    const key = e.edge_type || e.relationship || "UNKNOWN";
    counts[key] = (counts[key] ?? 0) + 1;
  }
  return counts;
}

// ---- Custom graph node -------------------------------------------------------
function CustomGraphNode({ data }: NodeProps) {
  const {
    label,
    kind,
    path,
    fan_in = 0,
    fan_out = 0,
    is_critical,
    isHighlighted,
    isDimmed,
    isSelected,
    blastDepth,
  } = data as {
    label: string;
    kind: string;
    path?: string;
    fan_in?: number;
    fan_out?: number;
    is_critical?: boolean;
    isHighlighted?: boolean;
    isDimmed?: boolean;
    isSelected?: boolean;
    blastDepth?: number; // 0=changed, 1=direct, 2=indirect, 3=tertiary
  };

  const getStyle = () => {
    if (blastDepth === 0)
      return "border-red-500 bg-red-950/40 text-red-200 font-bold shadow-xl ring-2 ring-red-500";
    if (blastDepth === 1)
      return "border-orange-500 bg-orange-950/30 text-orange-200 font-semibold shadow-lg ring-1 ring-orange-400";
    if (blastDepth === 2)
      return "border-yellow-500/80 bg-yellow-950/20 text-yellow-200 shadow-md ring-1 ring-yellow-400/50";
    if (blastDepth === 3)
      return "border-amber-400/60 bg-amber-950/10 text-amber-200 shadow-sm";

    if (is_critical || kind === "api")
      return "border-red-500/80 bg-red-950/20 text-red-900 dark:text-red-200 font-semibold shadow-md ring-1 ring-red-500/30";
    if (kind === "database")
      return "border-orange-500/80 bg-orange-950/20 text-orange-900 dark:text-orange-200 font-semibold shadow-md ring-1 ring-orange-500/30";
    if (kind === "module")
      return "border-amber-500/80 bg-amber-950/20 text-amber-900 dark:text-amber-200 font-bold shadow-md ring-1 ring-amber-500/30";
    if (kind === "folder")
      return "border-yellow-500/70 bg-yellow-950/15 text-yellow-900 dark:text-yellow-200 font-bold shadow-md ring-1 ring-yellow-400/40";
    if (kind === "package")
      return "border-sky-500/70 bg-sky-950/15 text-sky-900 dark:text-sky-200 font-medium shadow-sm";
    const p = (path || label).toLowerCase();
    if (p.includes("test") || p.includes("spec"))
      return "border-emerald-500/80 bg-emerald-950/20 text-emerald-900 dark:text-emerald-200 font-medium shadow-sm";
    if (kind === "class" || kind === "function" || kind === "file")
      return "border-blue-500/80 bg-blue-950/20 text-blue-900 dark:text-blue-200 font-medium shadow-sm";
    return "border-border/90 bg-card text-card-foreground shadow-xs hover:shadow-md transition-all";
  };

  const opacityClass = isDimmed
    ? "opacity-15 scale-95"
    : isSelected
    ? "scale-105 ring-2 ring-indigo-500 z-50 shadow-xl"
    : isHighlighted
    ? "scale-105 ring-2 ring-indigo-400 z-40 shadow-lg"
    : "opacity-100";

  const KindIcon = () => {
    if (kind === "folder") return <Folder className="size-3.5 text-yellow-500 shrink-0" />;
    if (kind === "module") return <Box className="size-3.5 text-amber-500 shrink-0" />;
    if (kind === "package") return <Package className="size-3.5 text-sky-500 shrink-0" />;
    if (kind === "api") return <Zap className="size-3.5 text-red-500 shrink-0" />;
    if (kind === "class") return <Code2 className="size-3.5 text-purple-500 shrink-0" />;
    if (kind === "function") return <GitBranch className="size-3.5 text-green-500 shrink-0" />;
    return <FileCode className="size-3.5 text-indigo-500 shrink-0" />;
  };

  return (
    <div className={`relative px-3.5 py-2.5 rounded-xl border w-[240px] cursor-pointer transition-all duration-200 ${getStyle()} ${opacityClass}`}>
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !bg-indigo-500 !border-2 !border-background hover:!scale-125 transition-transform"
      />

      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <KindIcon />
          <span className="font-semibold text-xs truncate" title={label}>
            {label}
          </span>
        </div>
        <span className="text-[9px] uppercase font-mono px-1.5 py-0.5 rounded-md border shrink-0 bg-muted/80 text-muted-foreground border-border/50">
          {kind}
        </span>
      </div>

      {path && path !== label && (
        <div className="text-[10px] text-muted-foreground/80 font-mono truncate mt-1 pl-5" title={path}>
          {path}
        </div>
      )}

      {(fan_in > 0 || fan_out > 0) && (
        <div className="flex items-center gap-2 mt-1.5 pt-1.5 border-t border-border/40 text-[9px] font-mono text-muted-foreground">
          <span>In: <strong className="text-foreground">{fan_in}</strong></span>
          <span>Out: <strong className="text-foreground">{fan_out}</strong></span>
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-indigo-500 !border-2 !border-background hover:!scale-125 transition-transform"
      />
    </div>
  );
}

// ---- Edge type filter toggle button -----------------------------------------
function EdgeTypeToggle({
  edgeType,
  active,
  count,
  onToggle,
}: {
  edgeType: string;
  active: boolean;
  count: number;
  onToggle: () => void;
}) {
  const config = EDGE_TYPE_CONFIG[edgeType] ?? { color: DEFAULT_EDGE_COLOR, label: edgeType, description: edgeType };
  return (
    <button
      onClick={onToggle}
      title={config.description}
      className={`flex items-center gap-1.5 px-2 py-1 rounded border text-[10px] font-mono transition-all ${
        active
          ? "border-indigo-500/60 bg-indigo-500/10 text-foreground"
          : "border-border/50 bg-muted/20 text-muted-foreground opacity-60"
      }`}
    >
      <span
        className="inline-block size-2 rounded-full shrink-0"
        style={{ background: config.color }}
      />
      {config.label} {count > 0 && <span className="opacity-60">({count})</span>}
    </button>
  );
}

// ---- Graph Legend panel -----------------------------------------------------
function GraphLegend({ edgeTypeCounts }: { edgeTypeCounts: Record<string, number> }) {
  const relevantTypes = Object.entries(EDGE_TYPE_CONFIG).filter(([key]) => edgeTypeCounts[key] > 0);
  if (relevantTypes.length === 0) return null;

  return (
    <div className="absolute bottom-12 left-3 z-30 bg-background/95 backdrop-blur border border-border/80 rounded-lg p-2.5 shadow-lg">
      <div className="text-[10px] font-semibold text-muted-foreground mb-2 uppercase tracking-wide">Legend</div>
      <div className="space-y-1.5">
        {relevantTypes.map(([key, cfg]) => (
          <div key={key} className="flex items-center gap-2 text-[10px]">
            <svg width="20" height="8">
              <line
                x1="0" y1="4" x2="20" y2="4"
                stroke={cfg.color}
                strokeWidth="1.5"
                strokeDasharray={cfg.dashArray ?? "none"}
              />
              <polygon points="15,1 20,4 15,7" fill={cfg.color} />
            </svg>
            <span className="text-muted-foreground" title={cfg.description}>{cfg.label}</span>
            <span className="text-muted-foreground/60">({edgeTypeCounts[key]})</span>
          </div>
        ))}
      </div>

      {/* Node type legend */}
      <div className="mt-2.5 pt-2 border-t border-border/50 space-y-1">
        <div className="text-[10px] font-semibold text-muted-foreground">Node Types</div>
        {[
          { color: "#f59e0b", label: "Module / Folder" },
          { color: "#ef4444", label: "API / Critical" },
          { color: "#6366f1", label: "File / Class" },
          { color: "#22d3ee", label: "Test" },
          { color: "#0ea5e9", label: "Package" },
          { color: "#ef4444", label: "Blast: Changed", ring: true },
          { color: "#f97316", label: "Blast: Direct" },
          { color: "#eab308", label: "Blast: Indirect" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-2 text-[10px]">
            <span className="inline-block size-2.5 rounded-full shrink-0" style={{ background: color }} />
            <span className="text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Graph Health panel in toolbar ------------------------------------------
function GraphHealthBadge({
  graphHealth,
  edgeTypeCounts,
  totalNodes,
  totalEdges,
}: {
  graphHealth?: DependencyGraphProps["graphHealth"];
  edgeTypeCounts: Record<string, number>;
  totalNodes: number;
  totalEdges: number;
}) {
  const [expanded, setExpanded] = useState(false);

  const sourceImports = (edgeTypeCounts["SOURCE_IMPORT"] ?? 0) + (edgeTypeCounts["IMPORTS"] ?? 0);
  const dynamicImports = edgeTypeCounts["DYNAMIC_IMPORT"] ?? 0;
  const packageDeps = edgeTypeCounts["PACKAGE_DEPENDENCY"] ?? 0;
  const configRefs = edgeTypeCounts["CONFIG_REFERENCE"] ?? 0;
  const selfImports = graphHealth?.self_edge_count ?? 0;
  const circular = graphHealth?.circular_dependency_count ?? 0;
  const unresolved = graphHealth?.unresolved_imports ?? 0;

  return (
    <div className="relative">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 h-8 px-2.5 rounded-lg border border-border/80 bg-background text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <Layers className="size-3.5" />
        <span className="hidden sm:inline">Nodes: <strong className="text-foreground">{totalNodes}</strong></span>
        <span className="hidden sm:inline">· Edges: <strong className="text-foreground">{totalEdges}</strong></span>
        {circular > 0 && <span className="text-amber-500 font-semibold">⚠ {circular} cycles</span>}
      </button>

      {expanded && (
        <div className="absolute top-10 right-0 z-50 bg-background border border-border/80 rounded-lg shadow-xl p-3 w-64">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold">Graph Health</span>
            <button onClick={() => setExpanded(false)}><X className="size-3.5 text-muted-foreground" /></button>
          </div>
          <div className="space-y-1.5 text-[11px] font-mono">
            {[
              ["Nodes", totalNodes],
              ["Source Imports", sourceImports],
              ["Dynamic Imports", dynamicImports],
              ["Package Deps", packageDeps],
              ["Config Refs", configRefs],
              ["Self Imports", selfImports, selfImports > 0 ? "text-amber-500" : ""],
              ["Circular Deps", circular, circular > 0 ? "text-red-500" : "text-emerald-500"],
              ["Unresolved", unresolved, unresolved > 0 ? "text-amber-500" : ""],
            ].map(([label, val, cls]) => (
              <div key={String(label)} className="flex justify-between items-center border-b border-border/30 pb-1">
                <span className="text-muted-foreground">{label}</span>
                <span className={`font-bold ${cls || "text-foreground"}`}>{val}</span>
              </div>
            ))}
          </div>
          {graphHealth?.warnings && graphHealth.warnings.length > 0 && (
            <div className="mt-2 pt-2 border-t border-border/50">
              <div className="text-[10px] text-amber-500 font-semibold mb-1">Warnings</div>
              {graphHealth.warnings.map((w, i) => (
                <div key={i} className="text-[10px] text-muted-foreground">{w}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---- Node Inspector Drawer --------------------------------------------------
function NodeInspector({
  selectedNode,
  allNodes,
  resolvedEdges,
  blastMap,
  onClose,
}: {
  selectedNode: GraphNode;
  allNodes: GraphNode[];
  resolvedEdges: GraphEdge[];
  blastMap: Map<string, number>;
  onClose: () => void;
}) {
  const kind = selectedNode.kind;

  // Compute direct importers/importees from resolved edges
  const directDependents = useMemo(() => {
    return resolvedEdges
      .filter((e) => e.target === selectedNode.id && !["CONFIG_REFERENCE", "BUILD_DEPENDENCY", "PACKAGE_DEPENDENCY"].includes(e.edge_type ?? ""))
      .map((e) => e.source);
  }, [selectedNode.id, resolvedEdges]);

  const directDependencies = useMemo(() => {
    return resolvedEdges
      .filter((e) => e.source === selectedNode.id && !["CONFIG_REFERENCE", "BUILD_DEPENDENCY", "PACKAGE_DEPENDENCY"].includes(e.edge_type ?? ""))
      .map((e) => e.target);
  }, [selectedNode.id, resolvedEdges]);

  const blastCounts = useMemo(() => {
    let direct = 0, indirect = 0, tertiary = 0;
    blastMap.forEach((depth) => {
      if (depth === 1) direct++;
      else if (depth === 2) indirect++;
      else if (depth === 3) tertiary++;
    });
    return { direct, indirect, tertiary, total: blastMap.size };
  }, [blastMap]);

  // Folder-specific aggregated metrics
  const folderMetrics = useMemo(() => {
    if (kind !== "folder" && kind !== "module") return null;
    const folderPath = selectedNode.path || selectedNode.label;

    // Build resolved edge list from all edges
    return computeFolderMetrics(folderPath, allNodes, resolvedEdges);
  }, [kind, selectedNode, allNodes, resolvedEdges]);

  const labelForNode = useCallback((id: string) => {
    const n = allNodes.find((n) => n.id === id);
    return n ? (n.path || n.label) : id;
  }, [allNodes]);

  const isFolder = kind === "folder" || kind === "module";

  return (
    <div className="w-[320px] border-l border-border bg-card p-4 overflow-y-auto z-40 text-card-foreground flex flex-col gap-3 shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-3">
        <div className="min-w-0">
          <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
            {kind}
          </span>
          <h3 className="text-sm font-semibold mt-1.5 truncate" title={selectedNode.label}>
            {selectedNode.label}
          </h3>
        </div>
        <button onClick={onClose} className="shrink-0 p-1 hover:bg-muted rounded">
          <X className="size-4 text-muted-foreground" />
        </button>
      </div>

      {/* Full path */}
      <div>
        <div className="text-[10px] font-medium text-muted-foreground mb-1">{isFolder ? "Folder Path" : "File Path"}</div>
        <div className="font-mono text-[10px] bg-muted/40 p-2 rounded border break-all">
          {selectedNode.path || selectedNode.label}
        </div>
      </div>

      {/* Language (file only) */}
      {selectedNode.language && !isFolder && (
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Language</span>
          <span className="font-mono">{selectedNode.language}</span>
        </div>
      )}

      {/* Folder/Module metrics */}
      {isFolder && folderMetrics && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <MetricBox label="Files" value={folderMetrics.fileCount} color="text-foreground" />
            <MetricBox label="Blast Radius" value={folderMetrics.blastRadius} color="text-red-500" suffix=" files" />
            <MetricBox label="Fan-In (external importers)" value={folderMetrics.fanIn} color="text-indigo-500" />
            <MetricBox label="Fan-Out (external targets)" value={folderMetrics.fanOut} color="text-purple-500" />
            <MetricBox label="Internal Deps" value={folderMetrics.internalDeps} color="text-emerald-500" />
            <MetricBox label="External Deps" value={folderMetrics.externalDeps} color="text-amber-500" />
          </div>
          <div className="text-[10px] text-muted-foreground bg-muted/30 rounded p-2 border border-border/50">
            Fan-In = distinct external files importing into this folder.<br />
            Fan-Out = distinct external targets this folder imports.<br />
            Internal edges between sibling files are excluded from Fan-In/Fan-Out.
          </div>
        </>
      )}

      {/* File metrics */}
      {!isFolder && (
        <>
          <div className="grid grid-cols-2 gap-2">
            <MetricBox label="Fan-In (importers)" value={directDependents.length} color="text-indigo-500" />
            <MetricBox label="Fan-Out (imports)" value={directDependencies.length} color="text-purple-500" />
          </div>

          {/* Blast radius */}
          {blastCounts.total > 0 && (
            <div>
              <div className="text-[10px] font-medium text-muted-foreground mb-1">Blast Radius</div>
              <div className="grid grid-cols-3 gap-1.5">
                <div className="rounded border bg-orange-500/10 border-orange-500/30 p-1.5 text-center">
                  <div className="text-[10px] text-orange-500">Direct</div>
                  <div className="font-bold text-sm text-orange-600">{blastCounts.direct}</div>
                </div>
                <div className="rounded border bg-yellow-500/10 border-yellow-500/30 p-1.5 text-center">
                  <div className="text-[10px] text-yellow-500">Indirect</div>
                  <div className="font-bold text-sm text-yellow-600">{blastCounts.indirect}</div>
                </div>
                <div className="rounded border bg-muted/30 border-border/50 p-1.5 text-center">
                  <div className="text-[10px] text-muted-foreground">Total</div>
                  <div className="font-bold text-sm">{blastCounts.total}</div>
                </div>
              </div>
            </div>
          )}

          {/* Direct dependencies */}
          {directDependencies.length > 0 && (
            <CollapsibleList
              title={`Imports (${directDependencies.length})`}
              items={directDependencies.slice(0, 15).map(labelForNode)}
              color="text-purple-500"
            />
          )}

          {/* Direct dependents */}
          {directDependents.length > 0 && (
            <CollapsibleList
              title={`Imported By (${directDependents.length})`}
              items={directDependents.slice(0, 15).map(labelForNode)}
              color="text-indigo-500"
            />
          )}
        </>
      )}

      {/* Metadata */}
      {selectedNode.metadata && Object.keys(selectedNode.metadata).length > 0 && (
        <div>
          <div className="text-[10px] font-medium text-muted-foreground mb-1">AST Symbols</div>
          <div className="space-y-0.5 font-mono text-[10px]">
            {Object.entries(selectedNode.metadata).slice(0, 8).map(([k, v]) =>
              v ? (
                <div key={k} className="border-b border-border/30 py-0.5 flex justify-between">
                  <span className="text-muted-foreground capitalize">{k}:</span>
                  <span className="text-foreground truncate max-w-[160px]" title={String(v)}>{String(v)}</span>
                </div>
              ) : null
            )}
          </div>
        </div>
      )}

      <Button className="w-full mt-2 text-xs" variant="outline" size="sm" onClick={onClose}>
        Close Inspector
      </Button>
    </div>
  );
}

function MetricBox({ label, value, color, suffix = "" }: { label: string; value: number; color: string; suffix?: string }) {
  return (
    <div className="border rounded p-2 bg-muted/20">
      <div className="text-[9px] text-muted-foreground leading-tight">{label}</div>
      <div className={`text-base font-bold ${color}`}>{value}{suffix}</div>
    </div>
  );
}

function CollapsibleList({ title, items, color }: { title: string; items: string[]; color: string }) {
  const [open, setOpen] = useState(false);
  const display = open ? items : items.slice(0, 4);
  return (
    <div>
      <button
        className={`text-[10px] font-medium ${color} mb-1 hover:underline`}
        onClick={() => setOpen(!open)}
      >
        {title} {items.length > 4 ? (open ? "▲" : "▼") : ""}
      </button>
      <div className="space-y-0.5 font-mono text-[10px]">
        {display.map((item, i) => (
          <div key={i} className="truncate text-muted-foreground border-b border-border/20 py-0.5" title={item}>
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Main inner component ---------------------------------------------------
function DependencyGraphInner({ nodes = [], edges = [], graphHealth }: DependencyGraphProps) {
  const { fitView } = useReactFlow();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showLegend, setShowLegend] = useState(false);
  const [selectedModule, setSelectedModule] = useState<string>("all");
  const [selectedNodeType, setSelectedNodeType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  // Edge type filtering — multi-select set
  const [activeEdgeTypes, setActiveEdgeTypes] = useState<Set<string>>(new Set(DEFAULT_VISIBLE_EDGE_TYPES));
  const [showEdgeFilter, setShowEdgeFilter] = useState(false);

  const nodeTypes = useMemo(() => ({ custom: CustomGraphNode }), []);

  const availableModules = useMemo(() => {
    const modSet = new Set<string>();
    nodes.forEach((n) => {
      if (n.module) modSet.add(n.module);
      else if (n.path && n.path.includes("/")) modSet.add(n.path.split("/")[0]);
    });
    return Array.from(modSet).sort();
  }, [nodes]);

  const availableNodeTypes = useMemo(() => {
    const set = new Set<string>(nodes.map((n) => n.kind));
    return Array.from(set).sort();
  }, [nodes]);

  // ---- Build nodeLookupMap ONCE from all nodes (not filtered) ---------------
  const nodeLookupMap = useMemo(() => {
    const idSet = new Set(nodes.map((n) => n.id));
    const labelMap = new Map<string, string>();
    nodes.forEach((n) => {
      labelMap.set(n.id, n.id);
      labelMap.set(n.label, n.id);
      if (n.path) {
        labelMap.set(n.path, n.id);
        const filename = n.path.split("/").pop();
        if (filename) labelMap.set(filename, n.id);
      }
    });
    return { idSet, labelMap };
  }, [nodes]);

  const resolveId = useCallback((rawId: string): string | null => {
    const { idSet, labelMap } = nodeLookupMap;
    if (idSet.has(rawId)) return rawId;
    const stripped = rawId.replace(/^(call:|base:|file:|function:|class:|module:|package:|api:|folder:)/, "");
    if (labelMap.has(stripped)) return labelMap.get(stripped)!;
    if (idSet.has(`function:${stripped}`)) return `function:${stripped}`;
    if (idSet.has(`file:${stripped}`)) return `file:${stripped}`;
    if (idSet.has(`class:${stripped}`)) return `class:${stripped}`;
    return null;
  }, [nodeLookupMap]);

  // ---- All resolved edges (deduped) — used for metric computation ----------
  const allResolvedEdges = useMemo(() => {
    const seenTriplet = new Set<string>();
    const result: GraphEdge[] = [];
    for (const e of edges) {
      const srcId = resolveId(e.source);
      const tgtId = resolveId(e.target);
      if (!srcId || !tgtId || srcId === tgtId) continue;
      const triplet = `${srcId}||${tgtId}||${e.edge_type ?? e.relationship}`;
      if (seenTriplet.has(triplet)) continue;
      seenTriplet.add(triplet);
      result.push({ ...e, source: srcId, target: tgtId, id: `${srcId}->${tgtId}` });
    }
    return result;
  }, [edges, resolveId]);

  // ---- Edge type counts (for legend/health) --------------------------------
  const edgeTypeCounts = useMemo(() => computeEdgeTypeCounts(allResolvedEdges), [allResolvedEdges]);
  const availableEdgeTypes = useMemo(() => Object.keys(edgeTypeCounts).sort(), [edgeTypeCounts]);

  // ---- Blast radius from selected node (BFS reverse, max 3 hops) ----------
  const blastMap = useMemo(() => {
    const result = new Map<string, number>(); // nodeId -> depth
    if (!selectedNode) return result;

    // Forward adjacency: node → nodes that depend on it (reverse lookup)
    const reverseAdj = new Map<string, string[]>();
    for (const e of allResolvedEdges) {
      const edgeTypeKey = e.edge_type ?? e.relationship ?? "";
      if (["CONFIG_REFERENCE", "BUILD_DEPENDENCY", "PACKAGE_DEPENDENCY"].includes(edgeTypeKey)) continue;
      if (!reverseAdj.has(e.target)) reverseAdj.set(e.target, []);
      reverseAdj.get(e.target)!.push(e.source);
    }

    result.set(selectedNode.id, 0);
    const queue: [string, number][] = [[selectedNode.id, 0]];
    while (queue.length > 0) {
      const [cur, depth] = queue.shift()!;
      if (depth >= 3) continue;
      for (const dep of reverseAdj.get(cur) ?? []) {
        if (!result.has(dep)) {
          result.set(dep, depth + 1);
          queue.push([dep, depth + 1]);
        }
      }
    }
    return result;
  }, [selectedNode, allResolvedEdges]);

  // ---- Filter nodes --------------------------------------------------------
  const filteredNodes = useMemo(() => {
    return nodes.filter((n) => {
      if (selectedModule !== "all" && n.module !== selectedModule && !n.path?.startsWith(selectedModule)) return false;
      if (selectedNodeType !== "all" && n.kind !== selectedNodeType) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return n.label.toLowerCase().includes(q) || (n.path && n.path.toLowerCase().includes(q));
      }
      return true;
    });
  }, [nodes, selectedModule, selectedNodeType, searchQuery]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map((n) => n.id)), [filteredNodes]);

  const uniqueNodes = useMemo(() => {
    const seen = new Set<string>();
    return filteredNodes.filter((n) => {
      if (seen.has(n.id)) return false;
      seen.add(n.id);
      return true;
    });
  }, [filteredNodes]);

  // ---- Filter edges by active edge types and visible nodes -----------------
  const visibleEdges = useMemo(() => {
    return allResolvedEdges.filter((e) => {
      if (!filteredNodeIds.has(e.source) || !filteredNodeIds.has(e.target)) return false;
      const key = e.edge_type ?? e.relationship ?? "IMPORTS";
      return activeEdgeTypes.has(key);
    });
  }, [allResolvedEdges, filteredNodeIds, activeEdgeTypes]);

  // ---- Connected neighbors (hover/select highlights) ----------------------
  const connectedNodeIds = useMemo(() => {
    const activeId = hoveredNodeId || selectedNode?.id;
    if (!activeId) return new Set<string>();
    const connected = new Set<string>([activeId]);
    visibleEdges.forEach((e) => {
      if (e.source === activeId) connected.add(e.target);
      if (e.target === activeId) connected.add(e.source);
    });
    return connected;
  }, [hoveredNodeId, selectedNode, visibleEdges]);

  // ---- ReactFlow nodes with blast radius depth coloring -------------------
  const flowNodes: Node[] = useMemo(() => {
    const COLS = 5;
    const X_GAP = 280;
    const Y_GAP = 120;

    return uniqueNodes.map((node, idx) => {
      const col = idx % COLS;
      const row = Math.floor(idx / COLS);
      const isHov = hoveredNodeId === node.id;
      const isSel = selectedNode?.id === node.id;
      const isConn = connectedNodeIds.has(node.id);
      const blastDepth = blastMap.has(node.id) ? blastMap.get(node.id) : undefined;
      const hasBlast = blastMap.size > 0;

      return {
        id: node.id,
        type: "custom",
        position: { x: col * X_GAP + 30, y: row * Y_GAP + 30 },
        width: 240,
        height: 85,
        style: { width: 240, height: 85 },
        data: {
          label: node.label,
          kind: node.kind,
          path: node.path,
          module: node.module,
          language: node.language,
          fan_in: node.fan_in,
          fan_out: node.fan_out,
          is_critical: node.is_critical,
          isHighlighted: isHov,
          isSelected: isSel,
          blastDepth: blastDepth,
          isDimmed: hasBlast
            ? blastDepth === undefined
            : (hoveredNodeId !== null || selectedNode !== null) && !isConn,
        },
      };
    });
  }, [uniqueNodes, hoveredNodeId, selectedNode, connectedNodeIds, blastMap]);

  // ---- ReactFlow edges with per-type coloring -----------------------------
  const flowEdges: Edge[] = useMemo(() => {
    return visibleEdges.map((edge) => {
      const activeId = hoveredNodeId || selectedNode?.id;
      const isConnected = activeId && (edge.source === activeId || edge.target === activeId);
      const isDimmed = activeId !== null && !isConnected;
      const cfg = getEdgeConfig(edge.edge_type, edge.relationship);

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        label: cfg.label,
        labelStyle: { fill: "#64748b", fontSize: 9, fontWeight: 600 },
        labelBgStyle: { fill: "#f8fafc", rx: 4, ry: 4 },
        animated: Boolean(isConnected),
        style: {
          stroke: isConnected ? cfg.color : cfg.color,
          strokeWidth: isConnected ? 2.5 : 1.5,
          opacity: isDimmed ? 0.12 : 0.9,
          strokeDasharray: cfg.dashArray ?? undefined,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: cfg.color,
          width: 12,
          height: 12,
        },
      };
    });
  }, [visibleEdges, hoveredNodeId, selectedNode]);

  useEffect(() => {
    if (uniqueNodes.length > 0) {
      const timer = setTimeout(() => {
        fitView({ padding: 0.2, duration: 300 });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [uniqueNodes.length, fitView]);

  const containerClasses = isFullscreen
    ? "fixed inset-0 z-50 flex flex-col bg-background/98 backdrop-blur-md p-6 animate-in fade-in zoom-in-95 duration-200"
    : "relative flex flex-col rounded-xl border border-border/80 bg-background overflow-hidden shadow-sm";

  const innerHeight = isFullscreen ? "calc(100vh - 120px)" : "520px";

  return (
    <div className={containerClasses}>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-3 border-b border-border/80 bg-muted/40 backdrop-blur">
        <div className="flex flex-wrap items-center gap-2">
          {/* Search */}
          <div className="flex items-center gap-1.5 rounded-lg border border-border/80 bg-background px-3 py-1.5 text-xs shadow-2xs">
            <Search className="size-3.5 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search graph nodes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-transparent outline-none w-32 sm:w-44 text-xs placeholder:text-muted-foreground"
            />
          </div>

          {/* Module Filter */}
          {availableModules.length > 0 && (
            <select
              value={selectedModule}
              onChange={(e) => setSelectedModule(e.target.value)}
              className="h-8 rounded-lg border border-border/80 bg-background px-2.5 text-xs outline-none text-muted-foreground hover:text-foreground"
            >
              <option value="all">All Modules...</option>
              {availableModules.map((m) => (
                <option key={m} value={m}>📁 {m}</option>
              ))}
            </select>
          )}

          {/* Node Type Filter */}
          {availableNodeTypes.length > 0 && (
            <select
              value={selectedNodeType}
              onChange={(e) => setSelectedNodeType(e.target.value)}
              className="h-8 rounded-lg border border-border/80 bg-background px-2.5 text-xs outline-none text-muted-foreground hover:text-foreground"
            >
              <option value="all">All Node Types...</option>
              {availableNodeTypes.map((t) => (
                <option key={t} value={t}>🏷️ {t}</option>
              ))}
            </select>
          )}

          {/* Edge Type Filter Toggle */}
          <div className="relative">
            <button
              onClick={() => setShowEdgeFilter(!showEdgeFilter)}
              className={`flex items-center gap-1.5 h-8 px-2.5 rounded-lg border text-xs transition-colors ${
                showEdgeFilter
                  ? "border-indigo-500/60 bg-indigo-500/10 text-foreground"
                  : "border-border/80 bg-background text-muted-foreground hover:text-foreground"
              }`}
            >
              <Filter className="size-3.5" />
              <span>Edge Types</span>
              <span className="font-mono text-[10px] opacity-70">({activeEdgeTypes.size}/{availableEdgeTypes.length})</span>
            </button>

            {showEdgeFilter && (
              <div className="absolute top-10 left-0 z-50 bg-background border border-border/80 rounded-lg shadow-xl p-3 min-w-[240px]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold">Filter Edge Types</span>
                  <button onClick={() => setShowEdgeFilter(false)}><X className="size-3.5 text-muted-foreground" /></button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {availableEdgeTypes.map((et) => (
                    <EdgeTypeToggle
                      key={et}
                      edgeType={et}
                      active={activeEdgeTypes.has(et)}
                      count={edgeTypeCounts[et] ?? 0}
                      onToggle={() => {
                        setActiveEdgeTypes((prev) => {
                          const next = new Set(prev);
                          if (next.has(et)) next.delete(et);
                          else next.add(et);
                          return next;
                        });
                      }}
                    />
                  ))}
                </div>
                <div className="flex gap-2 mt-2 pt-2 border-t border-border/40">
                  <button
                    onClick={() => setActiveEdgeTypes(new Set(availableEdgeTypes))}
                    className="text-[10px] text-indigo-500 hover:underline"
                  >
                    All
                  </button>
                  <button
                    onClick={() => setActiveEdgeTypes(new Set(DEFAULT_VISIBLE_EDGE_TYPES))}
                    className="text-[10px] text-muted-foreground hover:underline"
                  >
                    Reset Default
                  </button>
                  <button
                    onClick={() => setActiveEdgeTypes(new Set())}
                    className="text-[10px] text-rose-500 hover:underline"
                  >
                    None
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <GraphHealthBadge
            graphHealth={graphHealth}
            edgeTypeCounts={edgeTypeCounts}
            totalNodes={flowNodes.length}
            totalEdges={visibleEdges.length}
          />

          <button
            onClick={() => setShowLegend(!showLegend)}
            className={`h-8 px-2.5 rounded-lg border text-xs transition-colors ${
              showLegend
                ? "border-indigo-500/60 bg-indigo-500/10 text-foreground"
                : "border-border/80 bg-background text-muted-foreground hover:text-foreground"
            }`}
          >
            Legend
          </button>

          <Button
            size="sm"
            variant="outline"
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="flex items-center gap-1.5 h-8 text-xs font-medium"
          >
            {isFullscreen ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
          </Button>
        </div>
      </div>

      {/* ReactFlow Canvas + Inspector */}
      <div className="relative flex-1 min-h-0 w-full flex">
        <div className="flex-1 w-full relative" style={{ height: innerHeight }}>
          {flowNodes.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-2 text-xs text-muted-foreground p-6">
              <Layers className="size-8 opacity-40" />
              <span>No knowledge graph nodes match current search filters.</span>
            </div>
          ) : (
            <ReactFlow
              nodes={flowNodes}
              edges={flowEdges}
              nodeTypes={nodeTypes}
              onNodeClick={(_, node) => {
                const target = nodes.find((n) => n.id === node.id);
                setSelectedNode((prev) => prev?.id === node.id ? null : (target || null));
              }}
              onNodeMouseEnter={(_, node) => setHoveredNodeId(node.id)}
              onNodeMouseLeave={() => setHoveredNodeId(null)}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              minZoom={0.05}
              maxZoom={2.5}
            >
              <Background color="#94a3b8" gap={24} size={1} />
              <Controls position="bottom-left" />
              {isFullscreen && <MiniMap position="bottom-right" className="!bg-background !border-border !rounded-lg shadow-lg" />}
            </ReactFlow>
          )}

          {/* Graph Legend overlay */}
          {showLegend && <GraphLegend edgeTypeCounts={edgeTypeCounts} />}

          {/* Blast radius info banner */}
          {selectedNode && blastMap.size > 1 && (
            <div className="absolute top-3 left-3 z-30 bg-background/95 backdrop-blur border border-orange-500/40 rounded-lg px-3 py-2 shadow-lg text-[11px]">
              <span className="font-semibold text-orange-500">Blast Radius</span>
              <span className="text-muted-foreground ml-2">
                Direct: <strong className="text-orange-500">{[...blastMap.values()].filter(d => d === 1).length}</strong>
                {" "}· Indirect: <strong className="text-yellow-500">{[...blastMap.values()].filter(d => d === 2).length}</strong>
                {" "}· Total: <strong className="text-foreground">{blastMap.size - 1}</strong>
              </span>
            </div>
          )}
        </div>

        {/* Selected Node Inspector Drawer */}
        {selectedNode && (
          <NodeInspector
            selectedNode={selectedNode}
            allNodes={nodes}
            resolvedEdges={allResolvedEdges}
            blastMap={blastMap}
            onClose={() => setSelectedNode(null)}
          />
        )}
      </div>
    </div>
  );
}

export function DependencyGraph(props: DependencyGraphProps) {
  return (
    <ReactFlowProvider>
      <DependencyGraphInner {...props} />
    </ReactFlowProvider>
  );
}
