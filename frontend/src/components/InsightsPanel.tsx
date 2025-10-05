import { useEffect, useRef } from "react";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatMessage } from "@/types/chat";
import { Loader2, CheckCircle, AlertCircle } from "lucide-react";

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
          {messages.map((message) => (
            <div key={message.id} className="animate-fade-in">
              {message.role === 'user' ? (
                <Card className="bg-secondary border-border shadow-sm p-4 ml-auto max-w-[85%]">
                  <p className="text-sm text-foreground">{message.content}</p>
                </Card>
              ) : (
                <div className="space-y-4 max-w-full">
                  {/* Loading States */}
                  {message.isLoading && (
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
                                <p key={idx} className="text-sm text-foreground">
                                  {func}
                                </p>
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
                        {message.researchSummary.relevant_papers.length > 0 && (
                          <div>
                            <h4 className="font-semibold text-foreground mb-2">Relevant Papers:</h4>
                            <div className="space-y-1">
                              {message.researchSummary.relevant_papers.map((paper, idx) => (
                                <a 
                                  key={idx} 
                                  href={paper} 
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                  className="block text-sm text-primary hover:underline"
                                >
                                  {paper}
                                </a>
                              ))}
                            </div>
                          </div>
                        )}
                        <div className="text-xs text-muted-foreground">
                          Sources: {message.researchSummary.source_count}
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
                          <span className="text-sm text-foreground ml-1">
                            {message.proteinData.functions}
                          </span>
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

                  {/* Basic content if no structured data */}
                  {message.content && !message.proteinInfo && !message.proteinData && (
                    <Card className="bg-white border border-border shadow-sm p-4">
                      <p className="text-sm text-foreground">{message.content}</p>
                    </Card>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
};
