import { useEffect, useRef } from "react";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatMessage } from "@/types/chat";
import { Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { TruncatedText } from "@/components/ui/truncated-text";

interface InsightsPanelProps {
  messages: ChatMessage[];
}

export const InsightsPanel = ({ messages }: InsightsPanelProps) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  return (
    <div className="h-full flex flex-col bg-background">
      <div className="p-6 border-b border-border">
        <h2 className="text-2xl font-semibold text-foreground">Space Path</h2>
      </div>
      
      <ScrollArea className="flex-1">
        <div ref={scrollRef} className="p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center space-y-6">
              <div className="space-y-4">
                <h3 className="text-3xl font-bold text-foreground">
                  SpacePath
                </h3>
                <p className="text-lg text-muted-foreground max-w-md">
                  Turning NASA's space biology data into actionable insights for pharma and life sciences.
                </p>
              </div>
              
              <div className="space-y-4 w-full max-w-lg">
                <p className="text-sm font-medium text-foreground">
                  Ask questions like:
                </p>
                <div className="space-y-3">
                  <div className="bg-secondary/50 border border-border rounded-lg p-4 text-left">
                    <p className="text-sm text-foreground font-mono">
                      "How does microgravity affect EGFR?"
                    </p>
                  </div>
                  <div className="bg-secondary/50 border border-border rounded-lg p-4 text-left">
                    <p className="text-sm text-foreground font-mono">
                      "Show protein pathways altered in space conditions."
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            messages.map((message) => (
            <div key={message.id} className="animate-fade-in">
              {message.role === 'user' ? (
                <Card className="bg-secondary border-border shadow-sm p-4 ml-auto max-w-[85%]">
                  <p className="text-sm text-foreground">{message.content}</p>
                </Card>
              ) : (
                <div className="space-y-4 max-w-full">
                  {/* Loading States */}
                  {message.isLoading && (message.isLoading.proteinInfo || message.isLoading.pathways || message.isLoading.researchSummary) && (
                    <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20 shadow-lg p-6 space-y-4">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>Processing your query...</span>
                      </div>
                      
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 text-xs">
                          {message.isLoading.proteinInfo ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <CheckCircle className="h-3 w-3 text-green-500" />
                          )}
                          <span>Protein Information</span>
                        </div>
                        <div className="flex items-center gap-2 text-xs">
                          {message.isLoading.pathways ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <CheckCircle className="h-3 w-3 text-green-500" />
                          )}
                          <span>Pathways</span>
                        </div>
                        <div className="flex items-center gap-2 text-xs">
                          {message.isLoading.researchSummary ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <CheckCircle className="h-3 w-3 text-green-500" />
                          )}
                          <span>Research Summary</span>
                        </div>
                      </div>
                    </Card>
                  )}

                  {/* Protein Information */}
                  {message.proteinInfo && (
                    <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20 shadow-lg p-6 space-y-4">
                      <div className="inline-block px-4 py-2 bg-background border border-border rounded-lg">
                        <span className="font-semibold text-foreground">
                          Protein: {message.proteinInfo.protein_name}
                        </span>
                      </div>

                      <div className="bg-background border border-border rounded-lg p-4 space-y-3">
                        <div>
                          <h3 className="font-bold text-foreground mb-2">Accession:</h3>
                          <p className="text-sm text-foreground font-mono">{message.proteinInfo.accession}</p>
                        </div>
                        
                        {message.proteinInfo.alternate_names.length > 0 && (
                          <div>
                            <h3 className="font-bold text-foreground mb-2">Alternate names:</h3>
                            <ol className="list-decimal list-inside space-y-1 text-sm text-foreground">
                              {message.proteinInfo.alternate_names.map((name, idx) => (
                                <li key={idx}>{name}</li>
                              ))}
                            </ol>
                          </div>
                        )}

                        {message.proteinInfo.synonyms.length > 0 && (
                          <div>
                            <h3 className="font-bold text-foreground mb-2">Synonyms:</h3>
                            <p className="text-sm text-foreground">
                              {message.proteinInfo.synonyms.join(', ')}
                            </p>
                          </div>
                        )}

                        {message.proteinInfo.functions.length > 0 && (
                          <div>
                            <h3 className="font-bold text-foreground mb-2">Functions:</h3>
                            <div className="space-y-2">
                              {message.proteinInfo.functions.map((func, idx) => (
                                <TruncatedText 
                                  key={idx} 
                                  text={func}
                                  maxSentences={2}
                                  className="text-sm text-foreground"
                                />
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </Card>
                  )}

                  {/* Research Summary */}
                  {message.researchSummary && (
                    <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200 shadow-lg p-6">
                      <div className="space-y-3">
                        <div className="flex items-center gap-2">
                          <CheckCircle className="h-5 w-5 text-green-500" />
                          <h3 className="font-bold text-foreground">Research Summary</h3>
                        </div>
                        <p className="text-sm leading-relaxed text-foreground">
                          {message.researchSummary.summary}
                        </p>
                        <div className="flex justify-between items-end">
                          <div className="text-xs text-muted-foreground">
                            {/* Sources: {message.researchSummary.source_count} */}
                          </div>
                          {message.researchSummary.relevant_papers.length > 0 && (
                            <div className="flex gap-1">
                              {message.researchSummary.relevant_papers.map((paper, idx) => (
                                <a 
                                  key={idx} 
                                  href={paper} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="text-xs text-primary hover:underline font-mono"
                                >
                                  [{idx + 1}]
                                </a>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </Card>
                  )}

                  {/* Fallback for old proteinData structure */}
                  {message.proteinData && !message.proteinInfo && (
                    <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20 shadow-lg p-6 space-y-4">
                      <div className="inline-block px-4 py-2 bg-background border border-border rounded-lg">
                        <span className="font-semibold text-foreground">
                          Protein: {message.proteinData.name}
                        </span>
                      </div>

                      <div className="bg-background border border-border rounded-lg p-4 space-y-3">
                        <h3 className="font-bold text-foreground">Alternate names:</h3>
                        <ol className="list-decimal list-inside space-y-1 text-sm text-foreground">
                          {message.proteinData.alternateNames.map((name, idx) => (
                            <li key={idx}>{name}</li>
                          ))}
                        </ol>
                        <div className="pt-2">
                          <span className="font-bold text-foreground">Functions:</span>
                          <TruncatedText 
                            text={message.proteinData.functions}
                            maxSentences={2}
                            className="text-sm text-foreground ml-1"
                          />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <p className="text-sm leading-relaxed text-foreground">
                          <span className="font-bold">Summary:</span> {message.proteinData.summary}
                        </p>
                        <div className="text-right">
                          <span className="text-xs text-muted-foreground">
                            Source{' '}
                            {message.proteinData.sources.map((source, idx) => (
                              <a key={idx} href="#" className="text-primary hover:underline">
                                {source}
                              </a>
                            ))}
                          </span>
                        </div>
                      </div>
                    </Card>
                  )}

                  {/* Basic content if no structured data - only show if no research summary */}
                  {message.content && !message.proteinInfo && !message.proteinData && !message.researchSummary && (
                    <Card className="bg-white border border-border shadow-sm p-4">
                      <p className="text-sm text-foreground">{message.content}</p>
                    </Card>
                  )}
                </div>
              )}
            </div>
          ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
};
