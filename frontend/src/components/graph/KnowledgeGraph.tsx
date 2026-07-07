import { useEffect, useRef } from "react";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface GraphNode {
  id: string;
  label: string;
  type: "regulation" | "entity" | "requirement" | "finding" | "document";
}

interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

interface KnowledgeGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  title?: string;
  className?: string;
  height?: number;
}

const nodeColors: Record<string, string> = {
  regulation: "#6366f1",
  entity: "#22c55e",
  requirement: "#f97316",
  finding: "#ef4444",
  document: "#06b6d4",
};

export function KnowledgeGraph({
  nodes,
  edges,
  title = "Knowledge Graph",
  className,
  height = 500,
}: KnowledgeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const elements: ElementDefinition[] = [
      ...nodes.map((n) => ({
        data: {
          id: n.id,
          label: n.label,
          type: n.type,
        },
      })),
      ...edges.map((e) => ({
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
        },
      })),
    ];

    const isDark = document.documentElement.classList.contains("dark");

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele) => nodeColors[ele.data("type") as string] || "#6366f1",
            label: "data(label)",
            "text-valign": "bottom",
            "text-halign": "center",
            "font-size": "11px",
            color: isDark ? "#e2e8f0" : "#334155",
            "text-margin-y": 8,
            width: 40,
            height: 40,
            "border-width": 2,
            "border-color": isDark ? "#334155" : "#e2e8f0",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": isDark ? "#475569" : "#cbd5e1",
            "target-arrow-color": isDark ? "#475569" : "#cbd5e1",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "font-size": "9px",
            color: isDark ? "#64748b" : "#94a3b8",
            label: "data(label)",
            "text-margin-y": -4,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#6366f1",
            "border-width": 3,
          },
        },
      ],
      layout: {
        name: "dagre",
        rankDir: "TB",
        spacingFactor: 1.5,
        animate: true,
      } as any,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      minZoom: 0.5,
      maxZoom: 3,
    });

    return () => {
      cyRef.current?.destroy();
    };
  }, [nodes, edges]);

  return (
    <Card className={cn(className)}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <span className="text-xs text-surface-400">Drag to pan &middot; Scroll to zoom</span>
      </CardHeader>
      <div
        ref={containerRef}
        style={{ height }}
        className="rounded-lg border border-surface-200 bg-surface-50 dark:border-surface-700 dark:bg-surface-900/50"
        role="img"
        aria-label="Knowledge graph visualization"
      />
    </Card>
  );
}
