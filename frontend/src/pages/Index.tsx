import { useState } from "react";
import { InsightsPanel } from "@/components/InsightsPanel";
import { ExplorerPanel } from "@/components/ExplorerPanel";
import { QueryInput } from "@/components/QueryInput";
import { ChatMessage } from "@/types/chat";
import { useQueryWorkflow } from "@/hooks/useQueryWorkflow";

const Index = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      role: 'user',
      content: 'What happens to EGFR in microgravity?',
      timestamp: new Date(),
    },
    {
      id: '2',
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      proteinData: {
        name: 'EGFR',
        alternateNames: [
          'Proto-oncogene c-ErbB-1',
          'Receptor tyrosine-protein kinase erbB-1',
        ],
        functions: 'Receptor tyrosine kinase binding ligands of the EGF family and activating several signaling pathways...',
        summary: 'In microgravity, epidermal growth factor receptor (EGFR) signal transduction is inhibited downstream of receptor redistribution, leading to suppressed early gene expression like c-fos and c-jun. This inhibition appears to stem from microgravity\'s impact on the actin cytoskeleton and protein kinase C (PKC) signaling, as EGFR binding and clustering are not significantly affected.',
        sources: ['[1]', '[2]', '[3]'],
      },
    },
  ]);

  const { processQuery, isLoading, error } = useQueryWorkflow();

  const handleSendMessage = async (query: string) => {
    // Add user message immediately
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: query,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);

    // Process query and get assistant response
    try {
      const assistantMessage = await processQuery(query);
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Query processing failed:', error);
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your query. Please try again.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-background">
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-0 overflow-hidden">
        <div className="border-r border-border overflow-hidden">
          <InsightsPanel messages={messages} />
        </div>
        <div className="overflow-hidden">
          <ExplorerPanel messages={messages} />
        </div>
      </div>
      <QueryInput onSendMessage={handleSendMessage} />
    </div>
  );
};

export default Index;
