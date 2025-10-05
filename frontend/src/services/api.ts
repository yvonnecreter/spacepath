import { 
  QueryRequest, 
  ProteinRequest, 
  ProteinNameResponse, 
  ProteinInfoResponse, 
  Pathway, 
  ResearchSummaryResponse 
} from '@/types/api';

const API_BASE_URL = 'http://localhost:8000'; // Update this to match your backend URL

class ApiService {
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    
    const defaultOptions: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, defaultOptions);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error(`API request failed for ${endpoint}:`, error);
      throw error;
    }
  }

  /**
   * Step 1: Extract protein name from user query
   */
  async extractProteinName(query: string): Promise<ProteinNameResponse> {
    return this.request<ProteinNameResponse>('/query', {
      method: 'POST',
      body: JSON.stringify({ query }),
    });
  }

  /**
   * Step 2: Get protein information and clinical studies
   */
  async getProteinInfo(proteinName: string): Promise<ProteinInfoResponse> {
    return this.request<ProteinInfoResponse>('/get-protein-info', {
      method: 'POST',
      body: JSON.stringify({ protein_name: proteinName }),
    });
  }

  /**
   * Step 3: Get pathways for the protein
   */
  async getPathways(proteinName: string): Promise<Pathway[]> {
    return this.request<Pathway[]>('/get-pathways', {
      method: 'POST',
      body: JSON.stringify({ protein_name: proteinName }),
    });
  }

  /**
   * Step 4: Get research summary (RAG response)
   */
  async getResearchSummary(query: string): Promise<ResearchSummaryResponse> {
    return this.request<ResearchSummaryResponse>('/get-research-summary', {
      method: 'POST',
      body: JSON.stringify({ query }),
    });
  }

  /**
   * Complete workflow: Process query through all steps
   * This method orchestrates the entire workflow with proper loading states
   */
  async processCompleteQuery(query: string): Promise<{
    proteinName: string;
    proteinInfo: ProteinInfoResponse | null;
    pathways: Pathway[] | null;
    researchSummary: ResearchSummaryResponse | null;
  }> {
    try {
      // Step 1: Extract protein name
      const proteinNameResponse = await this.extractProteinName(query);
      const proteinName = proteinNameResponse.protein_name;

      // Step 2 & 3: Get protein info and pathways in parallel (faster)
      const [proteinInfo, pathways] = await Promise.all([
        this.getProteinInfo(proteinName).catch(error => {
          console.error('Failed to get protein info:', error);
          return null;
        }),
        this.getPathways(proteinName).catch(error => {
          console.error('Failed to get pathways:', error);
          return null;
        })
      ]);

      // Step 4: Get research summary (this takes longer, so we return what we have)
      const researchSummary = await this.getResearchSummary(query).catch(error => {
        console.error('Failed to get research summary:', error);
        return null;
      });

      return {
        proteinName,
        proteinInfo,
        pathways,
        researchSummary,
      };
    } catch (error) {
      console.error('Complete query processing failed:', error);
      throw error;
    }
  }
}

export const apiService = new ApiService();
