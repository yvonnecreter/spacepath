import pandas as pd
import requests
from bs4 import BeautifulSoup
import numpy as np
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
import pickle
import time
from typing import List, Dict, Tuple, Set
import re
from collections import Counter
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
import json
import uuid
import os
from llm_summarizer import LLMSummarizer

class MedicalRAGVectorStore:
    """
    Enhanced RAG system for medical papers with keyword extraction
    from abstracts and results sections. Uses ChromaDB with proper persistence.
    """
    
    def __init__(self, model_name='all-MiniLM-L6-v2', persist_directory='./chroma_db'):
        """
        Initialize the RAG system with models for embeddings and keyword extraction.
        
        Args:
            model_name: HuggingFace model for embeddings
            persist_directory: Directory to persist ChromaDB
        """
        self.embedding_model = SentenceTransformer(model_name)
        self.persist_directory = persist_directory
        
        # Create persist directory if it doesn't exist
        os.makedirs(persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client with persistent storage
        self.chroma_client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        self.collection = None
        self.collection_name = "medical_papers"
        
        # LLM configuration for keyword extraction (proteins & pathways)
        self.llm_backend = os.getenv('LLM_BACKEND', 'ollama')
        self.llm_model = os.getenv('LLM_MODEL', 'granite3.3:2b')
        try:
            self.llm = LLMSummarizer(backend=self.llm_backend, model_name=self.llm_model)
        except Exception:
            self.llm = None

        # Try to load spaCy model for biomedical NER
        try:
            # Use scispacy for biomedical text if available
            self.nlp = spacy.load("en_core_sci_sm")
            print("✓ Loaded scispacy model for biomedical NER")
        except Exception:
            try:
                # Fallback to standard spacy
                self.nlp = spacy.load("en_core_web_sm")
                print("✓ Loaded standard spacy model")
            except Exception:
                print("⚠ Warning: spaCy model not found. Install with:")
                print("  pip install spacy && python -m spacy download en_core_web_sm")
                print("  For biomedical: pip install scispacy && pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.1/en_core_sci_sm-0.5.1.tar.gz")
                self.nlp = None

        # Medical/biological terms that are important
        self.medical_pos_tags = {'NOUN', 'PROPN', 'ADJ'}
        self.stopwords = self._load_medical_stopwords()

    @staticmethod
    def define_relationship_patterns() -> List[Dict]:
        """
        Provide relationship patterns similar to KnowledgeGraph for reuse.
        Useful if downstream wants to infer edges from LLM-extracted terms.
        """
        return [
            {'verbs': ['cause', 'causes', 'caused', 'causing', 'induce', 'induces', 'induced'], 'relation': 'CAUSES'},
            {'verbs': ['trigger', 'triggers', 'triggered', 'initiate', 'initiates'], 'relation': 'TRIGGERS'},
            {'verbs': ['lead', 'leads', 'leading', 'result', 'results', 'resulting'], 'relation': 'LEADS_TO'},
            {'verbs': ['inhibit', 'inhibits', 'inhibited', 'suppress', 'suppresses', 'block', 'blocks'], 'relation': 'INHIBITS'},
            {'verbs': ['activate', 'activates', 'activated', 'stimulate', 'stimulates', 'enhance', 'enhances'], 'relation': 'ACTIVATES'},
            {'verbs': ['regulate', 'regulates', 'regulated', 'modulate', 'modulates', 'control', 'controls'], 'relation': 'REGULATES'},
            {'verbs': ['associate', 'associated', 'correlate', 'correlated', 'link', 'linked'], 'relation': 'ASSOCIATED_WITH'},
            {'verbs': ['interact', 'interacts', 'interacted', 'bind', 'binds'], 'relation': 'INTERACTS_WITH'},
            {'verbs': ['express', 'expresses', 'expressed', 'produce', 'produces', 'produced'], 'relation': 'EXPRESSES'},
            {'verbs': ['increase', 'increases', 'increased', 'elevate', 'elevates', 'upregulate'], 'relation': 'INCREASES'},
            {'verbs': ['decrease', 'decreases', 'decreased', 'reduce', 'reduces', 'downregulate'], 'relation': 'DECREASES'},
            {'verbs': ['treat', 'treats', 'treated', 'therapy', 'therapeutic'], 'relation': 'TREATS'},
            {'verbs': ['prevent', 'prevents', 'prevented', 'protection', 'protective'], 'relation': 'PREVENTS'},
            {'verbs': ['involve', 'involves', 'involved', 'participate', 'participates'], 'relation': 'INVOLVED_IN'},
            {'verbs': ['require', 'requires', 'required', 'depend', 'depends', 'dependent'], 'relation': 'REQUIRES'},
        ]
    
    def _load_medical_stopwords(self) -> Set[str]:
        """Load common stopwords while preserving medical terms."""
        common_stops = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'what', 'which', 'who', 'when', 'where', 'why', 'how', 'all', 'each',
            'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such',
            'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
            'very', 'also', 'however', 'therefore', 'thus', 'study', 'studies',
            'using', 'used', 'found', 'showed', 'shown', 'observed', 'demonstrated', 'abstract', 'summary', 'background'
        }
        return common_stops
    
    def load_csv(self, csv_path: str) -> pd.DataFrame:
        """Load CSV with paper titles and links."""
        df = pd.read_csv(csv_path)
        
        if 'title' not in df.columns and len(df.columns) >= 1:
            df.columns = ['title'] + list(df.columns[1:])
        if 'link' not in df.columns and 'url' not in df.columns:
            if len(df.columns) >= 2:
                df = df.rename(columns={df.columns[1]: 'link'})
        elif 'url' in df.columns:
            df = df.rename(columns={'url': 'link'})
            
        return df
    
    def fetch_paper_content(self, url: str) -> Dict[str, str]:
        """
        Fetch paper content and extract abstract and results sections.
        
        Returns:
            Dict with 'abstract', 'results', and 'full_text'
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            content = {
                'abstract': '',
                'results': '',
                'full_text': ''
            }
            
            # Extract abstract
            abstract_section = soup.find(['div', 'section', 'p'], 
                                        class_=re.compile(r'abstract', re.I))
            if not abstract_section:
                abstract_section = soup.find(['div', 'section'], 
                                            id=re.compile(r'abstract', re.I))
            if abstract_section:
                content['abstract'] = abstract_section.get_text(strip=True, separator=' ')
            
            # Extract results section
            results_section = soup.find(['div', 'section'], 
                                       class_=re.compile(r'results?', re.I))
            if not results_section:
                results_section = soup.find(['div', 'section'], 
                                          id=re.compile(r'results?', re.I))
            if results_section:
                content['results'] = results_section.get_text(strip=True, separator=' ')
            
            # Extract full text
            content_divs = soup.find_all(['div', 'article', 'section'], 
                                        class_=re.compile(r'body|content|article'))
            if content_divs:
                content['full_text'] = ' '.join([div.get_text(strip=True, separator=' ') 
                                                for div in content_divs])
            else:
                paragraphs = soup.find_all('p')
                content['full_text'] = ' '.join([p.get_text(strip=True) 
                                                for p in paragraphs])
            
            # Clean up
            for key in content:
                content[key] = re.sub(r'\s+', ' ', content[key]).strip()
            
            return content
            
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return {'abstract': '', 'results': '', 'full_text': ''}
    
    def extract_keywords_llm(self, text: str, max_items: int = 25) -> Dict[str, List[str]]:
        """
        Extract proteins, pathways, and general keywords using an LLM.
        Falls back to heuristics if LLM is unavailable.
        Returns a dict: {'proteins': [...], 'pathways': [...], 'general': [...], 'all': [...]}.
        """
        if not text:
            return {'proteins': [], 'pathways': [], 'all': []}

        # If LLM available, instruct to return strict JSON
        if getattr(self, 'llm', None) and getattr(self.llm, 'backend', None):
            sample = text[:6000]
            prompt = f"""
            You are an expert biomedical text-mining assistant.

            Task: From the text, extract three lists as STRICT JSON:
            1) proteins — gene/protein names explicitly mentioned (e.g., DMD, EGFR, NADPH oxidase)
            2) pathways — biological pathways/processes (e.g., MAPK signaling, PI3K/AKT pathway)
            3) general_keywords — salient biomedical terms not covered above (e.g., diseases, phenotypes, mechanisms, clinical endpoints)

            Rules:
            - Only include terms present in the text; do not invent.
            - Use concise canonical surface forms; avoid overly generic words.
            - Return STRICT JSON with exactly these keys: "proteins", "pathways", "general_keywords".
            - Limit to top {max_items} unique items per list.

            Text:
            {sample}

            Output JSON example:
            {{
              "proteins": ["EGFR", "KRAS"],
              "pathways": ["PI3K/AKT pathway"],
              "general_keywords": ["non-small cell lung cancer", "apoptosis"]
            }}
            """

            try:
                resp = self.llm.generate_summary(prompt, max_tokens=400)
                if resp:
                    # Try direct JSON parse; if not, extract the first JSON-looking block
                    parsed = None
                    try:
                        parsed = json.loads(resp)
                    except Exception:
                        import re as _re
                        m = _re.search(r"\{[\s\S]*\}", resp)
                        if m:
                            parsed = json.loads(m.group(0))
                    if isinstance(parsed, dict):
                        proteins = [p.strip() for p in parsed.get('proteins', []) if isinstance(p, str)]
                        pathways = [p.strip() for p in parsed.get('pathways', []) if isinstance(p, str)]
                        general = [p.strip() for p in parsed.get('general_keywords', []) if isinstance(p, str)]
                        # Deduplicate while preserving order
                        def _dedup(seq):
                            seen = set()
                            out = []
                            for s in seq:
                                key = s.lower()
                                if key not in seen and s:
                                    seen.add(key)
                                    out.append(s)
                            return out
                        proteins = _dedup(proteins)[:max_items]
                        pathways = _dedup(pathways)[:max_items]
                        general = _dedup(general)[:max_items]
                        return {
                            'proteins': proteins,
                            'pathways': pathways,
                            'general': general,
                            'all': _dedup(proteins + pathways + general)
                        }
            except Exception:
                pass

        # Fallback: use spaCy entities and simple patterns as heuristic
        proteins, pathways, general = [], [], []
        try:
            if self.nlp:
                doc = self.nlp(text[:100000])
                # Collect candidate entities and noun chunks
                cands = set()
                for ent in doc.ents:
                    if ent.label_.upper() in {"GENE_OR_GENE_PRODUCT", "PROTEIN", "CHEMICAL", "ORG", "PRODUCT"}:
                        cands.add(ent.text)
                for chunk in doc.noun_chunks:
                    if any(t.lower_ in {"pathway", "signaling", "signalling"} for t in chunk):
                        cands.add(chunk.text)
                for c in cands:
                    cl = c.lower()
                    if any(k in cl for k in [" pathway", "pathway ", " signaling", " signalling", "cascade", "axis"]):
                        pathways.append(c)
                    else:
                        # Heuristic: uppercase-looking token as protein/gene, otherwise general
                        if re.match(r'^[A-Z0-9-]{2,10}$', c.strip()):
                            proteins.append(c)
                        else:
                            general.append(c)
        except Exception:
            pass

        # Deduplicate and trim
        def _dedup(seq):
            seen = set()
            out = []
            for s in seq:
                key = s.lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    out.append(s.strip())
            return out
        proteins = _dedup(proteins)[:max_items]
        pathways = _dedup(pathways)[:max_items]
        general = _dedup(general)[:max_items]
        return {'proteins': proteins, 'pathways': pathways, 'general': general, 'all': _dedup(proteins + pathways + general)}
    
    def extract_keywords_spacy(self, text: str, top_n: int = 20) -> List[str]:
        """Extract medical keywords using local LLM (replaces spaCy heuristic).

        Uses extract_keywords_llm under the hood and returns a flat list
        of top unique keywords (proteins + pathways), up to top_n.
        """
        if not text:
            return []
        try:
            llm_kws = self.extract_keywords_llm(text, max_items=top_n)
            all_items = llm_kws.get('all') or []
            if not all_items:
                # Fallback: merge proteins and pathways
                all_items = (llm_kws.get('proteins') or []) + (llm_kws.get('pathways') or [])
            # Deduplicate while preserving order
            seen = set()
            out = []
            for item in all_items:
                key = (item or '').strip()
                if not key:
                    continue
                low = key.lower()
                if low not in seen:
                    seen.add(low)
                    out.append(key)
            return out[:top_n]
        except Exception:
            return []
    
    def extract_keywords_tfidf(self, texts: List[str], top_n: int = 15) -> Dict[int, List[str]]:
        """Extract keywords using TF-IDF across all documents."""
        if not texts:
            return {}
        
        vectorizer = TfidfVectorizer(
            max_features=200,
            ngram_range=(1, 3),
            stop_words='english',
            min_df=1,
            max_df=0.8
        )
        
        try:
            tfidf_matrix = vectorizer.fit_transform(texts)
            feature_names = vectorizer.get_feature_names_out()
            
            keywords_per_doc = {}
            for idx in range(len(texts)):
                doc_tfidf = tfidf_matrix[idx].toarray()[0]
                top_indices = doc_tfidf.argsort()[-top_n:][::-1]
                keywords_per_doc[idx] = [feature_names[i] for i in top_indices 
                                        if doc_tfidf[i] > 0]
            
            return keywords_per_doc
        except:
            return {}
    
    def extract_medical_keywords(self, abstract: str, results: str) -> Dict[str, any]:
        """
        Extract comprehensive keywords from abstract and results.
        
        Returns:
            Dict with various keyword extraction methods
        """
        combined_text = f"{abstract} {results}"
        
        keywords = {
            'llm_keywords': [],        # union of proteins + pathways + general
            'llm_proteins': [],
            'llm_pathways': [],
            'llm_general': [],
            'spacy_entities': [],
            'abstract_keywords': [],   # subset of llm_keywords that appear in abstract
            'results_keywords': [],    # subset that appear in results
            'combined_keywords': []
        }

        # LLM-driven keyword extraction focused on proteins and pathways
        llm_kws = self.extract_keywords_llm(combined_text, max_items=25)
        keywords['llm_proteins'] = llm_kws.get('proteins', [])
        keywords['llm_pathways'] = llm_kws.get('pathways', [])
        keywords['llm_general'] = llm_kws.get('general', [])
        keywords['llm_keywords'] = llm_kws.get('all', [])

        # Derive per-section subsets for quick reference
        low_abs = abstract.lower() if abstract else ''
        low_res = results.lower() if results else ''
        if abstract:
            keywords['abstract_keywords'] = [k for k in keywords['llm_keywords'] if k.lower() in low_abs]
        if results:
            keywords['results_keywords'] = [k for k in keywords['llm_keywords'] if k.lower() in low_res]

        # Replace spaCy NER with local-LLM keyword extraction
        spacy_kws = self.extract_keywords_spacy(combined_text, top_n=20)
        keywords['spacy_entities'] = spacy_kws
        
        # Combine all unique keywords
        all_keywords = set()
        for key in ['llm_keywords', 'spacy_entities', 'abstract_keywords', 'results_keywords']:
            all_keywords.update([kw.lower() for kw in keywords[key]])
        
        keywords['combined_keywords'] = list(all_keywords)
        
        return keywords
    
    def process_csv_to_documents(self, csv_path: str) -> List[Dict]:
        """
        Process CSV, fetch content, and extract keywords.
        """
        df = self.load_csv(csv_path)
        documents = []
        all_abstracts = []
        all_results = []
        
        print("Phase 1: Fetching papers and extracting keywords...")
        
        # Normalize possible metadata columns
        possible_author_cols = [c for c in df.columns if c.lower() in {"authors", "author", "creators"}]
        possible_date_cols = [c for c in df.columns if c.lower() in {"date", "year", "published", "publication_date"}]

        for idx, row in df.iterrows():
            title = row['title']
            link = row['link']
            authors = None
            pub_date = None
            if possible_author_cols:
                try:
                    authors = str(row[possible_author_cols[0]]).strip()
                except Exception:
                    authors = None
            if possible_date_cols:
                try:
                    pub_date = str(row[possible_date_cols[0]]).strip()
                except Exception:
                    pub_date = None
            
            print(f"\nProcessing {idx+1}/{len(df)}: {title[:60]}...")
            
            content = self.fetch_paper_content(link)
            time.sleep(1)  # Be respectful
            
            # Extract keywords
            keywords = self.extract_medical_keywords(
                content['abstract'], 
                content['results']
            )
            
            print(f"  Extracted {len(keywords['combined_keywords'])} unique keywords")
            if keywords['llm_keywords']:
                print(f"  Top keywords: {', '.join(keywords['llm_keywords'][:5])}")
            
            # Create document with enhanced metadata
            doc = {
                'title': title,
                'link': link,
                'abstract': content['abstract'][:2000],
                'results': content['results'][:3000],
                'authors': authors,
                'date': pub_date,
                'keywords': keywords,
                'text_for_embedding': self._create_enhanced_text(
                    title, 
                    content['abstract'], 
                    content['results'],
                    keywords['combined_keywords']
                )
            }
            
            documents.append(doc)
            all_abstracts.append(content['abstract'])
            all_results.append(content['results'])
        
        # Phase 2: TF-IDF across all documents for global importance
        print("\nPhase 2: Computing TF-IDF keywords across corpus...")
        combined_texts = [f"{doc['abstract']} {doc['results']}" for doc in documents]
        tfidf_keywords = self.extract_keywords_tfidf(combined_texts, top_n=15)
        
        for idx, doc in enumerate(documents):
            if idx in tfidf_keywords:
                doc['keywords']['tfidf_keywords'] = tfidf_keywords[idx]
                doc['keywords']['combined_keywords'].extend(tfidf_keywords[idx])
                doc['keywords']['combined_keywords'] = list(set(doc['keywords']['combined_keywords']))
        
        return documents
    
    def _create_enhanced_text(self, title: str, abstract: str, 
                             results: str, keywords: List[str]) -> str:
        """
        Create enhanced text for embedding by emphasizing keywords.
        """
        # Repeat important keywords to boost their importance in embeddings
        keyword_boost = ' '.join(keywords[:10]) + ' '
        
        text_parts = [
            f"Title: {title}",
            f"Keywords: {keyword_boost}",
            f"Abstract: {abstract[:1500]}" if abstract else "",
            f"Results: {results[:2000]}" if results else ""
        ]
        
        return '\n\n'.join([p for p in text_parts if p])
    
    def create_vector_store(self, documents: List[Dict], collection_name: str = None):
        """
        Create ChromaDB vector store from processed documents.
        
        Args:
            documents: List of processed documents
            collection_name: Name for the collection (default: medical_papers)
        """
        if collection_name:
            self.collection_name = collection_name
        
        print(f"\n{'='*70}")
        print(f"Creating ChromaDB collection '{self.collection_name}'...")
        print(f"{'='*70}")
        
        # Delete existing collection if it exists
        try:
            self.chroma_client.delete_collection(self.collection_name)
            print(f"✓ Deleted existing collection")
        except:
            pass
        
        # Create new collection
        self.collection = self.chroma_client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )
        
        print(f"✓ Created new collection")
        print(f"\nAdding {len(documents)} documents to vector store...")
        
        # Prepare data for ChromaDB
        ids = []
        embeddings = []
        metadatas = []
        documents_text = []
        
        for idx, doc in enumerate(documents):
            doc_id = str(uuid.uuid4())  # Generate unique ID
            ids.append(doc_id)
            documents_text.append(doc['text_for_embedding'])
            
            # Create metadata (ChromaDB supports nested dicts)
            metadata = {
                'title': doc['title'][:500],  # Limit size
                'link': doc['link'],
                'abstract': doc['abstract'][:1000],  # Limit size
                'results': doc['results'][:1000],
                'authors': (doc.get('authors') or '')[:500],
                'date': (doc.get('date') or '')[:50],
                # Keep backward-compatible key name used by the app: store LLM keywords under 'yake_keywords'
                'yake_keywords': json.dumps(doc['keywords'].get('llm_keywords', [])[:10]),
                'combined_keywords': json.dumps(doc['keywords']['combined_keywords'][:20]),
                'llm_proteins': json.dumps(doc['keywords'].get('llm_proteins', [])[:20]),
                'llm_pathways': json.dumps(doc['keywords'].get('llm_pathways', [])[:20]),
                'llm_general': json.dumps(doc['keywords'].get('llm_general', [])[:20]),
                'doc_index': idx
            }
            metadatas.append(metadata)
        
        # Generate embeddings
        print("\nGenerating embeddings...")
        embeddings = self.embedding_model.encode(
            documents_text, 
            show_progress_bar=True,
            batch_size=32
        ).tolist()
        
        # Add to ChromaDB in batches
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            batch_end = min(i + batch_size, len(ids))
            self.collection.add(
                ids=ids[i:batch_end],
                embeddings=embeddings[i:batch_end],
                metadatas=metadatas[i:batch_end],
                documents=documents_text[i:batch_end]
            )
            print(f"  ✓ Added batch {i//batch_size + 1}/{(len(ids)-1)//batch_size + 1}")
        
        print(f"\n{'='*70}")
        print(f"✅ Vector store created successfully!")
        print(f"   Location: {self.persist_directory}")
        print(f"   Collection: {self.collection_name}")
        print(f"   Documents: {len(documents)}")
        print(f"{'='*70}\n")
    
    def load_collection(self, collection_name: str = None):
        """
        Load existing ChromaDB collection.
        
        Args:
            collection_name: Name of collection to load
        """
        if collection_name:
            self.collection_name = collection_name
        
        try:
            self.collection = self.chroma_client.get_collection(self.collection_name)
            count = self.collection.count()
            print(f"✓ Loaded collection '{self.collection_name}' with {count} documents")
            return True
        except Exception as e:
            print(f"⚠ Error loading collection: {e}")
            collections = self.chroma_client.list_collections()
            if collections:
                print(f"Available collections: {[c.name for c in collections]}")
            else:
                print("No collections found in database")
            return False
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search with enhanced results showing keywords.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            List of relevant documents with metadata
        """
        if self.collection is None:
            raise ValueError("Collection not loaded. Call create_vector_store or load_collection first.")
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query]).tolist()
        
        # Search ChromaDB
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            include=['metadatas', 'documents', 'distances']
        )
        
        # Format results with recency weighting (50%)
        formatted_results = []
        current_year = time.localtime().tm_year

        def parse_year(meta: dict) -> int:
            # Try multiple fields to extract a 4-digit year
            for k in ('date', 'year', 'published', 'publication_date'):
                val = meta.get(k)
                if not val:
                    continue
                try:
                    # If already an int-like
                    y = int(str(val)[:4])
                    if 1800 <= y <= current_year + 1:
                        return y
                except Exception:
                    pass
                import re as _re
                m = _re.search(r'(19|20)\d{2}', str(val))
                if m:
                    y = int(m.group(0))
                    if 1800 <= y <= current_year + 1:
                        return y
            return 0
        for idx in range(len(results['ids'][0])):
            metadata = results['metadatas'][0][idx]
            
            # Prefer LLM keywords if available; fall back to stored key
            try:
                top_keywords = json.loads(metadata.get('yake_keywords', '[]'))
            except Exception:
                top_keywords = []

            distance = results['distances'][0][idx]
            similarity = 1 - float(distance)
            year = parse_year(metadata)
            if year:
                age = max(0, current_year - year)
                # Map age 0->1.0, 10+ years -> 0.0 linearly
                recency = max(0.0, 1.0 - min(10, age) / 10.0)
            else:
                recency = 0.5  # neutral if unknown

            combined_score = 0.5 * similarity + 0.5 * recency

            formatted_results.append({
                'title': metadata.get('title', ''),
                'link': metadata.get('link', ''),
                'abstract': (metadata.get('abstract') or '')[:300],
                'authors': metadata.get('authors', ''),
                'date': metadata.get('date', ''),
                'keywords': top_keywords,
                'all_keywords': json.loads(metadata.get('combined_keywords', '[]'))[:15],
                'distance': distance,
                'score': combined_score,
                'document_preview': (results['documents'][0][idx] or '')[:200]
            })

        # Sort by combined score desc
        formatted_results.sort(key=lambda r: r.get('score', 0), reverse=True)
        return formatted_results
    
    def get_collection_stats(self) -> Dict:
        """Get statistics about the current collection."""
        if self.collection is None:
            return {"error": "No collection loaded"}
        
        count = self.collection.count()
        return {
            'collection_name': self.collection_name,
            'document_count': count,
            'persist_directory': self.persist_directory
        }


# Example usage
if __name__ == "__main__":
    # Initialize enhanced RAG system
    rag = MedicalRAGVectorStore(persist_directory='./medical_chroma_db')
    
    # Process CSV with keyword extraction
    documents = rag.process_csv_to_documents('SB_publications/SB_publication_PMC.csv')
    
    # Create vector store (automatically persisted to disk)
    rag.create_vector_store(documents)
    
    # Print stats
    print("\n" + "="*70)
    stats = rag.get_collection_stats()
    print(f"Collection Stats: {stats}")
    
    # Test search
    print("\n" + "="*70)
    print("Testing semantic search with keywords...")
    results = rag.search("oxidative stress endoplasmic reticulum", top_k=3)
    
    for i, result in enumerate(results, 1):
        print(f"\n{'='*70}")
        print(f"Result {i} (Distance: {result['distance']:.4f})")
        print(f"{'='*70}")
        print(f"Title: {result['title']}")
        print(f"Link: {result['link']}")
        print(f"\nTop Keywords: {', '.join(result['keywords'])}")
        print(f"\nAbstract: {result['abstract']}...")
        print(f"\nAll Keywords ({len(result['all_keywords'])}): {', '.join(result['all_keywords'])}")
    
    # To reload later in another session:
    print("\n" + "="*70)
    print("Example: Loading existing collection...")
    rag2 = MedicalRAGVectorStore(persist_directory='./medical_chroma_db')
    rag2.load_collection('medical_papers')
    results2 = rag2.search("NADPH oxidase", top_k=2)
    print(f"✓ Found {len(results2)} results from loaded collection")
