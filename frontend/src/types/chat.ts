import { ProteinInfo, ClinicalStudy, Pathway, ResearchSummaryResponse } from './api';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  proteinData?: {
    name: string;
    alternateNames: string[];
    functions: string;
    summary: string;
    sources: string[];
  };
  // New fields for API integration
  proteinInfo?: ProteinInfo;
  clinicalStudies?: ClinicalStudy[];
  pathways?: Pathway[];
  researchSummary?: ResearchSummaryResponse;
  isLoading?: {
    proteinInfo: boolean;
    pathways: boolean;
    researchSummary: boolean;
  };
}
