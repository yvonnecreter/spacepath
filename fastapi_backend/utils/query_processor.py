from fastapi_backend.services.llm_service import LLMService
from pydantic import BaseModel, Field
from typing import List, Optional
import re
from fastapi_backend.schema_models.model import ProteinName

def extract_protein_name(query: str, llm_svc: LLMService) -> Optional[str]:
    """
    Extract protein name from the query using both pattern matching and LLM.
    Returns the protein name if found, None otherwise.
    """
    # First try pattern matching for common proteins
    common_proteins = ['EGFR', 'p53', 'BRCA1', 'BRCA2', 'MYC', 'TP53', 'AKT1', 'PIK3CA', 'KRAS', 'APC']
    
    query_upper = query.upper()
    for protein in common_proteins:
        if protein.upper() in query_upper:
            return protein
    
    # If no common protein found, use LLM
    try:
        prompt = f"""Extract the protein or gene name from the following query: "{query}"

IMPORTANT: 
- Only return a single protein/gene name, no other text or explanation
- If no clear protein/gene is mentioned, return "UNKNOWN"
- Use standard gene symbols (e.g., EGFR, p53, BRCA1, BRCA2)
- Be confident in your extraction

Examples:
- Query: "EGFR in microgravity" → EGFR
- Query: "p53 in space" → p53  
- Query: "BRCA1 in microgravity" → BRCA1
- Query: "What happens to cells in space?" → UNKNOWN
- Query: "How does radiation affect DNA repair?" → UNKNOWN
"""
        
        formatter = llm_svc.llm_provider.with_structured_output(ProteinName)
        result = formatter.invoke(prompt)
        
        if result.protein_name and result.protein_name != "UNKNOWN":
            return result.protein_name
        else:
            return None
            
    except Exception as e:
        print(f"Error extracting protein name with LLM: {e}")
        return None

