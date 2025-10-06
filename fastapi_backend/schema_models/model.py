from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from pydantic import Field
from fastapi import UploadFile, File

class ProteinName(BaseModel):
    protein_name: str = Field(description="The name of the protein or gene")

class ProteinInfo(BaseModel):
    protein_name: str = Field(description="The name of the protein or gene")
    accession: str = Field(description="The UniProt accession of the protein or gene")
    alternate_names: List[str] = Field(description="Alternate names of the protein or gene")
    synonyms: List[str] = Field(description="Synonyms of the protein or gene")
    functions: List[str] = Field(description="Functions of the protein or gene")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ProteinInfo to dictionary for compatibility with existing code."""
        return {
            "protein_name": self.protein_name,
            "accession": self.accession,
            "alternate_names": self.alternate_names,
            "synonyms": self.synonyms,
            "functions": self.functions,
            "alt_names": self.alternate_names,  # Add alias for backward compatibility
        }


class ClinicalStudies(BaseModel):
    nct_id: str = Field(description="The NCT ID of the clinical study")
    title: str = Field(description="The title of the clinical study")
    brief_summary: str = Field(description="The brief summary of the clinical study")
    link: str = Field(description="The link to the clinical study")
    publication_year: Optional[str] = Field(description="The year the study was first posted", default=None)

class ClinicalStudiesResponse(BaseModel):
    clinical_studies: List[ClinicalStudies] = Field(description="The list of clinical studies")