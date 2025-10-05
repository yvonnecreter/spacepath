import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RelationshipsGraph } from "./RelationshipsGraph";
import { PathwaysViewer } from "./PathwaysViewer";
import { ClinicalTrialsList } from "./ClinicalTrialsList";
import { ChatMessage } from "@/types/chat";

interface ExplorerPanelProps {
  messages: ChatMessage[];
}

export const ExplorerPanel = ({ messages }: ExplorerPanelProps) => {
  const [activeTab, setActiveTab] = useState("pathways");

  // Get the latest assistant message with data
  const latestMessage = messages
    .filter(msg => msg.role === 'assistant')
    .pop();

  const pathways = latestMessage?.pathways || [];
  const clinicalStudies = latestMessage?.clinicalStudies || [];
  const isLoadingPathways = latestMessage?.isLoading?.pathways || false;
  const isLoadingClinical = latestMessage?.isLoading?.proteinInfo || false;

  return (
    <div className="h-full flex flex-col">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
        <div className="px-6 pt-6">
          <TabsList className="grid w-full grid-cols-3 bg-white border border-border shadow-sm">

            <TabsTrigger 
              value="pathways"
              className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-lg transition-all"
            >
              Pathways
            </TabsTrigger>
            <TabsTrigger 
              value="trials"
              className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-lg transition-all"
            >
              Clinical Trials
            </TabsTrigger>
            <TabsTrigger 
              value="relationships"
              className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground rounded-lg transition-all"
            >
              Relationships
            </TabsTrigger>

          </TabsList>
        </div>

        <div className="flex-1 overflow-auto">
          <TabsContent value="relationships" className="h-full mt-0 p-6">
            <RelationshipsGraph />
          </TabsContent>
          <TabsContent value="pathways" className="h-full mt-0 p-6">
            <PathwaysViewer pathways={pathways} isLoading={isLoadingPathways} />
          </TabsContent>
          <TabsContent value="trials" className="h-full mt-0 p-6">
            <ClinicalTrialsList clinicalStudies={clinicalStudies} isLoading={isLoadingClinical} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
};
