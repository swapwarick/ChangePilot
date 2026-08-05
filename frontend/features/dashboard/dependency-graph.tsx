"use client";

import "@xyflow/react/dist/style.css";
import { Background, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { GraphNode, GraphEdge } from "@/types/api";

interface DependencyGraphProps {
  nodes?: GraphNode[];
  edges?: GraphEdge[];
}

function riskClass(kind: string) {
  if (kind === "service") return "border-primary bg-primary/10 text-primary";
  if (kind === "module") return "border-warning bg-warning/10 text-amber-700";
  if (kind === "database") return "border-orange-500 bg-orange-500/10 text-orange-700";
  return "border-border bg-card text-foreground";
}

export function DependencyGraph({ nodes = [], edges = [] }: DependencyGraphProps) {
  const flowNodes: Node[] = nodes.map((node, index) => {
    const col = index % 4;
    const row = Math.floor(index / 4);
    return {
      id: node.id,
      position: { x: col * 180 + 30, y: row * 100 + 20 },
      data: {
        label: (
          <div className={`rounded-md border px-3 py-2 text-xs shadow-sm ${riskClass(node.kind)}`}>
            <div className="font-semibold">{node.label}</div>
            <div className="text-[10px] opacity-75">{node.kind}</div>
          </div>
        )
      },
      type: "default"
    };
  });

  const flowEdges: Edge[] = edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    animated: edge.relationship === "imports" || edge.relationship === "calls",
    style: { stroke: "#718096", strokeWidth: 1.2 }
  }));

  return (
    <div className="h-[280px] overflow-hidden rounded-md border border-border bg-background">
      {flowNodes.length === 0 ? (
        <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
          No knowledge graph nodes available. Connect a repository to build the AST graph.
        </div>
      ) : (
        <ReactFlow nodes={flowNodes} edges={flowEdges} fitView minZoom={0.4} maxZoom={1.4}>
          <Background color="#d7dee2" gap={18} />
          <Controls showInteractive={false} />
        </ReactFlow>
      )}
    </div>
  );
}
