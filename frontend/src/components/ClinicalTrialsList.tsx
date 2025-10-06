import { useState } from "react";
import { Card } from "@/components/ui/card";
import { ChevronDown, ChevronUp, ExternalLink, Users, Activity, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ClinicalStudy } from "@/types/api";

interface ClinicalTrialsListProps {
  clinicalStudies?: ClinicalStudy[];
  isLoading?: boolean;
}

export const ClinicalTrialsList = ({ clinicalStudies = [], isLoading = false }: ClinicalTrialsListProps) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Debug: Log the clinical studies data to see what we're receiving
  console.log('ClinicalTrialsList - clinicalStudies:', clinicalStudies);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Loading clinical studies...</span>
        </div>
      </div>
    );
  }

  if (!clinicalStudies || clinicalStudies.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-muted-foreground">
          <p>No clinical studies available</p>
          <p className="text-sm">Ask a question about a protein to see related clinical trials</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      {/* Header with sorting info */}
      <div className="mb-4 px-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-muted-foreground">
            Clinical Studies ({clinicalStudies.length})
          </h2>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Activity className="h-3 w-3" />
            <span>Sorted by publication year (latest first)</span>
          </div>
        </div>
      </div>
      
      <div className="space-y-4">
        {clinicalStudies.map((study, index) => {
          // Debug: Log each study to see the publication_year
          console.log(`Study ${index}:`, study, 'Publication year:', study.publication_year);
          return (
        <Card 
          key={study.nct_id || index} 
          className="bg-white border border-border shadow-sm hover:shadow-md transition-all duration-300 hover-scale overflow-hidden"
        >
          <div className="p-6">
            {/* Header Section */}
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1 pr-4">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-base font-semibold text-foreground leading-snug">
                    {study.title}
                  </h3>
                  {study.publication_year && 
                   parseInt(study.publication_year) >= new Date().getFullYear() - 1 && (
                    <Badge variant="default" className="text-xs px-2 py-0.5">
                      Recent
                    </Badge>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <div className="text-xs text-muted-foreground mb-1">Published</div>
                  <Badge variant="outline" className="text-sm font-medium px-3 py-1">
                    {study.publication_year || "N/A"}
                  </Badge>
                </div>
                <button
                  onClick={() => toggleExpand(study.nct_id || index.toString())}
                  className="text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
                  aria-label="Toggle details"
                >
                  {expandedId === (study.nct_id || index.toString()) ? (
                    <ChevronUp className="h-5 w-5" />
                  ) : (
                    <ChevronDown className="h-5 w-5" />
                  )}
                </button>
              </div>
            </div>


            {/* Expandable Summary */}
            {expandedId === (study.nct_id || index.toString()) && study.brief_summary && (
              <div className="animate-accordion-down">
                <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                  Brief Summary
                </h4>
                <p className="text-sm text-foreground leading-relaxed mb-4">
                  {study.brief_summary}
                </p>
              </div>
            )}

            {/* Footer Links */}
            <div className="flex items-center justify-between pt-3 border-t border-border">
              <a
                href={study.link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary transition-colors"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                <span className="font-mono">{study.nct_id}</span>
              </a>
            </div>
          </div>
        </Card>
          );
        })}
      </div>
    </div>
  );
};
