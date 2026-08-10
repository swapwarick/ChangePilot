"use client";

import { useState, useMemo, useCallback } from "react";
import "@xyflow/react/dist/style.css";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
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
  Network,
  Filter,
  Eye,
  EyeOff,
  Zap,
  Box,
  FileCode
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { GraphNode, GraphEdge } from "@/types/api";

interface DependencyGraphProps {
  nodes?: GraphNode[];
  edges?: GraphEdge[];
}

// Custom Node Component with Enterprise Semantic Color Coding
function CustomGraphNode({ data, id }: NodeProps) {
  const {
    label,
    kind,
    path,
    module,
    language,
    fan_in = 0,
    fan_out = 0,
    is_critical,
    isHighlighted,
    isDimmed,
    isSelected
  } = data as {
    label: string;
    kind: string;
    path?: string;
    module?: string;
    language?: string;
    fan_in?: number;
    fan_out?: number;
    is_critical?: boolean;
    isHighlighted?: boolean;
    isDimmed?: boolean;
    isSelected?: boolean;
  };

  const getStyle = () => {
    const p = (path || label).toLowerCase();
    const isTest = p.includes("test") || p.includes("spec");

    if (is_critical || kind === "api") {
      return "border-red-500/80 bg-gradient-to-r from-red-500/20 via-background to-red-500/10 text-red-900 dark:text-red-200 font-semibold shadow-md ring-1 ring-red-500/30";
    }
    if (kind === "database" || fan_out > 5) {
      return "border-orange-500/80 bg-gradient-to-r from-orange-500/20 via-background to-orange-500/10 text-orange-900 dark:text-orange-200 font-semibold shadow-md ring-1 ring-orange-500/30";
    }
    if (kind === "module" || kind === "package") {
      return "border-amber-500/80 bg-gradient-to-r from-amber-500/20 via-background to-amber-500/10 text-amber-900 dark:text-amber-200 font-bold shadow-md ring-1 ring-amber-500/30";
    }
    if (isTest) {
      return "border-emerald-500/80 bg-gradient-to-r from-emerald-500/20 via-background to-emerald-500/10 text-emerald-900 dark:text-emerald-200 font-medium shadow-sm";
    }
    if (kind === "class" || kind === "function" || kind === "file") {
      return "border-blue-500/80 bg-gradient-to-r from-blue-500/15 via-background to-blue-500/10 text-blue-900 dark:text-blue-200 font-medium shadow-sm";
    }
    return "border-border/90 bg-card text-card-foreground shadow-2xs hover:shadow-md transition-all";
  };

  const opacityClass = isDimmed ? "opacity-20 scale-95" : isSelected ? "scale-105 ring-2 ring-indigo-500 z-50 shadow-xl" : isHighlighted ? "scale-105 ring-2 ring-indigo-400 z-40 shadow-lg" : "opacity-100";

  return (
    <div className={`relative px-3.5 py-2.5 rounded-xl border min-w-[220px] max-w-[260px] cursor-pointer transition-all duration-200 ${getStyle()} ${opacityClass}`}>
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !bg-indigo-500 !border-2 !border-background hover:!scale-125 transition-transform"
      />

      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          {kind === "module" || kind === "folder" ? (
            <Box className="size-3.5 text-amber-500 shrink-0" />
          ) : kind === "api" ? (
            <Zap className="size-3.5 text-red-500 shrink-0" />
          ) : (
            <FileCode className="size-3.5 text-indigo-500 shrink-0" />
          )}
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

export function DependencyGraph({ nodes = [], edges = [] }: DependencyGraphProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [viewMode, setViewMode] = useState<"all" | "modules">("all");
  const [selectedModule, setSelectedModule] = useState<string>("all");
  const [selectedNodeType, setSelectedNodeType] = useState<string>("all");
  const [selectedLanguage, setSelectedLanguage] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

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

  const availableLanguages = useMemo(() => {
    const set = new Set<string>(nodes.map((n) => n.language).filter(Boolean) as string[]);
    return Array.from(set).sort();
  }, [nodes]);

  // Determine connected neighbor nodes
  const connectedNodeIds = useMemo(() => {
    const activeId = hoveredNodeId || selectedNode?.id;
    if (!activeId) return new Set<string>();
    const connected = new Set<string>([activeId]);
    edges.forEach((e) => {
      if (e.source === activeId) connected.add(e.target);
      if (e.target === activeId) connected.add(e.source);
    });
    return connected;
  }, [hoveredNodeId, selectedNode, edges]);

  // Filter nodes
  const filteredNodes = useMemo(() => {
    return nodes.filter((n) => {
      if (viewMode === "modules" && n.kind !== "module" && n.kind !== "folder") return false;
      if (selectedModule !== "all" && n.module !== selectedModule && !n.path?.startsWith(selectedModule)) return false;
      if (selectedNodeType !== "all" && n.kind !== selectedNodeType) return false;
      if (selectedLanguage !== "all" && n.language !== selectedLanguage) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return n.label.toLowerCase().includes(q) || (n.path && n.path.toLowerCase().includes(q));
      }
      return true;
    });
  }, [nodes, viewMode, selectedModule, selectedNodeType, selectedLanguage, searchQuery]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map((n) => n.id)), [filteredNodes]);

  const filteredEdges = useMemo(() => {
    return edges.filter((e) => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target));
  }, [edges, filteredNodeIds]);

  const flowNodes: Node[] = useMemo(() => {
    const COLS = 4;
    const X_GAP = 310;
    const Y_GAP = 110;

    return filteredNodes.map((node, idx) => {
      const col = idx % COLS;
      const row = Math.floor(idx / COLS);
      const isHov = hoveredNodeId === node.id;
      const isSel = selectedNode?.id === node.id;
      const isConn = connectedNodeIds.has(node.id);

      return {
        id: node.id,
        type: "custom",
        position: { x: col * X_GAP + 40, y: row * Y_GAP + 40 },
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
          isDimmed: (hoveredNodeId !== null || selectedNode !== null) && !isConn
        }
      };
    });
  }, [filteredNodes, hoveredNodeId, selectedNode, connectedNodeIds]);

  const flowEdges: Edge[] = useMemo(() => {
    return filteredEdges.map((edge) => {
      const activeId = hoveredNodeId || selectedNode?.id;
      const isConnected = activeId && (edge.source === activeId || edge.target === activeId);
      const isDimmed = activeId !== null && !isConnected;

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: "smoothstep",
        label: edge.relationship,
        labelStyle: { fill: "#64748b", fontSize: 9, fontWeight: 600 },
        labelBgStyle: { fill: "#f8fafc", rx: 4, ry: 4 },
        animated: Boolean(isConnected),
        style: {
          stroke: isConnected ? "#3b82f6" : "#6366f1",
          strokeWidth: isConnected ? 2.5 : 1.5,
          opacity: isDimmed ? 0.15 : 0.85
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isConnected ? "#3b82f6" : "#6366f1",
          width: 12,
          height: 12
        }
      };
    });
  }, [filteredEdges, hoveredNodeId, selectedNode]);

  const containerClasses = isFullscreen
    ? "fixed inset-0 z-50 flex flex-col bg-background/98 backdrop-blur-md p-6 animate-in fade-in zoom-in-95 duration-200"
    : "relative flex flex-col h-[600px] rounded-xl border border-border/80 bg-background overflow-hidden shadow-sm";

  return (
    <div className={containerClasses}>
      {/* Top Toolbar Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 border-b border-border/80 bg-muted/40 backdrop-blur">
        <div className="flex flex-wrap items-center gap-2">
          {/* Search Box */}
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
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground hidden lg:inline">
            Showing <strong className="text-foreground">{flowNodes.length}</strong> nodes •{" "}
            <strong className="text-indigo-600 dark:text-indigo-400">{flowEdges.length}</strong> connections
          </span>

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

      {/* Main Graph & Inspector Split */}
      <div className="relative flex-1 min-h-0 w-full flex">
        <div className="flex-1 h-full">
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
                setSelectedNode(target || null);
              }}
              onNodeMouseEnter={(_, node) => setHoveredNodeId(node.id)}
              onNodeMouseLeave={() => setHoveredNodeId(null)}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              minZoom={0.15}
              maxZoom={2.0}
            >
              <Background color="#cbd5e1" gap={28} size={1} />
              <Controls position="bottom-left" />
              {isFullscreen && <MiniMap position="bottom-right" className="!bg-background !border-border !rounded-lg shadow-lg" />}
            </ReactFlow>
          )}
        </div>

        {/* Selected Node Detail Inspector Drawer */}
        {selectedNode && (
          <div className="w-80 border-l border-border bg-card p-4 overflow-y-auto z-40 text-card-foreground flex flex-col justify-between shadow-xl">
            <div>
              <div className="flex items-center justify-between border-b pb-3 mb-3">
                <div>
                  <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                    {selectedNode.kind}
                  </span>
                  <h3 className="text-sm font-semibold mt-1.5 truncate">{selectedNode.label}</h3>
                </div>
                <Button size="sm" variant="ghost" onClick={() => setSelectedNode(null)}>✕</Button>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <div className="text-[11px] font-medium text-muted-foreground">Full Path</div>
                  <div className="font-mono text-[11px] bg-muted/40 p-2 rounded border mt-1 break-all">
                    {selectedNode.path || selectedNode.label}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="border rounded p-2 bg-muted/20">
                    <div className="text-[10px] text-muted-foreground">Fan-In (Dependents)</div>
                    <div className="text-base font-bold text-indigo-600">{selectedNode.fan_in || 0}</div>
                  </div>
                  <div className="border rounded p-2 bg-muted/20">
                    <div className="text-[10px] text-muted-foreground">Fan-Out (Imports)</div>
                    <div className="text-base font-bold text-purple-600">{selectedNode.fan_out || 0}</div>
                  </div>
                </div>

                {selectedNode.metadata && Object.keys(selectedNode.metadata).length > 0 && (
                  <div>
                    <div className="text-[11px] font-medium text-muted-foreground mb-1">AST Extracted Symbols</div>
                    <div className="space-y-1 font-mono text-[11px]">
                      {Object.entries(selectedNode.metadata).map(([k, v]) => (
                        v ? (
                          <div key={k} className="border-b py-1">
                            <span className="text-muted-foreground capitalize">{k}: </span>
                            <span className="text-foreground truncate">{v}</span>
                          </div>
                        ) : null
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <Button className="w-full mt-4 text-xs" variant="outline" onClick={() => setSelectedNode(null)}>
              Close Inspector
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

