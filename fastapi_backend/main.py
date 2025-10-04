from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import logging
GREEN = "\033[32m"
RESET = "\033[0m"
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=f'{GREEN}%(levelname)s{RESET}: %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
    ]
)

logger = logging.getLogger(__name__)

logger.info("Starting SPACEPATH Backend")

from fastapi_backend.config.config import settings
from fastapi_backend.interfaces.llm_providers.openai_provider import OpenAILLMProvider, OpenAIEmbeddingProvider
from fastapi_backend.services.llm_service import LLMService
from fastapi_backend.rag_module.vanilla_rag import VanillaRAGPipeline
from fastapi_backend.rag_module.structured_reader import BiologicalEffect
from pydantic import BaseModel
from typing import List, Optional
from fastapi_backend.utils.extract_protein_details import extract_protein_details
from fastapi_backend.utils.get_clinical_studies import get_protein_clinical_studies


def create_llm_provider():
    """Create LLM provider based on configuration"""
    if settings.LLM_BACKEND == "openai":
        return OpenAILLMProvider(
            api_key=settings.OPENAI_API_KEY,
            model_name=settings.LLM_MODEL
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {settings.LLM_BACKEND}")

def create_embedding_provider():
    """Create embedding provider based on configuration"""
    if settings.LLM_BACKEND == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.OPENAI_API_KEY,
            model_name=settings.EMBEDDING_MODEL
        )
    else:
        raise ValueError(f"Unsupported embedding provider: {settings.LLM_BACKEND}")


def create_app():
    app = FastAPI(title="SPACEPATH Backend", description="SPACEPATH Backend")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )    

    llm_provider = create_llm_provider()
    embedding_provider = create_embedding_provider()
    llm_svc = LLMService(llm_provider, embedding_provider)
    
    # Initialize RAG pipeline
    rag_pipeline = VanillaRAGPipeline(
        llm_svc=llm_svc,
        csv_path="SB_publication_PMC.csv",
        chroma_persist_dir="tmp/embeddings/SB_publication_PMC",
        top_k_docs=15
    )

    rag_qa = rag_pipeline.setup_qa_chain()


    @app.post("/get-protein-clinical-studies")
    async def get_protein_clinical_studies(protein_name: str):
        """Get clinical studies"""
        protein_info, clinical_studies = get_protein_clinical_studies(protein_name)
        return protein_info, clinical_studies


    @app.post("/get-summary")
    async def get_summary(query: str):
        """Process user query and return summary using LLM"""

        output = rag_qa.invoke({"query": query})
        summary = output['result']
        sources = output['source_documents']

        # find unique research papers from sources
        unique_papers = set()
        for source in sources:
            unique_papers.add(source.metadata['title'])

        # return summary and unique research papers
        return {"summary": summary, "relevant_papers": list(unique_papers)}


    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "message": "SPACEPATH Backend is running"}

    return app

