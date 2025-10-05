import { useState } from "react";
import { Card } from "@/components/ui/card";
import { ChevronDown, ExternalLink, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Dialog, DialogContent, DialogClose } from "@/components/ui/dialog";
import { Pathway } from "@/types/api";

interface PathwaysViewerProps {
  pathways?: Pathway[];
  isLoading?: boolean;
}

export const PathwaysViewer = ({ pathways = [], isLoading = false }: PathwaysViewerProps) => {
  const [openPathways, setOpenPathways] = useState<Record<string, boolean>>({});
  const [fullscreenImage, setFullscreenImage] = useState<string | null>(null);

  const togglePathway = (id: string) => {
    setOpenPathways(prev => ({ ...prev, [id]: !prev[id] }));
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Loading pathways...</span>
        </div>
      </div>
    );
  }

  if (!pathways || pathways.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <p>No pathways available</p>
          <p className="text-sm">Ask a question about a protein to see related pathways</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto space-y-4">
      {pathways.map((pathway) => (
        <Card key={pathway.pathway_id} className="bg-white border border-border shadow-md hover:shadow-lg transition-shadow">
          <Collapsible open={openPathways[pathway.pathway_id]} onOpenChange={() => togglePathway(pathway.pathway_id)}>
            <div className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <h3 className="text-base font-medium text-foreground mb-1">{pathway.title}</h3>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
                    <a 
                      href={pathway.page_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-primary hover:underline"
                    >
                      Pathway ID: {pathway.pathway_id}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                </div>
                <CollapsibleTrigger asChild>
                  <Button variant="ghost" size="sm">
                    <ChevronDown className={`h-5 w-5 transition-transform ${openPathways[pathway.pathway_id] ? 'rotate-180' : ''}`} />
                  </Button>
                </CollapsibleTrigger>
              </div>

              {pathway.image_url && (
                <CollapsibleContent>
                  <div className="mt-4 border border-border rounded-lg bg-gray-50 p-4">
                    <div className="text-xs text-muted-foreground mb-2 font-mono">
                      {pathway.title.toUpperCase()}
                    </div>
                    <div className="bg-white border border-border rounded p-4 overflow-auto">
                      <img 
                        src={pathway.image_url} 
                        alt={pathway.title}
                        className="w-full h-auto cursor-pointer hover:opacity-90 transition-opacity"
                        onClick={() => setFullscreenImage(pathway.image_url)}
                      />
                    </div>
                  </div>
                </CollapsibleContent>
              )}
            </div>
          </Collapsible>
        </Card>
      ))}

      <Dialog open={!!fullscreenImage} onOpenChange={() => setFullscreenImage(null)}>
        <DialogContent className="max-w-[95vw] max-h-[95vh] p-0 overflow-auto">
          <DialogClose className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground z-10 bg-background/80 backdrop-blur-sm p-2">
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </DialogClose>
          {fullscreenImage && (
            <img 
              src={fullscreenImage} 
              alt="Pathway full view"
              className="w-full h-auto"
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};