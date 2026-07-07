import { KnowledgeGraph } from "@/components/graph/KnowledgeGraph";

const sampleNodes = [
  { id: "r1", label: "GDPR", type: "regulation" as const },
  { id: "r2", label: "SOX", type: "regulation" as const },
  { id: "e1", label: "Acme Corp", type: "entity" as const },
];

const sampleEdges = [
  { id: "e1-r1", source: "e1", target: "r1", label: "applies to" },
  { id: "e1-r2", source: "e1", target: "r2", label: "applies to" },
];

export function KnowledgeGraphPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
          Knowledge Graph
        </h1>
        <p className="text-surface-500 dark:text-surface-400">
          Visualize relationships between regulations, entities, and requirements
        </p>
      </div>
      <KnowledgeGraph nodes={sampleNodes} edges={sampleEdges} height={600} />
    </div>
  );
}
