import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Send } from "lucide-react";

interface QueryInputProps {
  onSendMessage: (query: string) => void;
}

export const QueryInput = ({ onSendMessage }: QueryInputProps) => {
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSendMessage(query.trim());
      setQuery("");
    }
  };

  return (
    <div className="border-t border-border bg-white shadow-lg">
      <form onSubmit={handleSubmit} className="max-w-4xl mx-auto p-4">
        <div className="flex gap-3">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a scientific question (e.g., 'What happens to EGFR in microgravity?')"
            className="flex-1 bg-secondary border-border focus:ring-2 focus:ring-primary text-base"
          />
          <Button 
            type="submit" 
            className="bg-primary hover:bg-primary/90 text-primary-foreground px-6"
            disabled={!query.trim()}
          >
            <Send className="h-4 w-4 mr-2" />
            Ask
          </Button>
        </div>
      </form>
    </div>
  );
};
