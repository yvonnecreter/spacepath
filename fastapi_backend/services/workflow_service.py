"""
Workflow Service for SPACEPATH Backend

This service orchestrates the complete workflow:
1. Extract protein name from user query
2. Get protein information and clinical studies
3. Generate RAG response from research papers
"""

from typing import Optional, Dict, Any, Tuple, List
from fastapi_backend.services.llm_service import LLMService
from fastapi_backend.utils.query_processor import extract_protein_name
from fastapi_backend.utils.extract_protein_details import extract_protein_details
from fastapi_backend.utils.get_clinical_studies import get_protein_clinical_studies
from fastapi_backend.utils.get_pathways import get_human_kegg_pathways_for_gene
from fastapi_backend.schema_models.model import ProteinInfo, ClinicalStudiesResponse
from fastapi_backend.rag_module.vanilla_rag import VanillaRAGPipeline

import logging

logger = logging.getLogger(__name__)

class WorkflowService:
    """
    Main workflow service that orchestrates the complete process
    """
    
    def __init__(self, llm_svc: LLMService, rag_pipeline: VanillaRAGPipeline):
        self.llm_svc = llm_svc
        self.rag_pipeline = rag_pipeline
        self.rag_qa = rag_pipeline.setup_qa_chain()
    
    async def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a user query through the complete workflow:
        1. Extract protein name
        2. Get protein info and clinical studies
        3. Generate RAG response
        
        Args:
            query: User's query string
            
        Returns:
            Dictionary containing all results
        """
        logger.info(f"Processing query: {query}")
        
        # Step 1: Extract protein name from query
        protein_name = extract_protein_name(query, self.llm_svc)
        
        result = {
            "query": query,
            "protein_name": protein_name,
            "protein_info": None,
            "clinical_studies": None,
            "rag_response": None,
            "pathways": None,
            "error": None
        }
        
        try:
            # Step 2: Get protein information and clinical studies (if protein found)
            if protein_name:
                logger.info(f"Extracted protein: {protein_name}")
                try:
                    protein_info, clinical_studies = get_protein_clinical_studies(protein_name)
                    pathways = get_human_kegg_pathways_for_gene(protein_name)
                    result["protein_info"] = protein_info
                    result["clinical_studies"] = clinical_studies
                    result["pathways"] = pathways
                    logger.info(f"Successfully retrieved info for {protein_name}")
                except Exception as e:
                    logger.error(f"Error getting protein info for {protein_name}: {e}")
                    result["error"] = f"Failed to retrieve protein information: {str(e)}"
            else:
                logger.info("No protein name extracted from query")
            
            # Step 3: Generate RAG response
            try:
                rag_output = self.rag_qa.invoke({"query": query})
                summary = rag_output['result']
                sources = rag_output['source_documents']
                
                # Extract unique research papers from sources
                unique_papers = set()
                for source in sources:
                    if 'title' in source.metadata:
                        unique_papers.add(source.metadata['title'])
                
                result["rag_response"] = {
                    "summary": summary,
                    "relevant_papers": list(unique_papers),
                    "source_count": len(sources)
                }
                logger.info("Successfully generated RAG response")
                
            except Exception as e:
                logger.error(f"Error generating RAG response: {e}")
                result["error"] = f"Failed to generate research summary: {str(e)}"
        
        except Exception as e:
            logger.error(f"Unexpected error in workflow: {e}")
            result["error"] = f"Unexpected error: {str(e)}"
        
        return result

    def get_pathways_for_protein(self, protein_name: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Get pathways for a specific protein.
        """
        try:
            return get_human_kegg_pathways_for_gene(protein_name)
        except Exception as e:
            logger.error(f"Error getting pathways for {protein_name}: {e}")
            return None, None
    
    def get_protein_only_info(self, protein_name: str) -> Tuple[Optional[ProteinInfo], Optional[ClinicalStudiesResponse]]:
        """
        Get only protein information and clinical studies for a specific protein.
        
        Args:
            protein_name: Name of the protein
            
        Returns:
            Tuple of (protein_info, clinical_studies) or (None, None) if error
        """
        try:
            return get_protein_clinical_studies(protein_name)
        except Exception as e:
            logger.error(f"Error getting protein info for {protein_name}: {e}")
            return None, None
    
    def get_rag_only_response(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Get only RAG response for a query.
        
        Args:
            query: User's query string
            
        Returns:
            Dictionary with RAG response or None if error
        """
        try:
            rag_output = self.rag_qa.invoke({"query": query})
            summary = rag_output['result']
            sources = rag_output['source_documents']
            
            # Extract unique research papers from sources
            unique_papers = set()
            for source in sources:
                if 'title' in source.metadata:
                    unique_papers.add(source.metadata['title'])
            
            return {
                "summary": summary,
                "relevant_papers": list(unique_papers),
                "source_count": len(sources)
            }
        except Exception as e:
            logger.error(f"Error generating RAG response: {e}")
            return None
