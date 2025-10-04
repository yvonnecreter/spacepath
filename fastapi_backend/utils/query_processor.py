from fastapi_backend.services.llm_service import LLMService
from pydantic import BaseModel, Field
from typing import List
import requests

class ProteinName(BaseModel):
    protein_name: str = Field(description="The name of the protein or gene")

# extract protein name from the query
def extract_protein_name(query: str, llm_svc: LLMService) -> str:
    """
    Extract protein name from the query.
    """
    if 'EGFR' in query:
        return "EGFR"
    elif 'p53' in query:
        return "p53"
    elif 'BRCA1' in query:
        return "BRCA1"
    elif 'BRCA2' in query:
        return "BRCA2"
    else:
        # call llm to extract protein name
        prompt = f"""Extract the protein name from the following query: {query}
        IMPORTANT: Only return the protein name, no other text or explanation.
        For example, 
        Example 1: Query = "EGFR in microgravity", Protein = "EGFR".
        Example 2: Query = "p53 in space", Protein = "p53".
        Example 3: Query = "BRCA1 in microgravity", Protein = "BRCA1".
        Example 4: Query = "BRCA2 in space", Protein = "BRCA2".
        """
        formatter = llm_svc.llm_provider.with_structured_output(ProteinName)
        protein_name = formatter.invoke(prompt)
        return protein_name

