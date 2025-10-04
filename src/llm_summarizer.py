"""
LLM Summarizer for Knowledge Graph Tooltips
Uses local LLM or API to generate contextual summaries
"""

from typing import List, Dict, Optional
import os

class LLMSummarizer:
    """
    Generate intelligent summaries for entity relationships using LLM.
    Supports multiple backends: OpenAI, Anthropic, or local models via Ollama.
    """
    
    def __init__(self, backend='ollama', model_name='granite3.3:2b'):
        """
        Initialize LLM summarizer.
        
        Args:
            backend: 'openai', 'anthropic', or 'ollama'
            model_name: Model to use (e.g., 'gpt-3.5-turbo', 'claude-3-haiku', 'granite3.3:2b')
        """
        self.backend = backend
        self.model_name = model_name
        self.client = None
        
        self._initialize_backend()
    
    def _initialize_backend(self):
        """Initialize the selected LLM backend."""
        if self.backend == 'openai':
            try:
                from openai import OpenAI
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    print("⚠ OPENAI_API_KEY not set. Set it with: export OPENAI_API_KEY=your-key")
                    self.backend = None
                    return
                self.client = OpenAI(api_key=api_key)
                print(f"✓ Initialized OpenAI with model: {self.model_name}")
            except ImportError:
                print("⚠ OpenAI not installed. Install with: pip install openai")
                self.backend = None
        
        elif self.backend == 'anthropic':
            try:
                from anthropic import Anthropic
                api_key = os.getenv('ANTHROPIC_API_KEY')
                if not api_key:
                    print("⚠ ANTHROPIC_API_KEY not set. Set it with: export ANTHROPIC_API_KEY=your-key")
                    self.backend = None
                    return
                self.client = Anthropic(api_key=api_key)
                print(f"✓ Initialized Anthropic with model: {self.model_name}")
            except ImportError:
                print("⚠ Anthropic not installed. Install with: pip install anthropic")
                self.backend = None
        
        elif self.backend == 'ollama':
            try:
                import requests
                # Test if Ollama is running
                response = requests.get('http://localhost:11434/api/tags', timeout=2)
                if response.status_code == 200:
                    print(f"✓ Initialized Ollama with model: {self.model_name}")
                else:
                    print("⚠ Ollama not responding. Start it with: ollama serve")
                    self.backend = None
            except:
                print("⚠ Ollama not available. Install from: https://ollama.ai")
                print("  After installing, run: ollama pull llama2")
                self.backend = None
        
        else:
            print(f"⚠ Unknown backend: {self.backend}")
            self.backend = None
    
    def _call_openai(self, prompt: str, max_tokens: int = 150) -> str:
        """Call OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes medical research relationships concisely."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI error: {e}")
            return None
    
    def _call_anthropic(self, prompt: str, max_tokens: int = 150) -> str:
        """Call Anthropic API."""
        try:
            response = self.client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text.strip()
        except Exception as e:
            print(f"Anthropic error: {e}")
            return None
    
    def _call_ollama(self, prompt: str, max_tokens: int = 150) -> str:
        """Call local Ollama API."""
        try:
            import requests
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': self.model_name,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'num_predict': max_tokens,
                        'temperature': 0.7
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()['response'].strip()
            else:
                print(f"Ollama error: {response.status_code}")
                return None
        except Exception as e:
            print(f"Ollama error: {e}")
            return None
    
    def generate_summary(self, prompt: str, max_tokens: int = 150) -> Optional[str]:
        """
        Generate summary using configured LLM backend.
        
        Args:
            prompt: The prompt to send to LLM
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated summary or None if error
        """
        if not self.backend:
            return None
        
        if self.backend == 'openai':
            return self._call_openai(prompt, max_tokens)
        elif self.backend == 'anthropic':
            return self._call_anthropic(prompt, max_tokens)
        elif self.backend == 'ollama':
            return self._call_ollama(prompt, max_tokens)
        
        return None
    
    def summarize_entity(self, entity_name: str, entity_info: Dict, papers: List[Dict]) -> str:
        """
        Generate a concise summary of an entity based on related papers.
        
        Args:
            entity_name: Name of the entity
            entity_info: Entity metadata (type, frequency, etc.)
            papers: List of related papers from RAG search
            
        Returns:
            Concise summary (2-3 sentences)
        """
        # Build context from papers
        context = f"Entity: {entity_name}\nType: {entity_info.get('type', 'Unknown')}\n\n"
        context += "Relevant Research:\n"
        
        for i, paper in enumerate(papers[:3], 1):
            context += f"{i}. {paper['title']}\n"
            context += f"   Abstract: {paper['abstract'][:200]}...\n\n"
        
        prompt = f"""{context}

Based on the above research papers, provide a concise 2-3 sentence summary explaining what "{entity_name}" is and its significance in medical research. Focus on key findings and relationships."""

        summary = self.generate_summary(prompt, max_tokens=150)
        
        if summary:
            return summary
        else:
            # Fallback
            return f"{entity_name} ({entity_info.get('type', 'Unknown')}) appears in {entity_info.get('frequency', 0)} contexts across {len(entity_info.get('papers', []))} papers."
    
    def summarize_relationship(self, source: str, relation: str, target: str, 
                              papers: List[Dict]) -> str:
        """
        Generate a summary explaining the relationship between two entities.
        
        Args:
            source: Source entity
            relation: Relationship type
            target: Target entity
            papers: Related papers from RAG
            
        Returns:
            Explanation of the relationship (2-3 sentences)
        """
        # Build context
        context = f"Relationship: {source} {relation} {target}\n\n"
        context += "Supporting Evidence:\n"
        
        for i, paper in enumerate(papers[:2], 1):
            context += f"{i}. {paper['title']}\n"
            if 'abstract' in paper:
                context += f"   Abstract: {paper['abstract'][:200]}...\n"
            if 'results' in paper and paper['results']:
                context += f"   Results: {paper['results'][:200]}...\n"
            context += "\n"
        
        prompt = f"""{context}

Based on the research above, explain in 2-3 sentences how "{source}" {relation.lower().replace('_', ' ')} "{target}". Focus on the mechanism or evidence supporting this relationship."""

        summary = self.generate_summary(prompt, max_tokens=150)
        
        if summary:
            return summary
        else:
            # Fallback
            return f"{source} {relation.lower().replace('_', ' ')} {target} based on research evidence."
    
    def summarize_multi_hop(self, path: List[str], papers: List[Dict]) -> str:
        """
        Summarize a multi-hop connection path between entities.
        
        Args:
            path: List of entities in the connection path
            papers: Supporting papers
            
        Returns:
            Summary of the connection
        """
        context = f"Connection Path: {' → '.join(path)}\n\n"
        context += "Supporting Research:\n"
        
        for i, paper in enumerate(papers[:3], 1):
            context += f"{i}. {paper['title']}\n"
            context += f"   {paper.get('abstract', '')[:150]}...\n\n"
        
        prompt = f"""{context}

Explain in 2-3 sentences how these entities are connected: {' → '.join(path)}. Describe the biological or medical significance of this connection."""

        summary = self.generate_summary(prompt, max_tokens=180)
        
        if summary:
            return summary
        else:
            return f"These entities are connected through {len(path)-1} intermediate relationships in the research literature."


# Example usage
if __name__ == "__main__":
    # Test with Ollama (local, free)
    summarizer = LLMSummarizer(backend='ollama', model_name='granite3.3:2b')
    
    # Test entity summary
    entity_info = {
        'type': 'PROTEIN',
        'frequency': 5,
        'papers': ['Paper 1', 'Paper 2']
    }
    
    papers = [
        {
            'title': 'NADPH oxidase in oxidative stress',
            'abstract': 'NADPH oxidase is a key enzyme that produces reactive oxygen species...'
        }
    ]
    
    summary = summarizer.summarize_entity('NADPH oxidase', entity_info, papers)
    print(f"Entity Summary:\n{summary}\n")
    
    # Test relationship summary
    rel_summary = summarizer.summarize_relationship(
        'NADPH oxidase', 
        'CAUSES', 
        'oxidative stress',
        papers
    )
    print(f"Relationship Summary:\n{rel_summary}")