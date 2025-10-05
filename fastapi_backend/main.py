from fastapi import FastAPI, HTTPException
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
from fastapi_backend.services.workflow_service import WorkflowService
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

    # Initialize vector stores with rate limiting
    logger.info("Initializing RAG pipeline...")
    try:
        rag_pipeline.initialize_vector_stores(force_rebuild=False)
        logger.info("RAG pipeline initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG pipeline: {e}")
        logger.info("Continuing with limited functionality...")

    # Initialize workflow service
    workflow_service = WorkflowService(llm_svc, rag_pipeline)

    # Request/Response models
    class QueryRequest(BaseModel):
        query: str

    class QueryResponse(BaseModel):
        query: str
        protein_name: Optional[str]
        protein_info: Optional[dict]
        clinical_studies: Optional[dict]
        rag_response: Optional[dict]
        error: Optional[str]

    class ProteinRequest(BaseModel):
        protein_name: str

    @app.post("/query", response_model=QueryResponse)
    async def process_query(request: QueryRequest):
        """
        Main endpoint: Process user query through complete workflow
        1. Extract protein name
        2. Get protein info and clinical studies
        3. Generate RAG response from research papers
        """
        try:
            result = await workflow_service.process_query(request.query)
            return QueryResponse(**result)
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

    @app.post("/get-protein-info")
    async def get_protein_info(request: ProteinRequest):
        """Get protein information and clinical studies for a specific protein"""
        try:
            protein_info, clinical_studies = workflow_service.get_protein_only_info(request.protein_name)
            if protein_info is None:
                raise HTTPException(status_code=404, detail=f"Protein information not found for {request.protein_name}")
            
            return {
                "protein_info": protein_info,
                "clinical_studies": clinical_studies
            }
        except Exception as e:
            logger.error(f"Error getting protein info: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting protein info: {str(e)}")

    @app.post("/get-research-summary")
    async def get_research_summary(request: QueryRequest):
        """Get RAG response from research papers only"""
        try:
            rag_response = workflow_service.get_rag_only_response(request.query)
            if rag_response is None:
                raise HTTPException(status_code=500, detail="Failed to generate research summary")
            
            return rag_response
        except Exception as e:
            logger.error(f"Error getting research summary: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting research summary: {str(e)}")

    @app.post("/get-pathways")
    async def get_pathways(request: ProteinRequest):
        """Get pathways for a specific protein"""
        try:
            pathways = workflow_service.get_pathways_for_protein(request.protein_name)
            return pathways
        except Exception as e:
            logger.error(f"Error getting pathways: {e}")
            raise HTTPException(status_code=500, detail=f"Error getting pathways: {str(e)}")

    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "message": "SPACEPATH Backend is running"}

    return app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)