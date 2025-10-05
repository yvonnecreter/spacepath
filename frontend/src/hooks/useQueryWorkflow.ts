import { useState, useCallback } from 'react';
import { apiService } from '@/services/api';
import { ChatMessage } from '@/types/chat';
import { ProteinInfoResponse, Pathway, ResearchSummaryResponse } from '@/types/api';

export interface QueryWorkflowState {
  isLoading: boolean;
  error: string | null;
  currentStep: 'extracting' | 'protein-info' | 'pathways' | 'research' | 'complete';
}

export const useQueryWorkflow = () => {
  const [state, setState] = useState<QueryWorkflowState>({
    isLoading: false,
    error: null,
    currentStep: 'complete',
  });

  const processQuery = useCallback(async (query: string): Promise<ChatMessage> => {
    setState({
      isLoading: true,
      error: null,
      currentStep: 'extracting',
    });

    try {
      // Create initial assistant message with loading state
      const assistantMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isLoading: {
          proteinInfo: true,
          pathways: true,
          researchSummary: true,
        },
      };

      // Step 1: Extract protein name
      setState(prev => ({ ...prev, currentStep: 'extracting' }));
      const proteinNameResponse = await apiService.extractProteinName(query);
      const proteinName = proteinNameResponse.protein_name;

      // Update message with protein name
      assistantMessage.content = `I found the protein: ${proteinName}. Let me gather more information...`;

      // Step 2 & 3: Get protein info and pathways in parallel
      setState(prev => ({ ...prev, currentStep: 'protein-info' }));
      
      const [proteinInfoResult, pathwaysResult] = await Promise.allSettled([
        apiService.getProteinInfo(proteinName),
        apiService.getPathways(proteinName),
      ]);

      // Update with protein info if successful
      if (proteinInfoResult.status === 'fulfilled') {
        assistantMessage.proteinInfo = proteinInfoResult.value.protein_info;
        assistantMessage.clinicalStudies = proteinInfoResult.value.clinical_studies.clinical_studies;
        assistantMessage.isLoading!.proteinInfo = false;
      }

      // Update with pathways if successful
      if (pathwaysResult.status === 'fulfilled') {
        assistantMessage.pathways = pathwaysResult.value;
        assistantMessage.isLoading!.pathways = false;
      }

      // Step 4: Get research summary (this takes longer)
      setState(prev => ({ ...prev, currentStep: 'research' }));
      
      try {
        const researchSummary = await apiService.getResearchSummary(query);
        assistantMessage.researchSummary = researchSummary;
        assistantMessage.isLoading!.researchSummary = false;
        
        // Update content with the research summary
        assistantMessage.content = researchSummary.summary;
      } catch (error) {
        console.error('Failed to get research summary:', error);
        assistantMessage.isLoading!.researchSummary = false;
        assistantMessage.content = `I found information about ${proteinName}, but I'm having trouble generating a research summary. Please try again.`;
      }

      setState({
        isLoading: false,
        error: null,
        currentStep: 'complete',
      });

      return assistantMessage;

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'An unknown error occurred';
      
      setState({
        isLoading: false,
        error: errorMessage,
        currentStep: 'complete',
      });

      return {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Sorry, I encountered an error: ${errorMessage}`,
        timestamp: new Date(),
        isLoading: {
          proteinInfo: false,
          pathways: false,
          researchSummary: false,
        },
      };
    }
  }, []);

  return {
    ...state,
    processQuery,
  };
};
