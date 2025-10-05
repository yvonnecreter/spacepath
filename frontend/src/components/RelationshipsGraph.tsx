import { useEffect, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { Card } from "@/components/ui/card";

interface GraphNode {
  id: string;
  name: string;
  type: string;
  color: string;
}

interface GraphLink {
  source: string;
  target: string;
  label: string;
}

const mockData = {
  nodes: [
    { id: "disease", name: "Disease", type: "Disease", color: "#FCD34D" },
    { id: "gene", name: "Gene", type: "Gene", color: "#FB923C" },
    { id: "phenotype", name: "Phenotype", type: "Phenotype", color: "#D1D5DB" },
    { id: "oligogenic", name: "Oligogenic Combination", type: "OligogenicCombination", color: "#86EFAC" },
    { id: "molecular", name: "Molecular Function", type: "MolecularFunction", color: "#C084FC" },
    { id: "biological", name: "Biological Process", type: "BiologicalProcess", color: "#F87171" },
    { id: "cellular", name: "Cellular Component", type: "CellularComponent", color: "#67E8F9" },
    { id: "protein-complex", name: "Protein Complex", type: "ProteinComplex", color: "#FDE047" },
    { id: "protein-domain", name: "Protein Domain", type: "ProteinDomain", color: "#A78BFA" },
    { id: "protein-family", name: "Protein Family", type: "ProteinFamily", color: "#FDA4AF" },
  ] as GraphNode[],
  links: [
    { source: "disease", target: "phenotype", label: "resembles" },
    { source: "disease", target: "oligogenic", label: "described" },
    { source: "phenotype", target: "oligogenic", label: "resembles" },
    { source: "oligogenic", target: "gene", label: "involves" },
    { source: "molecular", target: "biological", label: "resembles" },
    { source: "gene", target: "protein-complex", label: "forms" },
    { source: "gene", target: "molecular", label: "bioGRID" },
    { source: "protein-complex", target: "cellular", label: "associated" },
    { source: "cellular", target: "biological", label: "associated" },
    { source: "protein-domain", target: "gene", label: "ageSimilar" },
    { source: "protein-family", target: "gene", label: "bioGRID" },
  ] as GraphLink[],
};

export const RelationshipsGraph = () => {
  const graphRef = useRef<any>();

  return (
    <div className="h-full flex gap-4">
      <Card className="flex-1 bg-white border border-border shadow-lg overflow-hidden">
        <div className="h-full w-full">
          <ForceGraph2D
            ref={graphRef}
            graphData={mockData}
            nodeLabel="name"
            nodeColor={(node: any) => node.color}
            nodeRelSize={8}
            linkLabel="label"
            linkDirectionalArrowLength={3}
            linkDirectionalArrowRelPos={1}
            linkColor={() => "#94A3B8"}
            linkWidth={1.5}
            backgroundColor="#ffffff"
            nodeCanvasObject={(node: any, ctx, globalScale) => {
              const label = node.name;
              const fontSize = 12/globalScale;
              ctx.font = `${fontSize}px Inter, sans-serif`;
              const textWidth = ctx.measureText(label).width;
              const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.4);

              ctx.fillStyle = node.color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI, false);
              ctx.fill();

              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = '#1e293b';
              ctx.fillText(label, node.x, node.y + 12);
            }}
            cooldownTicks={100}
            onEngineStop={() => graphRef.current?.zoomToFit(400)}
          />
        </div>
      </Card>

      <Card className="w-80 bg-white border border-border shadow-lg p-4 overflow-y-auto">
        <h3 className="font-semibold text-foreground mb-4">Node Statistics</h3>
        <div className="space-y-2">
          {[
            { label: "Gene (G)", count: 40924, color: "#FB923C" },
            { label: "BiologicalProcess (BP)", count: 28949, color: "#F87171" },
            { label: "ProteinFamily (MF)", count: 27386, color: "#FDA4AF" },
            { label: "Phenotype (P)", count: 16984, color: "#D1D5DB" },
            { label: "ProteinDomain (PD)", count: 15291, color: "#A78BFA" },
            { label: "Disease (D)", count: 12701, color: "#FCD34D" },
            { label: "MolecularFunction (MF)", count: 11238, color: "#C084FC" },
            { label: "CellularComponent (CC)", count: 4038, color: "#67E8F9" },
            { label: "ProteinComplex (PC)", count: 3827, color: "#FDE047" },
            { label: "OligogenicCombination (OC)", count: 1718, color: "#86EFAC" },
          ].map((item) => (
            <div key={item.label} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <div
                  className="w-4 h-4 rounded"
                  style={{ backgroundColor: item.color }}
                />
                <span className="text-foreground">{item.label}</span>
              </div>
              <span className="text-muted-foreground">{item.count.toLocaleString()}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 pt-4 border-t border-border">
          <div className="flex justify-between text-sm">
            <span className="text-foreground font-medium">Node count</span>
            <span className="text-muted-foreground">0 10k 20k 30k 40k</span>
          </div>
        </div>
      </Card>
    </div>
  );
};
