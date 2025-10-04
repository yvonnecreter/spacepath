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

