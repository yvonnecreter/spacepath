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
                  ProteinLens - By SpacePath
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
                      "How do inflammatory cytokines like TNF-α and IL-6 change in microgravity?"
                    </p>
                  </div>
                  <div className="bg-secondary/50 border border-border rounded-lg p-4 text-left">
                    <p className="text-sm text-foreground font-mono">
                      "How does BDNF expression change in neural stem cells during spaceflight?"
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
                    <Card className="bg-gradient-to-br from-primary/10 to-primary/20 border-2 border-primary/30 shadow-xl p-4 space-y-3 relative overflow-hidden">
                      {/* Header with icon and title */}
                      <div className="flex items-center gap-2 mb-3">
                        <div className="p-1.5 bg-primary/20 rounded-md">
                          <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                          </svg>
                        </div>
                        <div>
                          <h2 className="text-sm font-bold text-primary">Protein Information</h2>
                          <p className="text-xs text-muted-foreground">Detailed information about the identified protein</p>
                        </div>
                      </div>
                      
                      {/* Protein name highlight */}
                      <div className="bg-primary/10 border border-primary/30 rounded-lg p-3 text-center">
                        <div className="text-xs font-medium text-primary/70 uppercase tracking-wide mb-1">Primary Protein</div>
                        <div className="text-base font-bold text-primary">
                          {message.proteinInfo.protein_name}
                        </div>
                      </div>

                      {/* Protein Details */}
                      <div className="bg-white/50 backdrop-blur-sm border border-primary/20 rounded-lg p-3 space-y-3">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div className="bg-primary/5 border border-primary/20 rounded-md p-2">
                            <h3 className="font-semibold text-primary text-xs mb-1 flex items-center gap-1">
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                              </svg>
                              Accession ID
                            </h3>
                            <p className="text-xs text-foreground font-mono bg-white/50 px-2 py-1 rounded border">
                              {message.proteinInfo.accession}
                            </p>
                          </div>
                          
                          {message.proteinInfo.alternate_names.length > 0 && (
                            <div className="bg-primary/5 border border-primary/20 rounded-md p-2">
                              <h3 className="font-semibold text-primary text-xs mb-1 flex items-center gap-1">
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                                </svg>
                                Alternate Names
                              </h3>
                              <ol className="list-decimal list-inside space-y-0.5 text-xs text-foreground">
                                {message.proteinInfo.alternate_names.map((name, idx) => (
                                  <li key={idx} className="bg-white/50 px-1.5 py-0.5 rounded text-xs">{name}</li>
                                ))}
                              </ol>
                            </div>
                          )}
                        </div>

                        {message.proteinInfo.synonyms.length > 0 && (
                          <div className="bg-primary/5 border border-primary/20 rounded-md p-2">
                            <h3 className="font-semibold text-primary text-xs mb-1 flex items-center gap-1">
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                              </svg>
                              Gene Synonyms
                            </h3>
                            <div className="flex flex-wrap gap-1">
                              {message.proteinInfo.synonyms.map((synonym, idx) => (
                                <span key={idx} className="bg-white/50 px-1.5 py-0.5 rounded text-xs border">
                                  {synonym}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {message.proteinInfo.functions.length > 0 && (
                          <div className="bg-primary/5 border border-primary/20 rounded-md p-2">
                            <h3 className="font-semibold text-primary text-xs mb-1 flex items-center gap-1">
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                              </svg>
                              Biological Functions
                            </h3>
                            <div className="space-y-1">
                              {message.proteinInfo.functions.map((func, idx) => (
                                <div key={idx} className="bg-white/50 border rounded p-2">
                                  <TruncatedText 
                                    text={func}
                                    maxSentences={2}
                                    className="text-xs text-foreground leading-tight"
                                  />
                                </div>
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
