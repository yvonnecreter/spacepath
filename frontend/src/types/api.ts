// API Response Types
export interface ProteinNameResponse {
  protein_name: string;
}

export interface ProteinInfo {
  protein_name: string;
  accession: string;
  alternate_names: string[];
  synonyms: string[];
  functions: string[];
}

export interface ClinicalStudy {
  nct_id: string;
  title: string;
  brief_summary: string;
  link: string;
}

export interface ClinicalStudiesResponse {
  clinical_studies: ClinicalStudy[];
}

export interface Pathway {
  pathway_id: string;
  title: string;
  page_url: string;
  image_url: string;
}

export interface ResearchSummaryResponse {
  summary: string;
  relevant_papers: string[];
  source_count: number;
}

export interface ProteinInfoResponse {
  protein_info: ProteinInfo;
  clinical_studies: ClinicalStudiesResponse;
}

// API Request Types
export interface QueryRequest {
  query: string;
}

export interface ProteinRequest {
  protein_name: string;
}

// Combined response for the complete workflow
export interface CompleteWorkflowResponse {
  protein_name: string;
  protein_info: ProteinInfo;
  clinical_studies: ClinicalStudiesResponse;
  pathways: Pathway[];
  research_summary: ResearchSummaryResponse;
}
