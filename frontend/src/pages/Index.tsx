import { useState } from "react";
import { InsightsPanel } from "@/components/InsightsPanel";
import { ExplorerPanel } from "@/components/ExplorerPanel";
import { QueryInput } from "@/components/QueryInput";
import { ChatMessage } from "@/types/chat";
import { useQueryWorkflow } from "@/hooks/useQueryWorkflow";

const Index = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

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
