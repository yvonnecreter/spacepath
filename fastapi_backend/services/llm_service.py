from fastapi_backend.interfaces.llm_interface import LLMProvider, EmbeddingProvider
from typing import Optional

class LLMService:
    def __init__(self, llm_provider: LLMProvider, embedding_provider: EmbeddingProvider):
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider
    
    @property
    def llm_model(self):
        """Get the underlying LLM model for compatibility with existing code"""
        return self.llm_provider.llm_model if hasattr(self.llm_provider, 'llm_model') else self.llm_provider
    
    @property
    def embeddings(self):
        """Get the embedding model"""
        return self.embedding_provider.get_embeddings()
    
    def invoke_structured_output(self, schema, messages):
        """Invoke LLM with structured output"""
        formatter = self.llm_provider.with_structured_output(schema)
        
        # Add tracing if available
        if self.tracing_service and self.tracing_service.is_enabled:
            callback_manager = self.tracing_service.get_callback_manager()
            if callback_manager:
                # Note: This is a simplified approach. In practice, you might need to 
                # modify the provider implementations to support callbacks
                pass
        
        return formatter.invoke(messages)
    
    def invoke(self, prompt, **kwargs):
        """Invoke LLM with prompt - compatibility method"""
        return self.llm_provider.invoke(prompt)
    
    def get_callback_manager(self):
        """Get callback manager for tracing"""
        if self.tracing_service:
            return self.tracing_service.get_callback_manager()
        return None
