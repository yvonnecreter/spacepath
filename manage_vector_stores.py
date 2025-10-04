#!/usr/bin/env python3
"""
Vector Store Management Script

This script helps manage vector stores and handle rate limiting issues.
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi_backend.config.config import settings
from fastapi_backend.interfaces.llm_providers.openai_provider import OpenAILLMProvider, OpenAIEmbeddingProvider
from fastapi_backend.services.llm_service import LLMService
from fastapi_backend.rag_module.vanilla_rag import VanillaRAGPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_vector_stores_status():
    """Check the status of existing vector stores"""
    logger.info("Checking vector store status...")
    
    chroma_dir = "tmp/embeddings/SB_publication_PMC"
    chroma_db_path = os.path.join(chroma_dir, "chroma.sqlite3")
    paper_collection_path = os.path.join(chroma_dir, "papers_chroma.sqlite3")
    
    print(f"Chroma DB directory: {chroma_dir}")
    print(f"Document store exists: {os.path.exists(chroma_db_path)}")
    print(f"Paper store exists: {os.path.exists(paper_collection_path)}")
    
    if os.path.exists(chroma_db_path):
        size = os.path.getsize(chroma_db_path)
        print(f"Document store size: {size / (1024*1024):.2f} MB")
    
    if os.path.exists(paper_collection_path):
        size = os.path.getsize(paper_collection_path)
        print(f"Paper store size: {size / (1024*1024):.2f} MB")

def initialize_vector_stores(force_rebuild=False):
    """Initialize vector stores with rate limiting"""
    logger.info("Initializing vector stores...")
    
    try:
        # Create providers
        llm_provider = OpenAILLMProvider(api_key=settings.OPENAI_API_KEY, model_name=settings.LLM_MODEL)
        embedding_provider = OpenAIEmbeddingProvider(api_key=settings.OPENAI_API_KEY, model_name=settings.EMBEDDING_MODEL)
        llm_svc = LLMService(llm_provider, embedding_provider)
        
        # Create RAG pipeline
        rag_pipeline = VanillaRAGPipeline(
            llm_svc=llm_svc,
            csv_path="SB_publication_PMC.csv",
            chroma_persist_dir="tmp/embeddings/SB_publication_PMC",
            top_k_docs=15
        )
        
        # Initialize with rate limiting
        status = rag_pipeline.initialize_vector_stores(force_rebuild=force_rebuild)
        logger.info(f"Vector stores status: {status}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize vector stores: {e}")
        return False

def clear_vector_stores():
    """Clear existing vector stores"""
    logger.info("Clearing vector stores...")
    
    chroma_dir = "tmp/embeddings/SB_publication_PMC"
    
    if os.path.exists(chroma_dir):
        import shutil
        shutil.rmtree(chroma_dir)
        logger.info(f"Cleared directory: {chroma_dir}")
    else:
        logger.info("No vector stores to clear")

def test_vector_stores():
    """Test the vector stores"""
    logger.info("Testing vector stores...")
    
    try:
        # Create providers
        llm_provider = OpenAILLMProvider(api_key=settings.OPENAI_API_KEY, model_name=settings.LLM_MODEL)
        embedding_provider = OpenAIEmbeddingProvider(api_key=settings.OPENAI_API_KEY, model_name=settings.EMBEDDING_MODEL)
        llm_svc = LLMService(llm_provider, embedding_provider)
        
        # Create RAG pipeline
        rag_pipeline = VanillaRAGPipeline(
            llm_svc=llm_svc,
            csv_path="SB_publication_PMC.csv",
            chroma_persist_dir="tmp/embeddings/SB_publication_PMC",
            top_k_docs=15
        )
        
        # Test document search
        logger.info("Testing document search...")
        docs, info = rag_pipeline.retrieve_documents("EGFR microgravity", top_k_docs=3)
        logger.info(f"Found {len(docs)} documents")
        
        # Test paper search
        logger.info("Testing paper search...")
        papers = rag_pipeline.search_papers("EGFR microgravity", top_k=3)
        logger.info(f"Found {len(papers)} papers")
        
        # Test QA chain
        logger.info("Testing QA chain...")
        qa_chain = rag_pipeline.setup_qa_chain()
        result = qa_chain.invoke({"query": "What is EGFR?"})
        logger.info(f"QA result: {result['result'][:200]}...")
        
        logger.info("Vector stores test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Vector stores test failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Manage SPACEPATH vector stores")
    parser.add_argument("action", choices=["status", "init", "rebuild", "clear", "test"], 
                       help="Action to perform")
    parser.add_argument("--force", action="store_true", help="Force rebuild even if stores exist")
    
    args = parser.parse_args()
    
    if args.action == "status":
        check_vector_stores_status()
    elif args.action == "init":
        success = initialize_vector_stores(force_rebuild=False)
        if success:
            print("✓ Vector stores initialized successfully")
        else:
            print("✗ Failed to initialize vector stores")
            sys.exit(1)
    elif args.action == "rebuild":
        success = initialize_vector_stores(force_rebuild=True)
        if success:
            print("✓ Vector stores rebuilt successfully")
        else:
            print("✗ Failed to rebuild vector stores")
            sys.exit(1)
    elif args.action == "clear":
        clear_vector_stores()
        print("✓ Vector stores cleared")
    elif args.action == "test":
        success = test_vector_stores()
        if success:
            print("✓ Vector stores test passed")
        else:
            print("✗ Vector stores test failed")
            sys.exit(1)

if __name__ == "__main__":
    main()
