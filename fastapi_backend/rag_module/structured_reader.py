"""
Custom Structured Reader for Biological Information Extraction

This module provides a structured reader that extracts biological information
from text using LLM with structured output capabilities.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
from langchain.schema import Document
logger = logging.getLogger(__name__)


class BiologicalEffect(BaseModel):
    """Schema for biological effect extraction"""
    protein: str = Field(description="The protein or gene name (e.g., EGFR, p53)")
    condition: str = Field(description="The experimental condition (e.g., Microgravity, Spaceflight)")
    modification: str = Field(description="The specific biological modification or effect observed")
    pathway: str = Field(description="The biological pathway or process involved")
    papers: List[str] = Field(description="List of paper IDs that contain this information")


class StructuredReader:
    """
    Custom structured reader that extracts biological information from documents
    using LLM with structured output capabilities.
    """
    
    def __init__(self, llm_service):
        """
        Initialize the structured reader.
        
        Args:
            llm_service: LLMService instance for structured output
        """
        self.llm_service = llm_service
        self.schema = BiologicalEffect
    
    def extract_biological_effects(self, 
                                 documents: List[Document], 
                                 target_protein: str = "EGFR",
                                 condition: str = "Microgravity",
                                 max_effects: int = 10) -> List[BiologicalEffect]:
        """
        Extract biological effects from a list of documents.
        
        Args:
            documents: List of Document objects to extract from
            target_protein: Target protein to focus on (default: EGFR)
            condition: Experimental condition to focus on (default: Microgravity)
            max_effects: Maximum number of effects to extract
            
        Returns:
            List of BiologicalEffect objects
        """
        if not documents:
            logger.warning("No documents provided for extraction")
            return []
        
        # Combine document content
        combined_text = self._combine_documents(documents)
        
        # Create extraction prompt
        prompt = self._create_extraction_prompt(
            text=combined_text,
            target_protein=target_protein,
            condition=condition,
            max_effects=max_effects
        )
        
        try:
            # Use structured output to extract information
            formatter = self.llm_service.llm_provider.with_structured_output(self.schema)
            result = formatter.invoke(prompt)
            
            # Handle both single result and list of results
            if isinstance(result, list):
                return result[:max_effects]
            else:
                return [result] if result else []
                
        except Exception as e:
            logger.error(f"Error in structured extraction: {str(e)}")
            return []
    
    def extract_from_query(self, 
                          query: str, 
                          rag_pipeline,
                          target_protein: str = "EGFR",
                          condition: str = "Microgravity",
                          top_k: int = 5) -> List[BiologicalEffect]:
        """
        Extract biological effects by first retrieving relevant documents using RAG.
        
        Args:
            query: Search query
            rag_pipeline: VanillaRAGPipeline instance
            target_protein: Target protein to focus on
            condition: Experimental condition to focus on
            top_k: Number of documents to retrieve
            
        Returns:
            List of BiologicalEffect objects
        """
        # Retrieve relevant documents
        documents, _ = rag_pipeline.retrieve_documents(query, top_k_docs=top_k)
        
        if not documents:
            logger.warning("No relevant documents found for query")
            return []
        
        # Extract biological effects
        return self.extract_biological_effects(
            documents=documents,
            target_protein=target_protein,
            condition=condition
        )
    
    def extract_from_papers(self, 
                           query: str, 
                           rag_pipeline,
                           target_protein: str = "EGFR",
                           condition: str = "Microgravity",
                           top_k: int = 5) -> List[BiologicalEffect]:
        """
        Extract biological effects by first retrieving relevant papers using RAG.
        
        Args:
            query: Search query
            rag_pipeline: VanillaRAGPipeline instance
            target_protein: Target protein to focus on
            condition: Experimental condition to focus on
            top_k: Number of papers to retrieve
            
        Returns:
            List of BiologicalEffect objects
        """
        # Search for relevant papers
        papers = rag_pipeline.search_papers(query, top_k=top_k)
        
        if not papers:
            logger.warning("No relevant papers found for query")
            return []
        
        # Convert paper results to Document objects
        documents = []
        for paper in papers:
            # Create a document from paper data
            content = f"""
            Title: {paper['title']}
            Abstract: {paper['abstract']}
            Results: {paper['results']}
            Keywords: {paper['keywords']}
            """
            
            doc = Document(
                page_content=content,
                metadata={
                    'paper_id': paper['paper_id'],
                    'title': paper['title'],
                    'link': paper['link'],
                    'authors': paper['authors']
                }
            )
            documents.append(doc)
        
        # Extract biological effects
        return self.extract_biological_effects(
            documents=documents,
            target_protein=target_protein,
            condition=condition
        )
    
    def _combine_documents(self, documents: List[Document]) -> str:
        """Combine multiple documents into a single text for processing."""
        combined_parts = []
        
        for i, doc in enumerate(documents):
            # Add document separator
            combined_parts.append(f"--- Document {i+1} ---")
            combined_parts.append(f"Content: {doc.page_content}")


            # Add metadata if available
            if doc.metadata:
                metadata_str = ", ".join([f"{k}: {v}" for k, v in doc.metadata.items()])
                combined_parts.append(f"Metadata: {metadata_str}")
            
            combined_parts.append("")  # Empty line between documents
        
        return "\n".join(combined_parts)
    
    def _create_extraction_prompt(self, 
                                text: str, 
                                target_protein: str, 
                                condition: str,
                                max_effects: int) -> str:
        """Create the extraction prompt for the LLM."""
        return f"""
Extract from the following texts any described biological effects on {target_protein} under {condition} conditions. 

Focus on:
- Protein modifications (phosphorylation, acetylation, etc.)
- Expression changes (upregulation, downregulation)
- Functional changes (activity, binding, localization)
- Pathway involvement
- Molecular mechanisms

Return a JSON with fields [Protein, Condition, Modification, Pathway, Papers].

If multiple effects are found, extract up to {max_effects} distinct effects.

Text to analyze:
{text}

Please provide structured information about biological effects on {target_protein} under {condition} conditions.
"""
