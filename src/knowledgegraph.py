import pandas as pd
import requests
from bs4 import BeautifulSoup
try:
    import spacy  # Optional; deactivated in this build
except Exception:
    spacy = None
import networkx as nx
import json
import re
from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict, Counter
import matplotlib.pyplot as plt
from tqdm import tqdm
import pickle
import time
import os
import warnings

# LLM utilities
try:
    from llm_summarizer import LLMSummarizer
except ImportError:
    LLMSummarizer = None
    warnings.warn("llm_summarizer not available. LLM features will be disabled.")

# Optional: try to read keywords from existing RAG collection metadata
try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    chromadb = None
    warnings.warn("chromadb not available. RAG integration will be disabled.")


class MedicalKnowledgeGraph:
    """
    Build a knowledge graph from medical paper abstracts and results sections.
    Extracts entities (diseases, proteins, chemicals, etc.) and their relationships.
    """
    
    def __init__(self, rag_dir: str = './medical_chroma_db', rag_collection: str = 'medical_papers'):
        """Initialize the knowledge graph builder."""
        self.graph = nx.MultiDiGraph()  # Directed graph with multiple edges
        self.entity_types = defaultdict(set)
        self.paper_entities = {}  # Maps paper titles to their entities
        self.relationship_counts = Counter()
        # Map paper title/reference -> metadata (link, domain)
        self.paper_metadata: Dict[str, Dict[str, str]] = {}
        
        # Deactivate spaCy: use only LLM-based extraction
        self.nlp = None
        
        # Relationship patterns for medical texts
        self.relationship_patterns = self._define_relationship_patterns()

        # Initialize LLM for relation extraction with proper error handling
        self.llm = self._initialize_llm()

        # Optional: connect to existing RAG to reuse extracted keywords
        self.rag_collection = self._initialize_rag(rag_dir, rag_collection)
    
    def _load_spacy_model(self):
        """SpaCy is deactivated; return None."""
        print("ℹ spaCy disabled: using only LLM-based extraction")
        return None
    
    def _initialize_llm(self):
        """Initialize LLM with proper error handling."""
        if LLMSummarizer is None:
            print("⚠ LLM summarizer not available. Relation extraction will use pattern matching only.")
            return None
        
        backend = os.getenv('LLM_BACKEND', 'ollama')
        model = os.getenv('LLM_MODEL', 'granite3.3:2b')
        
        try:
            llm = LLMSummarizer(backend=backend, model_name=model)
            print(f"✓ Initialized LLM: {backend}/{model}")
            return llm
        except Exception as e:
            print(f"⚠ Could not initialize LLM ({e}). Falling back to pattern matching.")
            return None
    
    def _initialize_rag(self, rag_dir: str, rag_collection: str):
        """Initialize RAG collection connection."""
        if chromadb is None:
            return None
        
        if not os.path.exists(rag_dir):
            return None
        
        try:
            client = chromadb.PersistentClient(
                path=rag_dir, 
                settings=Settings(anonymized_telemetry=False)
            )
            collection = client.get_collection(rag_collection)
            print(f"✓ Connected to RAG collection: {rag_collection}")
            return collection
        except Exception as e:
            print(f"⚠ Could not connect to RAG collection: {e}")
            return None
        
    def _define_relationship_patterns(self) -> List[Dict]:
        """
        Define patterns to extract relationships between entities.
        Uses dependency parsing and verb patterns.
        """
        patterns = [
            # Causal relationships
            {'verbs': ['cause', 'causes', 'caused', 'causing', 'induce', 'induces', 'induced'],
             'relation': 'CAUSES'},
            {'verbs': ['trigger', 'triggers', 'triggered', 'initiate', 'initiates'],
             'relation': 'TRIGGERS'},
            {'verbs': ['lead', 'leads', 'leading', 'result', 'results', 'resulting'],
             'relation': 'LEADS_TO'},
            
            # Inhibition/Regulation
            {'verbs': ['inhibit', 'inhibits', 'inhibited', 'suppress', 'suppresses', 'block', 'blocks'],
             'relation': 'INHIBITS'},
            {'verbs': ['activate', 'activates', 'activated', 'stimulate', 'stimulates', 'enhance', 'enhances'],
             'relation': 'ACTIVATES'},
            {'verbs': ['regulate', 'regulates', 'regulated', 'modulate', 'modulates', 'control', 'controls'],
             'relation': 'REGULATES'},
            
            # Association
            {'verbs': ['associate', 'associated', 'correlate', 'correlated', 'link', 'linked'],
             'relation': 'ASSOCIATED_WITH'},
            {'verbs': ['interact', 'interacts', 'interacted', 'bind', 'binds'],
             'relation': 'INTERACTS_WITH'},
            
            # Expression/Production
            {'verbs': ['express', 'expresses', 'expressed', 'produce', 'produces', 'produced'],
             'relation': 'EXPRESSES'},
            {'verbs': ['increase', 'increases', 'increased', 'elevate', 'elevates', 'upregulate'],
             'relation': 'INCREASES'},
            {'verbs': ['decrease', 'decreases', 'decreased', 'reduce', 'reduces', 'downregulate'],
             'relation': 'DECREASES'},
            
            # Treatment
            {'verbs': ['treat', 'treats', 'treated', 'therapy', 'therapeutic'],
             'relation': 'TREATS'},
            {'verbs': ['prevent', 'prevents', 'prevented', 'protection', 'protective'],
             'relation': 'PREVENTS'},
            
            # Involvement
            {'verbs': ['involve', 'involves', 'involved', 'participate', 'participates'],
             'relation': 'INVOLVED_IN'},
            {'verbs': ['require', 'requires', 'required', 'depend', 'depends', 'dependent'],
             'relation': 'REQUIRES'},
        ]
        return patterns

    def set_relationship_patterns(self, patterns: List[Dict]):
        """Override relationship patterns (e.g., to sync with RAG)."""
        if not isinstance(patterns, list):
            raise ValueError("Patterns must be a list")
        if not all(isinstance(p, dict) and 'verbs' in p and 'relation' in p for p in patterns):
            raise ValueError("Each pattern must be a dict with 'verbs' and 'relation' keys")
        self.relationship_patterns = patterns

    def add_terms_from_rag_keywords(self, paper_title: str, keywords: Dict[str, List[str]]) -> int:
        """
        Add entities using RAG-extracted keywords, marking source as 'rag'.
        
        Args:
            paper_title: Title of the paper
            keywords: Dict with keys like 'llm_proteins' and 'llm_pathways'
            
        Returns:
            Number of entities added
        """
        if not isinstance(keywords, dict):
            return 0
        
        proteins = keywords.get('llm_proteins', []) or []
        pathways = keywords.get('llm_pathways', []) or []
        count = 0
        
        for p in proteins:
            if p and isinstance(p, str):
                self.add_entity_to_graph(p, 'PROTEIN', paper_title, section='rag', source='rag')
                count += 1
        
        for pw in pathways:
            if pw and isinstance(pw, str):
                self.add_entity_to_graph(pw, 'PATHWAY', paper_title, section='rag', source='rag')
                count += 1
        
        return count
    
    def load_csv(self, csv_path: str) -> pd.DataFrame:
        """Load CSV with paper titles and links."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            raise ValueError(f"Error reading CSV file: {e}")
        
        # Normalize column names
        if 'title' not in df.columns and len(df.columns) >= 1:
            df.columns = ['title'] + list(df.columns[1:])
        
        if 'link' not in df.columns:
            if 'url' in df.columns:
                df = df.rename(columns={'url': 'link'})
            elif len(df.columns) >= 2:
                df = df.rename(columns={df.columns[1]: 'link'})
            else:
                raise ValueError("CSV must have at least 2 columns: title and link/url")
        
        # Validate required columns
        if 'title' not in df.columns or 'link' not in df.columns:
            raise ValueError("CSV must contain 'title' and 'link' columns")
        
        # Remove rows with missing values
        df = df.dropna(subset=['title', 'link'])
        
        print(f"✓ Loaded {len(df)} papers from CSV")
        return df
    
    def fetch_paper_content(self, url: str) -> Dict[str, str]:
        """
        Fetch and extract abstract and results sections.
        
        Args:
            url: Paper URL
            
        Returns:
            Dict with keys: abstract, results, methods, discussion
        """
        content = {
            'abstract': '',
            'results': '',
            'methods': '',
            'discussion': ''
        }
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract abstract
            abstract_patterns = [
                lambda s: s.find(['div', 'section', 'p'], class_=re.compile(r'abstract', re.I)),
                lambda s: s.find(['div', 'section'], id=re.compile(r'abstract', re.I)),
                lambda s: s.find('abstract')
            ]
            
            for pattern in abstract_patterns:
                try:
                    abstract_section = pattern(soup)
                    if abstract_section:
                        content['abstract'] = abstract_section.get_text(strip=True, separator=' ')
                        break
                except:
                    continue
            
            # Extract results
            results_patterns = [
                lambda s: s.find(['div', 'section'], class_=re.compile(r'results?', re.I)),
                lambda s: s.find(['div', 'section'], id=re.compile(r'results?', re.I))
            ]
            
            for pattern in results_patterns:
                try:
                    results_section = pattern(soup)
                    if results_section:
                        content['results'] = results_section.get_text(strip=True, separator=' ')
                        break
                except:
                    continue
            
            # Extract methods (optional)
            try:
                methods_section = soup.find(['div', 'section'], class_=re.compile(r'method', re.I))
                if methods_section:
                    content['methods'] = methods_section.get_text(strip=True, separator=' ')
            except:
                pass
            
            # Extract discussion (optional)
            try:
                discussion_section = soup.find(['div', 'section'], class_=re.compile(r'discussion', re.I))
                if discussion_section:
                    content['discussion'] = discussion_section.get_text(strip=True, separator=' ')
            except:
                pass
            
            # Clean up text
            for key in content:
                if content[key]:
                    content[key] = re.sub(r'\s+', ' ', content[key]).strip()
            
        except requests.exceptions.Timeout:
            print(f"  ⚠ Timeout fetching {url}")
        except requests.exceptions.RequestException as e:
            print(f"  ⚠ Request error for {url}: {str(e)}")
        except Exception as e:
            print(f"  ⚠ Error parsing {url}: {str(e)}")
        
        return content

    def _infer_domain_from_ref(self, ref: Optional[str], link: Optional[str]) -> str:
        """Infer data domain for a paper reference or link.

        Priority: explicit ref prefixes, then link hostname classification.
        """
        try:
            if ref and isinstance(ref, str):
                if ref.startswith('UniProt:'):
                    return 'uniprot'
                if ref.startswith('PMID:'):
                    return 'pubmed'
            if link and isinstance(link, str):
                from urllib.parse import urlparse
                host = urlparse(link).hostname or ''
                host = host.lower()
                if 'clinicaltrials.gov' in host:
                    return 'clinicaltrials.gov'
                if 'pubmed' in host or 'ncbi.nlm.nih.gov' in host:
                    return 'pubmed'
                if 'uniprot' in host:
                    return 'uniprot'
            return 'other'
        except Exception:
            return 'other'
    
    def extract_entities(self, text: str, section_type: str = 'abstract') -> List[Dict]:
        """
        Deactivated: spaCy entity extraction disabled; return empty.
        
        Args:
            text: Text to extract entities from
            section_type: Section identifier (abstract, results, etc.)
            
        Returns:
            List of entity dictionaries with text, label, and context
        """
        return []

    def _fetch_keywords_from_rag(self, link: Optional[str], title: Optional[str]) -> Dict[str, List[str]]:
        """
        Try to fetch precomputed keywords from RAG collection metadata by link.
        
        Args:
            link: Paper URL
            title: Paper title
            
        Returns:
            Dict with keys: llm_keywords, llm_proteins, llm_pathways
        """
        result = {
            'llm_keywords': [],
            'llm_proteins': [],
            'llm_pathways': []
        }
        
        if not self.rag_collection or not link:
            return result
        
        try:
            # Fetch from ChromaDB by link metadata
            data = self.rag_collection.get(where={'link': link}, include=['metadatas'])
            
            if data and data.get('metadatas') and len(data['metadatas']) > 0:
                md = data['metadatas'][0]
                
                # Extract keywords
                try:
                    kws = json.loads(md.get('yake_keywords', '[]'))
                    if not isinstance(kws, list):
                        kws = []
                except:
                    kws = []
                
                try:
                    combined = json.loads(md.get('combined_keywords', '[]'))
                    if not isinstance(combined, list):
                        combined = []
                except:
                    combined = []
                
                result['llm_keywords'] = kws or combined
                
                # Extract proteins and pathways if available
                try:
                    proteins = json.loads(md.get('llm_proteins', '[]'))
                    if isinstance(proteins, list):
                        result['llm_proteins'] = proteins
                except:
                    pass
                
                try:
                    pathways = json.loads(md.get('llm_pathways', '[]'))
                    if isinstance(pathways, list):
                        result['llm_pathways'] = pathways
                except:
                    pass
                
        except Exception as e:
            print(f"  ⚠ Error fetching RAG keywords: {e}")
        
        return result

    def _extract_keywords_llm(self, text: str, max_items: int = 25) -> Dict[str, List[str]]:
        """
        LLM keyword extractor for proteins and pathways.
        
        Args:
            text: Text to extract keywords from
            max_items: Maximum items per category
            
        Returns:
            Dict with keys: llm_keywords, llm_proteins, llm_pathways
        """
        if not text or not self.llm:
            return {'llm_keywords': [], 'llm_proteins': [], 'llm_pathways': []}
        
        # Sample text to fit context window
        sample = text[:6000]
        
        prompt = (
            "You are an expert biomedical text-mining assistant.\n"
            "From the text, extract two lists strictly in JSON: 'proteins' and 'pathways'.\n"
            "- Only include names present in the text.\n"
            "- Use concise canonical forms.\n"
            f"- Limit to top {max_items} unique items per list.\n\n"
            f"Text:\n{sample}\n\n"
            "Return JSON with keys 'proteins' and 'pathways' only."
        )
        
        try:
            resp = self.llm.generate_summary(prompt, max_tokens=400)
            if not resp:
                return {'llm_keywords': [], 'llm_proteins': [], 'llm_pathways': []}
            
            # Parse JSON response
            try:
                parsed = json.loads(resp)
            except:
                # Try to extract JSON from response
                match = re.search(r"\{[\s\S]*\}", resp)
                if match:
                    parsed = json.loads(match.group(0))
                else:
                    return {'llm_keywords': [], 'llm_proteins': [], 'llm_pathways': []}
            
            # Extract and validate proteins
            proteins = parsed.get('proteins', [])
            if not isinstance(proteins, list):
                proteins = []
            proteins = [p.strip() for p in proteins if isinstance(p, str) and p.strip()]
            
            # Extract and validate pathways
            pathways = parsed.get('pathways', [])
            if not isinstance(pathways, list):
                pathways = []
            pathways = [p.strip() for p in pathways if isinstance(p, str) and p.strip()]
            
            # Deduplicate
            def deduplicate(seq):
                seen = set()
                result = []
                for item in seq:
                    key = item.lower()
                    if key not in seen and item:
                        seen.add(key)
                        result.append(item)
                return result
            
            proteins = deduplicate(proteins)[:max_items]
            pathways = deduplicate(pathways)[:max_items]
            
            return {
                'llm_keywords': deduplicate(proteins + pathways),
                'llm_proteins': proteins,
                'llm_pathways': pathways
            }
            
        except Exception as e:
            print(f"  ⚠ Error in LLM keyword extraction: {e}")
            return {'llm_keywords': [], 'llm_proteins': [], 'llm_pathways': []}

    def _llm_extract_relations(self, text: str, section: str, keywords: List[str]) -> List[Dict]:
        """
        Use LLM to extract causal and relational connections as JSON.
        
        Args:
            text: Text to extract relations from
            section: Section identifier
            keywords: Candidate keywords to use
            
        Returns:
            List of relation dicts with keys: source, relation, target, evidence, section, confidence
        """
        if not text or not self.llm:
            return []
        
        # Limit context
        context = text[:6000]
        kw_blob = ", ".join(keywords[:30]) if keywords else "various proteins and pathways"
        
        allowed = [
            'CAUSES', 'INHIBITS', 'ACTIVATES', 'REGULATES', 'ASSOCIATED_WITH', 'INTERACTS_WITH',
            'INCREASES', 'DECREASES', 'TREATS', 'PREVENTS', 'INVOLVED_IN', 'REQUIRES', 'BINDS'
        ]
        
        prompt = (
            "You are extracting biomedical relationships from a research paper section.\n"
            "Return STRICT JSON ONLY (no prose) with a 'relations' array. Each item must have:\n"
            "- source: entity text as appears in text\n"
            "- relation: one of " + ", ".join(allowed) + "\n"
            "- target: entity text\n"
            "- evidence: short quote/sentence supporting the relation\n"
            "- section: '" + section + "'\n"
            "- confidence: High/Medium/Low\n\n"
            "Use the following candidate terms when deciding entities: " + kw_blob + "\n\n"
            "Text:\n" + context + "\n\n"
            "Output JSON example: {\"relations\":[{\"source\":\"EGFR\",\"relation\":\"ACTIVATES\",\"target\":\"MAPK pathway\",\"evidence\":\"...\",\"section\":\"abstract\",\"confidence\":\"High\"}]}"
        )
        
        try:
            resp = self.llm.generate_summary(prompt, max_tokens=600)
            if not resp:
                return []

            def _strip_code_fences(s: str) -> str:
                # Extract content inside ```json ... ``` if present
                m = re.search(r"```\s*json\s*([\s\S]*?)```", s, re.IGNORECASE)
                if m:
                    return m.group(1)
                # Remove any code fences generically
                return re.sub(r"```[\s\S]*?```", "", s)

            def _balanced_json_slice(s: str) -> str:
                # Try to slice from first '{' that precedes 'relations'
                idx = s.find('{')
                best = None
                while idx != -1:
                    if 'relations' in s[idx:idx+500]:
                        # Walk to find balanced closing brace
                        depth = 0
                        in_str = False
                        esc = False
                        for j, ch in enumerate(s[idx:], start=idx):
                            if in_str:
                                if esc:
                                    esc = False
                                elif ch == '\\':
                                    esc = True
                                elif ch == '"':
                                    in_str = False
                            else:
                                if ch == '"':
                                    in_str = True
                                elif ch == '{':
                                    depth += 1
                                elif ch == '}':
                                    depth -= 1
                                    if depth == 0:
                                        best = s[idx:j+1]
                                        return best
                    idx = s.find('{', idx+1)
                return best

            def _remove_trailing_commas(s: str) -> str:
                # Remove trailing commas before closing braces/brackets
                prev = None
                cur = s
                while prev != cur:
                    prev = cur
                    cur = re.sub(r",\s*([}\]])", r"\1", cur)
                return cur

            raw = _strip_code_fences(resp)
            candidate = _balanced_json_slice(raw) or raw
            candidate = _remove_trailing_commas(candidate)

            # Parse JSON with robust fallbacks
            data = None
            try:
                data = json.loads(candidate)
            except Exception as e:
                # Fallback: extract just the relations array and parse objects one by one
                # Find relations array bounds
                rels = []
                try:
                    key_idx = candidate.lower().find('"relations"')
                    # If there is no explicit key, try the first array in the payload
                    if key_idx == -1:
                        brack_start = candidate.find('[')
                        if brack_start == -1:
                            raise ValueError('no relations key')
                    else:
                        brack_start = candidate.find('[', key_idx)
                        if brack_start == -1:
                            raise ValueError('no relations array start')
                    # Balanced bracket scan for end
                    depth = 0
                    in_str = False
                    esc = False
                    end_idx = -1
                    for j in range(brack_start, len(candidate)):
                        ch = candidate[j]
                        if in_str:
                            if esc:
                                esc = False
                            elif ch == '\\':
                                esc = True
                            elif ch == '"':
                                in_str = False
                        else:
                            if ch == '"':
                                in_str = True
                            elif ch == '[':
                                depth += 1
                            elif ch == ']':
                                depth -= 1
                                if depth == 0:
                                    end_idx = j
                                    break
                    if end_idx == -1:
                        raise ValueError('no relations array end')
                    rels_payload = candidate[brack_start+1:end_idx]

                    # Iterate object by object (balanced braces)
                    i = 0
                    while i < len(rels_payload):
                        # Find next '{'
                        lb = rels_payload.find('{', i)
                        if lb == -1:
                            break
                        # Scan to matching '}'
                        depth = 0
                        in_str = False
                        esc = False
                        rb = -1
                        for k in range(lb, len(rels_payload)):
                            ch = rels_payload[k]
                            if in_str:
                                if esc:
                                    esc = False
                                elif ch == '\\':
                                    esc = True
                                elif ch == '"':
                                    in_str = False
                            else:
                                if ch == '"':
                                    in_str = True
                                elif ch == '{':
                                    depth += 1
                                elif ch == '}':
                                    depth -= 1
                                    if depth == 0:
                                        rb = k
                                        break
                        if rb == -1:
                            break
                        obj_txt = rels_payload[lb:rb+1]

                        def sanitize_obj(txt: str) -> str:
                            # Remove trailing commas, normalize smart quotes, attempt to convert single quotes to double quotes safely
                            txt = txt.replace('\u201c', '"').replace('\u201d', '"').replace('“', '"').replace('”', '"').replace('’', "'")
                            txt = re.sub(r",\s*([}\]])", r"\1", txt)
                            # Quote keys with single quotes -> double quotes
                            txt = re.sub(r"(\{|,)\s*'([^']+)'\s*:\s*", r'\1"\2": ', txt)
                            # Single-quoted string values -> double quotes
                            txt = re.sub(r":\s*'([^']*)'\s*(,|})", lambda m: ': "' + m.group(1).replace('"', '\\"') + '"' + m.group(2), txt)
                            return txt

                        try:
                            rel_obj = json.loads(obj_txt)
                        except Exception:
                            try:
                                rel_obj = json.loads(sanitize_obj(obj_txt))
                            except Exception:
                                rel_obj = None
                        if isinstance(rel_obj, dict):
                            rels.append(rel_obj)
                        i = rb + 1

                    data = {'relations': rels}
                except Exception as e2:
                    print(f"  ⚠ JSON parse failed, skipping relations: {e2}")
                    return []
            
            # Normalize to relations list (LLM may return an array directly)
            if isinstance(data, list):
                rels = data
            elif isinstance(data, dict):
                rels = data.get('relations') or data.get('Relations') or data.get('RELATIONS') or []
            else:
                rels = []
            if not isinstance(rels, list):
                return []
            
            # Clean and validate relations
            clean = []
            for r in rels:
                if not isinstance(r, dict):
                    continue
                
                src = (r.get('source') or '').strip()
                rel = (r.get('relation') or '').strip().upper().replace(' ', '_')
                tgt = (r.get('target') or '').strip()
                evid = (r.get('evidence') or '')[:300]
                conf = (r.get('confidence') or 'Medium')
                
                if not (src and tgt and rel):
                    continue
                
                # Map common variants
                relation_map = {
                    'UPREGULATES': 'INCREASES',
                    'DOWNREGULATES': 'DECREASES',
                    'BINDS_TO': 'BINDS',
                    'ASSOCIATES_WITH': 'ASSOCIATED_WITH'
                }
                rel = relation_map.get(rel, rel)
                
                if rel in allowed:
                    clean.append({
                        'source': src,
                        'relation': rel,
                        'target': tgt,
                        'evidence': evid,
                        'section': section,
                        'confidence': conf
                    })
            
            return clean
            
        except Exception as e:
            print(f"  ⚠ Error in LLM relation extraction: {e}")
            return []
    
    def extract_relationships(self, text: str, entities: List[Dict]) -> List[Dict]:
        """
        Deactivated: spaCy/pattern-based relationship extraction disabled.
        
        Args:
            text: Text to extract relationships from
            entities: List of entity dicts
            
        Returns:
            List of relationship dictionaries
        """
        return []
    
    def add_entity_to_graph(self, entity: str, entity_type: str, 
                           paper_title: str, section: str,
                           source: str = 'paper'):
        """
        Add an entity node to the graph.

        Args:
            entity: Canonical entity text
            entity_type: NER label or semantic type
            paper_title: Provenance (may be PMID/UniProt id for non-paper)
            section: abstract/results or custom
            source: One of {'paper','uniprot','rag','other'} used for styling
        """
        if not entity or not isinstance(entity, str):
            return
        
        # Normalize entity name
        entity = entity.strip().lower()
        if not entity:
            return
        
        # Add or update node
        if entity not in self.graph:
            self.graph.add_node(
                entity, 
                entity_type=entity_type,
                papers=set(),
                sections=defaultdict(int),
                frequency=0,
                sources=set(),
                domains=set()
            )
        
        # Update node attributes
        try:
            self.graph.nodes[entity]['papers'].add(paper_title)
            self.graph.nodes[entity]['sections'][section] += 1
            self.graph.nodes[entity]['frequency'] += 1
            self.graph.nodes[entity]['sources'].add(source)
            # Update domain from paper metadata
            try:
                meta = self.paper_metadata.get(paper_title, {})
                dom = meta.get('domain') or self._infer_domain_from_ref(paper_title, meta.get('link'))
                if dom:
                    self.graph.nodes[entity]['domains'].add(dom)
            except Exception:
                pass
            self.entity_types[entity_type].add(entity)
        except Exception as e:
            print(f"  ⚠ Error adding entity {entity}: {e}")
    
    def add_relationship_to_graph(self, source: str, target: str, 
                                 relation: str, paper_title: str,
                                 context: str = '', verb: str = '', 
                                 edge_source: str = 'paper'):
        """
        Add a relationship edge to the graph.
        
        Args:
            source: Source entity
            target: Target entity
            relation: Relationship type
            paper_title: Paper reference
            context: Supporting context
            verb: Verb used in relation
            edge_source: Source of edge (paper/uniprot/rag/other)
        """
        if not source or not target or not isinstance(source, str) or not isinstance(target, str):
            return
        
        source = source.strip().lower()
        target = target.strip().lower()
        
        if not source or not target or source == target:
            return
        
        try:
            # Add edge
            # Determine domain for edge based on paper reference
            try:
                meta = self.paper_metadata.get(paper_title, {})
                edge_domain = meta.get('domain') or self._infer_domain_from_ref(paper_title, meta.get('link'))
            except Exception:
                edge_domain = ''

            self.graph.add_edge(
                source, target,
                relation=relation,
                paper=paper_title,
                context=context[:200],
                verb=verb,
                source=edge_source,
                domain=edge_domain
            )
            
            # Count relationship
            self.relationship_counts[(source, relation, target)] += 1
        except Exception as e:
            print(f"  ⚠ Error adding relationship {source}->{target}: {e}")

    def add_uniprot_interactions(self, uniprot_info: Dict) -> int:
        """
        Add UniProt interactions to the graph.
        
        Args:
            uniprot_info: Dict with UniProt data (from UniProtHarvester)
            
        Returns:
            Number of interactions added
        """
        if not isinstance(uniprot_info, dict):
            return 0
        
        accession = uniprot_info.get('accession', '')
        gene = uniprot_info.get('gene_name', '')
        protein = uniprot_info.get('protein_name', '')
        seed_name = gene or protein or accession
        
        if not seed_name:
            return 0

        # Add the seed protein node
        self.add_entity_to_graph(
            seed_name, 'PROTEIN', 
            f"UniProt:{accession}", 
            section='uniprot', 
            source='uniprot'
        )

        count = 0
        interactions = uniprot_info.get('interactions', []) or []
        
        for ix in interactions:
            if not isinstance(ix, dict):
                continue
            
            partner = ix.get('with') or ix.get('gene') or ix.get('accession')
            if not partner:
                continue
            
            self.add_entity_to_graph(
                partner, 'PROTEIN', 
                f"UniProt:{accession}", 
                section='uniprot', 
                source='uniprot'
            )
            
            # Use PMID as paper provenance if available
            pmids = ix.get('pmids', []) or []
            paper_field = f"PMID:{pmids[0]}" if pmids else f"UniProt:{accession}"
            # Record metadata for this reference
            try:
                if paper_field.startswith('PMID:'):
                    pmid = paper_field.split(':', 1)[1]
                    link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    domain = 'pubmed'
                else:
                    link = f"https://www.uniprot.org/uniprotkb/{accession}"
                    domain = 'uniprot'
                self.paper_metadata[paper_field] = {'link': link, 'domain': domain}
            except Exception:
                pass
            
            self.add_relationship_to_graph(
                seed_name, partner, 'INTERACTS_WITH', 
                paper_field, 
                edge_source='uniprot'
            )
            count += 1
        
        return count
    
    def process_paper(self, title: str, content: Dict[str, str], link: Optional[str] = None) -> int:
        """
        Process a single paper and extract entities and relationships.
        
        Args:
            title: Paper title
            content: Dict with abstract, results, etc.
            link: Paper URL (for RAG integration)
            
        Returns:
            Number of entities added
        """
        print(f"\nProcessing: {title[:70]}...")

        # Record paper metadata
        try:
            domain = self._infer_domain_from_ref(title, link)
            self.paper_metadata[title] = {
                'link': link or '',
                'domain': domain
            }
        except Exception:
            pass

        # Try to reuse RAG keywords by link
        rag_kws = self._fetch_keywords_from_rag(link, title)
        all_added_entities = []

        # Process abstract and results
        for section_name in ['abstract', 'results']:
            section_text = content.get(section_name, '')
            if not section_text:
                continue

            print(f"  Processing {section_name}...")

            # Get keywords (prefer RAG; fallback to local LLM)
            if rag_kws.get('llm_keywords'):
                keywords = rag_kws.get('llm_keywords', [])
                proteins = rag_kws.get('llm_proteins', [])
                pathways = rag_kws.get('llm_pathways', [])
                print(f"    Using RAG keywords: {len(keywords)} items")
            else:
                local_kws = self._extract_keywords_llm(section_text)
                keywords = local_kws.get('llm_keywords', [])
                proteins = local_kws.get('llm_proteins', [])
                pathways = local_kws.get('llm_pathways', [])
                if keywords:
                    print(f"    Extracted keywords via LLM: {len(keywords)} items")
                    print(keywords)

            # Add keyword-derived entities
            for p in proteins:
                if p:
                    self.add_entity_to_graph(p, 'PROTEIN', title, section=section_name, source='rag')
                    all_added_entities.append({'text': p, 'label': 'PROTEIN'})
            
            for pw in pathways:
                if pw:
                    self.add_entity_to_graph(pw, 'PATHWAY', title, section=section_name, source='rag')
                    all_added_entities.append({'text': pw, 'label': 'PATHWAY'})

            # Extract relations using LLM only
            if self.llm:
                # LLM-based relation extraction
                relations = self._llm_extract_relations(section_text, section_name, keywords)
                print(f"    LLM relations: {len(relations)}")
                
                for r in relations:
                    self.add_relationship_to_graph(
                        r['source'], r['target'], r['relation'], title,
                        context=r.get('evidence', ''), verb='', edge_source='rag'
                    )
            else:
                print("    ⚠ LLM not available; skipping relation extraction (spaCy disabled)")

        # Store paper entities
        self.paper_entities[title] = all_added_entities
        print(f"  Total entities: {len(all_added_entities)}")
        return len(all_added_entities)
    
    def build_from_csv(self, csv_path: str, max_papers: Optional[int] = None):
        """
        Build knowledge graph from CSV of papers.
        
        Args:
            csv_path: Path to CSV file
            max_papers: Optional limit on number of papers to process
        """
        df = self.load_csv(csv_path)
        
        if max_papers:
            df = df.head(max_papers)
        
        print(f"\n{'='*70}")
        print(f"Building Knowledge Graph from {len(df)} papers")
        print(f"{'='*70}")
        
        successful = 0
        failed = 0
        
        for idx, row in df.iterrows():
            title = row['title']
            link = row['link']
            
            print(f"\n[{idx+1}/{len(df)}]", end=' ')
            
            try:
                # Fetch content
                content = self.fetch_paper_content(link)
                
                if not content['abstract'] and not content['results']:
                    print(f"  ⚠ No abstract or results found, skipping")
                    failed += 1
                    continue
                
                # Process paper
                self.process_paper(title, content, link=link)
                successful += 1
                
            except Exception as e:
                print(f"  ✗ Error processing paper: {e}")
                failed += 1
                continue
            
            # Be respectful with requests
            time.sleep(1)
        
        print(f"\n{'='*70}")
        print("Knowledge Graph Construction Complete!")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"{'='*70}")
        self.print_statistics()
    
    def print_statistics(self):
        """Print statistics about the knowledge graph."""
        print(f"\n📊 Knowledge Graph Statistics:")
        print(f"  Total Entities: {self.graph.number_of_nodes()}")
        print(f"  Total Relationships: {self.graph.number_of_edges()}")
        print(f"  Papers Processed: {len(self.paper_entities)}")
        
        print(f"\n  Entity Types:")
        for etype, entities in sorted(self.entity_types.items(), 
                                     key=lambda x: len(x[1]), 
                                     reverse=True)[:15]:
            print(f"    {etype}: {len(entities)}")
        
        print(f"\n  Top 10 Relationship Types:")
        relation_counts = Counter()
        for _, _, data in self.graph.edges(data=True):
            relation_counts[data.get('relation', 'UNKNOWN')] += 1
        
        for rel, count in relation_counts.most_common(10):
            print(f"    {rel}: {count}")
        
        print(f"\n  Top 10 Most Frequent Entities:")
        entity_freqs = [(node, data['frequency']) 
                       for node, data in self.graph.nodes(data=True)]
        entity_freqs.sort(key=lambda x: x[1], reverse=True)
        
        for entity, freq in entity_freqs[:10]:
            print(f"    {entity}: {freq}")
    
    def query_entity(self, entity_name: str) -> Dict:
        """
        Query information about a specific entity.
        
        Args:
            entity_name: Entity to query
            
        Returns:
            Dict with entity information
        """
        entity_name = entity_name.strip().lower()
        
        if entity_name not in self.graph:
            return {'error': f"Entity '{entity_name}' not found in graph"}
        
        node_data = self.graph.nodes[entity_name]
        
        # Get relationships
        outgoing = []
        for _, target, data in self.graph.out_edges(entity_name, data=True):
            outgoing.append((target, data.get('relation', 'RELATED')))
        
        incoming = []
        for source, _, data in self.graph.in_edges(entity_name, data=True):
            incoming.append((source, data.get('relation', 'RELATED')))
        
        return {
            'entity': entity_name,
            'type': node_data.get('entity_type', 'UNKNOWN'),
            'frequency': node_data.get('frequency', 0),
            'papers': list(node_data.get('papers', set())),
            'sections': dict(node_data.get('sections', {})),
            'sources': list(node_data.get('sources', set())),
            'outgoing_relationships': outgoing[:10],
            'incoming_relationships': incoming[:10],
            'total_relationships': len(outgoing) + len(incoming)
        }
    
    def find_path(self, entity1: str, entity2: str, max_length: int = 4) -> List:
        """
        Find connection path between two entities.
        
        Args:
            entity1: First entity
            entity2: Second entity
            max_length: Maximum path length
            
        Returns:
            List of paths
        """
        entity1 = entity1.strip().lower()
        entity2 = entity2.strip().lower()
        
        if entity1 not in self.graph:
            print(f"Entity '{entity1}' not found in graph")
            return []
        
        if entity2 not in self.graph:
            print(f"Entity '{entity2}' not found in graph")
            return []
        
        try:
            paths = list(nx.all_simple_paths(self.graph, entity1, entity2, 
                                            cutoff=max_length))
            return paths[:5]  # Return up to 5 paths
        except nx.NetworkXNoPath:
            return []
        except Exception as e:
            print(f"Error finding path: {e}")
            return []
    
    def get_subgraph(self, entity: str, depth: int = 1) -> nx.MultiDiGraph:
        """
        Get subgraph around a specific entity.
        
        Args:
            entity: Entity to center on
            depth: Number of hops from entity
            
        Returns:
            Subgraph
        """
        entity = entity.strip().lower()
        
        if entity not in self.graph:
            print(f"Entity '{entity}' not found in graph")
            return nx.MultiDiGraph()
        
        # Get neighbors up to specified depth
        nodes = {entity}
        current_layer = {entity}
        
        for _ in range(depth):
            next_layer = set()
            for node in current_layer:
                try:
                    next_layer.update(self.graph.successors(node))
                    next_layer.update(self.graph.predecessors(node))
                except:
                    continue
            nodes.update(next_layer)
            current_layer = next_layer
        
        return self.graph.subgraph(nodes).copy()
    
    def save_graph(self, filename: str = 'knowledge_graph.pkl'):
        """
        Save the knowledge graph to file.
        
        Args:
            filename: Output filename
        """
        data = {
            'graph': self.graph,
            'entity_types': dict(self.entity_types),
            'paper_entities': self.paper_entities,
            'relationship_counts': dict(self.relationship_counts)
        }
        
        try:
            with open(filename, 'wb') as f:
                pickle.dump(data, f)
            print(f"✓ Knowledge graph saved to {filename}")
        except Exception as e:
            print(f"✗ Error saving graph: {e}")
    
    def load_graph(self, filename: str = 'knowledge_graph.pkl'):
        """
        Load knowledge graph from file.
        
        Args:
            filename: Input filename
        """
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Graph file not found: {filename}")
        
        try:
            with open(filename, 'rb') as f:
                data = pickle.load(f)
            
            self.graph = data['graph']
            self.entity_types = defaultdict(set, data['entity_types'])
            self.paper_entities = data['paper_entities']
            self.relationship_counts = Counter(data['relationship_counts'])
            
            print(f"✓ Knowledge graph loaded from {filename}")
            self.print_statistics()
        except Exception as e:
            print(f"✗ Error loading graph: {e}")
            raise
    
    def export_to_json(self, filename: str = 'knowledge_graph.json'):
        """
        Export graph to JSON format.
        
        Args:
            filename: Output filename
        """
        # Convert graph to JSON-serializable format
        nodes_data = []
        for node, data in self.graph.nodes(data=True):
            nodes_data.append({
                'id': node,
                'type': data.get('entity_type', 'UNKNOWN'),
                'frequency': data.get('frequency', 0),
                'papers': list(data.get('papers', set())),
                'sections': dict(data.get('sections', {})),
                'sources': list(data.get('sources', set()))
            })
        
        edges_data = []
        for source, target, data in self.graph.edges(data=True):
            edges_data.append({
                'source': source,
                'target': target,
                'relation': data.get('relation', 'UNKNOWN'),
                'paper': data.get('paper', ''),
                'context': data.get('context', ''),
                'edge_source': data.get('source', 'unknown')
            })
        
        graph_data = {
            'nodes': nodes_data,
            'edges': edges_data,
            'statistics': {
                'num_nodes': len(nodes_data),
                'num_edges': len(edges_data),
                'num_papers': len(self.paper_entities),
                'entity_types': {k: len(v) for k, v in self.entity_types.items()}
            }
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, indent=2, ensure_ascii=False)
            print(f"✓ Knowledge graph exported to {filename}")
        except Exception as e:
            print(f"✗ Error exporting graph: {e}")
    
    def visualize_subgraph(self, entity: str, depth: int = 1, 
                          filename: str = 'subgraph.png',
                          figsize: Tuple[int, int] = (15, 10)):
        """
        Visualize a subgraph around an entity.
        
        Args:
            entity: Entity to center visualization on
            depth: Number of hops from entity
            filename: Output filename
            figsize: Figure size (width, height)
        """
        subgraph = self.get_subgraph(entity, depth)
        
        if subgraph.number_of_nodes() == 0:
            print(f"Entity '{entity}' not found")
            return
        
        try:
            plt.figure(figsize=figsize)
            
            # Layout
            pos = nx.spring_layout(subgraph, k=2, iterations=50, seed=42)
            
            # Categorize nodes by source
            nodes_paper = []
            nodes_uniprot = []
            nodes_rag = []
            nodes_other = []
            
            for n, d in subgraph.nodes(data=True):
                sources = d.get('sources', set())
                if not sources:
                    nodes_other.append(n)
                elif sources == {'paper'}:
                    nodes_paper.append(n)
                elif sources == {'uniprot'}:
                    nodes_uniprot.append(n)
                elif sources == {'rag'}:
                    nodes_rag.append(n)
                elif 'uniprot' in sources:
                    nodes_uniprot.append(n)
                else:
                    nodes_other.append(n)

            # Draw nodes with different styles
            if nodes_paper:
                nx.draw_networkx_nodes(subgraph, pos, nodelist=nodes_paper,
                                       node_color='#8ecae6', node_shape='o', 
                                       node_size=900, alpha=0.85, label='Paper')
            if nodes_uniprot:
                nx.draw_networkx_nodes(subgraph, pos, nodelist=nodes_uniprot,
                                       node_color='#ffb703', node_shape='^', 
                                       node_size=1000, alpha=0.9, label='UniProt')
            if nodes_rag:
                nx.draw_networkx_nodes(subgraph, pos, nodelist=nodes_rag,
                                       node_color='#06d6a0', node_shape='s', 
                                       node_size=900, alpha=0.85, label='RAG')
            if nodes_other:
                nx.draw_networkx_nodes(subgraph, pos, nodelist=nodes_other,
                                       node_color='#bde0fe', node_shape='d', 
                                       node_size=800, alpha=0.8, label='Mixed')
            
            # Draw edges
            nx.draw_networkx_edges(subgraph, pos,
                                  edge_color='gray',
                                  arrows=True,
                                  arrowsize=20,
                                  alpha=0.5,
                                  width=1.5)
            
            # Draw labels
            nx.draw_networkx_labels(subgraph, pos, 
                                   font_size=8,
                                   font_weight='bold')
            
            # Draw edge labels (relations)
            edge_labels = {}
            for source, target, data in subgraph.edges(data=True):
                key = (source, target)
                if key not in edge_labels:
                    edge_labels[key] = data.get('relation', 'RELATED')
            
            nx.draw_networkx_edge_labels(subgraph, pos, edge_labels,
                                         font_size=6)
            
            plt.title(f"Knowledge Graph around '{entity}' (depth={depth})\n"
                     f"Nodes: {subgraph.number_of_nodes()}, "
                     f"Edges: {subgraph.number_of_edges()}")
            plt.legend(loc='best', framealpha=0.9)
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            print(f"✓ Visualization saved to {filename}")
            plt.close()
        except Exception as e:
            print(f"✗ Error creating visualization: {e}")


# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Build medical knowledge graph')
    parser.add_argument('--csv', default='SB_publications/SB_publication_PMC.csv',
                       help='Path to CSV file')
    parser.add_argument('--max-papers', type=int, default=None,
                       help='Maximum number of papers to process')
    parser.add_argument('--output', default='medical_knowledge_graph.pkl',
                       help='Output pickle file')
    parser.add_argument('--json', default='medical_knowledge_graph.json',
                       help='Output JSON file')
    args = parser.parse_args()
    
    # Initialize knowledge graph
    kg = MedicalKnowledgeGraph()
    
    # Build from CSV
    kg.build_from_csv(args.csv, max_papers=args.max_papers)
    
    # Save the graph
    kg.save_graph(args.output)
    
    # Export to JSON
    kg.export_to_json(args.json)
    
    # Example queries
    print("\n" + "="*70)
    print("Example Queries:")
    print("="*70)
    
    # Get most common entities
    if kg.graph.number_of_nodes() > 0:
        entity_freqs = [(node, data['frequency']) 
                       for node, data in kg.graph.nodes(data=True)]
        entity_freqs.sort(key=lambda x: x[1], reverse=True)
        
        if entity_freqs:
            top_entity = entity_freqs[0][0]
            
            # Query top entity
            print(f"\n1. Querying '{top_entity}':")
            result = kg.query_entity(top_entity)
            if 'error' not in result:
                print(f"   Type: {result['type']}")
                print(f"   Frequency: {result['frequency']}")
                print(f"   Appears in {len(result['papers'])} papers")
                print(f"   Sources: {', '.join(result['sources'])}")
                print(f"   Top outgoing relationships:")
                for target, relation in result['outgoing_relationships'][:5]:
                    print(f"     - {relation} -> {target}")
            
            # Visualize subgraph
            print(f"\n2. Creating visualization for '{top_entity}'...")
            kg.visualize_subgraph(top_entity, depth=2, 
                                 filename=f'{top_entity.replace(" ", "_")}_graph.png')
    
    print("\n" + "="*70)
    print("Knowledge graph construction complete!")
    print("Files created:")
    print(f"  - {args.output} (binary format)")
    print(f"  - {args.json} (JSON format)")
    print("="*70)
