from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from fastapi_backend.interfaces.llm_interface import LLMProvider, EmbeddingProvider
import time
import random
from typing import List
import logging

logger = logging.getLogger(__name__)

class OpenAILLMProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str, temperature: float=0.0, verbose: bool=True):
        self.llm_model = ChatOpenAI(api_key=api_key, 
                                    model=model_name, 
                                    # temperature=temperature, 
                                    verbose=verbose)
    
    def invoke(self, prompt) -> str:
        return self.llm_model.invoke(prompt).content
    
    def with_structured_output(self, schema):
        return self.llm_model.with_structured_output(schema)

class RateLimitedOpenAIEmbeddings(OpenAIEmbeddings):
    """OpenAI Embeddings with rate limiting and retry logic"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set attributes after initialization to avoid Pydantic validation issues
        object.__setattr__(self, 'max_retries', 5)
        object.__setattr__(self, 'base_delay', 1.0)
        object.__setattr__(self, 'max_delay', 60.0)
        object.__setattr__(self, 'batch_size', 10)  # Process embeddings in smaller batches
        
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter"""
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        jitter = random.uniform(0.1, 0.3) * delay
        return delay + jitter
    
    def _embed_documents_with_retry(self, texts: List[str]) -> List[List[float]]:
        """Embed documents with rate limiting and retry logic"""
        all_embeddings = []
        
        # Process in batches to avoid rate limits
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            logger.info(f"Processing embedding batch {i//self.batch_size + 1}/{(len(texts) + self.batch_size - 1)//self.batch_size}")
            
            batch_embeddings = self._embed_batch_with_retry(batch)
            all_embeddings.extend(batch_embeddings)
            
            # Add delay between batches to respect rate limits
            if i + self.batch_size < len(texts):
                delay = 2.0  # 2 second delay between batches
                logger.info(f"Waiting {delay}s before next batch...")
                time.sleep(delay)
        
        return all_embeddings
    
    def _embed_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts with retry logic"""
        for attempt in range(self.max_retries):
            try:
                return super().embed_documents(texts)
            except Exception as e:
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    if attempt < self.max_retries - 1:
                        delay = self._calculate_delay(attempt)
                        logger.warning(f"Rate limit hit, retrying in {delay:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Max retries exceeded for embedding batch: {e}")
                        raise
                else:
                    # Non-rate-limit error, don't retry
                    raise
        
        return []  # Should never reach here
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Override to use rate-limited embedding"""
        if len(texts) <= self.batch_size:
            return self._embed_batch_with_retry(texts)
        else:
            return self._embed_documents_with_retry(texts)

class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model_name: str):
        self.embeddings = RateLimitedOpenAIEmbeddings(api_key=api_key, model=model_name)
    
    def get_embeddings(self):
        return self.embeddings