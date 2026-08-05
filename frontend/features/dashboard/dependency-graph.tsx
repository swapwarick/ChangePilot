"use client";

import "@xyflow/react/dist/style.css";
import { Background, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { graphEdges, graphNodes } from "./data";

const positions: Record<string, { x: number; y: number }> = {
  web: { x: 240, y: 20 },
  api: { x: 40, y: 140 },
  user: { x: 260, y: 140 },
  notify: { x: 480, y: 140 },
  auth: { x: 10, y: 270 },
  account: { x: 175, y: 270 },
  userdb: { x: 340, y: 270 },
  redis: { x: 505, y: 270 },
  mail: { x: 650, y: 170 }
};

function riskClass(risk: number) {
  if (risk >= 0.8) return "border-destructive bg-destructive/8 text-destructive";
  if (risk >= 0.65) return "border-orange-500 bg-orange-500/8 text-orange-700";
  if (risk >= 0.35) return "border-warning bg-warning/10 text-amber-700";
  return "border-primary bg-primary/8 text-primary";
}

const nodes: Node[] = graphNodes.map((node) => ({
  id: node.id,
  position: positions[node.id],
  data: {
    label: (
      <div className={`rounded-md border px-3 py-2 text-xs shadow-sm ${riskClass(node.risk)}`}>
        <div className="font-semibold text-foreground">{node.label}</div>
        <div>{node.risk.toFixed(2)}</div>
      </div>
    )
  },
  type: "default"
}));

const edges: Edge[] = graphEdges.map((edge) => ({
  id: edge.id,
  source: edge.source,
  target: edge.target,
  animated: edge.relationship === "calls",
  style: { stroke: "#718096", strokeWidth: 1.2 }
}));

export function DependencyGraph() {
  return (
    <div className="h-[280px] overflow-hidden rounded-md border border-border bg-background">
      <ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.55} maxZoom={1.4}>
        <Background color="#d7dee2" gap={18} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

