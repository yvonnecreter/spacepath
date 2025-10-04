from abc import ABC, abstractmethod
from typing import Any, List, Dict

class LLMProvider(ABC):
    @abstractmethod
    def invoke(self, prompt) -> str:
        pass
    
    @abstractmethod
    def with_structured_output(self, schema):
        pass

class EmbeddingProvider(ABC):
    @abstractmethod
    def get_embeddings(self):
        pass