import { useEffect, useRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { Card } from "@/components/ui/card";

interface GraphNode {
  id: string;
  name: string;
  type: string;
  color: string;
  value: number;
}

interface GraphLink {
  source: string;
  target: string;
  label: string;
  weight: number;
}

interface ConfidenceData {
  term: string;
  nasa: number;
  clinical: number;
}

// Real data from spacepath_llm_demo.html
const realData = {
  nodes: [
    { id: "Protein", name: "Input Protein", type: "Protein", color: "#f4a261", value: 37 },
    { id: "ERBB1", name: "ERBB1", type: "Synonym", color: "#bdbdbd", value: 4 },
    { id: "HER1", name: "HER1", type: "Synonym", color: "#bdbdbd", value: 4 },
    { id: "MAPK Pathway", name: "MAPK Pathway", type: "Pathway", color: "#6fcf97", value: 8 },
    { id: "PI3K-AKT Pathway", name: "PI3K-AKT Pathway", type: "Pathway", color: "#6fcf97", value: 6 },
    { id: "Microgravity", name: "Microgravity", type: "Condition", color: "#56ccf2", value: 11 },
    { id: "Cell Proliferation", name: "Cell Proliferation", type: "Outcome", color: "#2dd4bf", value: 6 },
    { id: "Osimertinib", name: "Osimertinib", type: "Drug", color: "#f06292", value: 16 },
    { id: "NSCLC Trials", name: "NSCLC Trials", type: "Trial", color: "#9b59b6", value: 6 },
    { id: "NASA Papers", name: "NASA Papers", type: "Evidence", color: "#90a4ae", value: 1 },
    { id: "ClinicalTrials.gov", name: "ClinicalTrials.gov", type: "Evidence", color: "#90a4ae", value: 1 },
  ] as GraphNode[],
  links: [
    { source: "Protein", target: "ERBB1", label: "aliases", weight: 4 },
    { source: "Protein", target: "HER1", label: "aliases", weight: 4 },
    { source: "Protein", target: "MAPK Pathway", label: "participates_in", weight: 8 },
    { source: "Protein", target: "PI3K-AKT Pathway", label: "participates_in", weight: 6 },
    { source: "Protein", target: "Microgravity", label: "affected_by", weight: 5 },
    { source: "Microgravity", target: "Cell Proliferation", label: "leads_to", weight: 6 },
    { source: "Protein", target: "Osimertinib", label: "targeted_by", weight: 10 },
    { source: "Osimertinib", target: "NSCLC Trials", label: "studied_in", weight: 6 },
    { source: "Protein", target: "NASA Papers", label: "reported_in", weight: 0 },
    { source: "Protein", target: "ClinicalTrials.gov", label: "linked_to", weight: 0 },
  ] as GraphLink[],
};

const confidenceData: ConfidenceData[] = [
  { term: "EGFR", nasa: 80, clinical: 95 },
  { term: "MAPK Pathway", nasa: 65, clinical: 60 },
  { term: "PI3K-AKT Pathway", nasa: 60, clinical: 55 },
  { term: "Microgravity", nasa: 95, clinical: 35 },
  { term: "Cell Proliferation", nasa: 70, clinical: 60 },
  { term: "Osimertinib", nasa: 25, clinical: 95 },
  { term: "NSCLC Trials", nasa: 20, clinical: 98 },
];

export const RelationshipsGraph = () => {
  const graphRef = useRef<any>();

  return (
    <div className="h-full flex gap-4">
      <Card className="w-80 bg-white border border-border shadow-lg p-4 overflow-y-hidden">
      <h3 className="font-semibold text-foreground mb-4">Knowledge Graph</h3>
        <div className="h-full w-full flex items-center justify-center min-h-[500px]">
          <ForceGraph2D
            ref={graphRef}
            graphData={realData}
            nodeLabel="name"
            nodeColor={(node: any) => node.color}
            nodeRelSize={8}
            linkLabel="label"
            linkDirectionalArrowLength={3}
            linkDirectionalArrowRelPos={1}
            linkColor={() => "#808080"}
            linkWidth={(link: any) => 1 + 0.2 * (link.weight || 1)}
            backgroundColor="#ffffff"
            nodeCanvasObject={(node: any, ctx, globalScale) => {
              const label = node.name;
              const fontSize = 14/globalScale;
              ctx.font = `${fontSize}px Inter, sans-serif`;
              
              // Draw node circle
              ctx.fillStyle = node.color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, Math.max(6, Math.min(20, node.value / 2)), 0, 2 * Math.PI, false);
              ctx.fill();

              // Draw label
              ctx.textAlign = 'center';
              ctx.textBaseline = 'middle';
              ctx.fillStyle = '#1e293b';
              ctx.fillText(label, node.x, node.y);
            }}
            cooldownTicks={100}
            onEngineStop={() => graphRef.current?.zoomToFit(400)}
          />
        </div>
      </Card>

      <Card className="w-80 bg-white border border-border shadow-lg p-4 overflow-y-auto">
        <h3 className="font-semibold text-foreground mb-4">Confidence (NASA vs Clinical)</h3>
        <div className="space-y-3 mb-4">
          {confidenceData.map((item) => (
            <div key={item.term} className="space-y-1">
              <div className="text-sm font-medium text-foreground">{item.term}</div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <div className="text-xs text-muted-foreground mb-1">NASA</div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-[#2a9d8f] h-2 rounded-full" 
                      style={{ width: `${item.nasa}%` }}
                    />
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">{item.nasa}%</div>
                </div>
                <div className="flex-1">
                  <div className="text-xs text-muted-foreground mb-1">Clinical</div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-[#e76f51] h-2 rounded-full" 
                      style={{ width: `${item.clinical}%` }}
                    />
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">{item.clinical}%</div>
                </div>
              </div>
            </div>
          ))}
        </div>
        
        <div className="mt-4 pt-4 border-t border-border">
          <div className="space-y-2">
            <div className="text-sm font-medium text-foreground mb-2">Node Types</div>
            <div className="flex flex-wrap gap-1">
              <span className="px-2 py-1 text-xs rounded-full bg-[#e8fff7]">Protein</span>
              <span className="px-2 py-1 text-xs rounded-full bg-[#f0fff0]">Pathway</span>
              <span className="px-2 py-1 text-xs rounded-full bg-[#e3f2fd]">Condition</span>
              <span className="px-2 py-1 text-xs rounded-full bg-[#e0f7fa]">Outcome</span>
              <span className="px-2 py-1 text-xs rounded-full bg-[#fde2e4]">Drug</span>
              <span className="px-2 py-1 text-xs rounded-full bg-[#ede7f6]">Trial</span>
              <span className="px-2 py-1 text-xs rounded-full bg-[#eeeeee]">Evidence</span>
            </div>
          </div>
          <div className="mt-4 text-xs text-muted-foreground">
            Query: <span className="font-medium">Input Protein in microgravity</span><br/>
            Edge labels show relations; node size scales with evidence weight.
          </div>
        </div>
      </Card>
    </div>
  );
};
