import warnings
import os
from uuid import uuid4
from typing import List, Dict, Any, Tuple

import pandas as pd
import time

from langchain.schema import Document
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.text_splitter import Language
from langchain.agents import Tool

from fastapi_backend.services.llm_service import LLMService
from fastapi_backend.rag_module.paper_scraper import PaperScraper
import logging

logger = logging.getLogger(__name__)

class VanillaRAGPipeline:
    def __init__(self, 
                llm_svc:LLMService=None, 
                chroma_persist_dir: str="tmp/embeddings/test_chroma",
                chunk_size: int = 1000,
                chunk_overlap: int = 200,
                csv_path: str = None,
                ):
        warnings.filterwarnings("ignore")

        self.documents = None
        self.docSearch = None
        self.paperSearch = None  # New: for paper-level retrieval
        self.llm_model = llm_svc.llm_model if llm_svc else None
        self.embedding_model = llm_svc.embeddings if llm_svc else None
        self.qa = None

        # retrieval parameters
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chroma_db_dir = chroma_persist_dir
        self.query_preprocessor=None
        self.csv_path = csv_path

        self.scraper = PaperScraper()

    def _load_csv(self, csv_path: str) -> pd.DataFrame:
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


    def _fetch_paper_content(self, url: str) -> Dict[str, str]:
        """
        Fetch paper content using the new PaperScraper with OSDR scrapper.
        
        Returns:
            Dict with comprehensive paper content including all sections
        """
        # Use the new PaperScraper
        scraper = PaperScraper()
        content = scraper.scrape_paper(url)
        
        # Ensure backward compatibility by mapping to expected format
        return {
            'abstract': content.get('abstract', ''),
            'results': content.get('results', ''),
            'full_text': content.get('full_text', ''),
            'sections': content.get('sections', {}),
            'title': content.get('title', ''),
            'authors': content.get('authors', []),
            'keywords': content.get('keywords', ''),
            'figures': content.get('figures', []),
            'tables': content.get('tables', [])
        }

    def _get_documents_from_csv(self) -> List[Dict[str, Any]]:
        # get csv data
        df = self._load_csv(self.csv_path)
        documents = []
        
        print("Phase 1: Fetching papers and extracting keywords...")
        
        for idx, row in df.iterrows():
            title = row['title']
            link = row['link']
            
            print(f"\nProcessing {idx+1}/{len(df)}: {title[:60]}...")
            
            content = self._fetch_paper_content(link)
            page_content = content['full_text']
            metadata = {
                'title': title,
                'link': link,
                'abstract': content['abstract'],
                'authors': ', '.join(content['authors']),
                'keywords': content['keywords'],
                'results': content['results'],
            }
            doc = Document(
                page_content=page_content,
                metadata=metadata,
                id=str(uuid4())
            )
            documents.append(doc)
            time.sleep(1)
        self.documents = documents
        
        return documents

    def _setup_paper_vector_store(self, collection_name="papers_collection"):
        """
        Create a separate vector store for papers (not chunks).
        Each paper is stored as a single document with unique UUID.
        """
        if self.embedding_model is None:
            raise ValueError("Embedding model is not set")
        
        if not os.path.exists(self.chroma_db_dir):
            os.makedirs(self.chroma_db_dir)

        persist_dir = self.chroma_db_dir
        paper_collection_path = os.path.join(persist_dir, "papers_chroma.sqlite3")

        logger.info(f"Papers Chroma DB path: {paper_collection_path}")
        logger.info(f"Collection name: {collection_name}")
        logger.info(f"Persist directory: {persist_dir}")

        # Check if the DB already exists
        if os.path.exists(paper_collection_path):
            logger.info("Loading existing Papers Chroma DB...")
            self.paperSearch = Chroma(
                collection_name=collection_name,
                embedding_function=self.embedding_model,
                persist_directory=persist_dir,
            )
        else:
            logger.info("Creating new Papers Chroma DB...")
            if self.documents is None:
                self._get_documents_from_csv()
            
            # Store papers as single documents (no chunking)
            paper_docs = []
            for doc in self.documents:
                # Create enhanced metadata for paper-level search
                paper_metadata = dict(doc.metadata)
                paper_metadata["paper_id"] = doc.id  # Store original document ID
                paper_metadata["paper_type"] = "full_paper"
                
                # Create paper document with enhanced content for better search
                paper_content = f"""
                Title: {doc.metadata['title']}
                Abstract: {doc.metadata['abstract']}
                Authors: {doc.metadata['authors']}
                Keywords: {doc.metadata['keywords']}
                Results: {doc.metadata['results']}
                Full Text: {doc.page_content[:5000]}  # Limit full text for embedding
                """
                
                paper_doc = Document(
                    page_content=paper_content,
                    metadata=paper_metadata,
                    id=doc.id  # Use same ID as original document
                )
                paper_docs.append(paper_doc)

            logger.info(f"Total papers to store: {len(paper_docs)}")
            
            self.paperSearch = Chroma.from_documents(
                documents=paper_docs, 
                embedding=self.embedding_model, 
                collection_name=collection_name,
                persist_directory=persist_dir,
                ids=[doc.id for doc in paper_docs],
            )
            
            self.paperSearch.persist()

        return self.paperSearch

    def _setup_vector_store(self, collection_name="default_collection"):
        if self.embedding_model is None:
            raise ValueError("Embedding model is not set")
        
        if not os.path.exists(self.chroma_db_dir):
            os.makedirs(self.chroma_db_dir)

        persist_dir = self.chroma_db_dir

        chroma_db_path = os.path.join(persist_dir, "chroma.sqlite3")

        logger.info(f"Chroma DB path: {chroma_db_path}")
        logger.info(f"Collection name: {collection_name}")
        logger.info(f"Persist directory: {persist_dir}")

        # Check if the DB already exists. If cleaning is enabled, rebuild to ensure artifacts are removed.
        if os.path.exists(chroma_db_path):
            logger.info("Loading existing Chroma DB...")

            self.docSearch = Chroma(
                collection_name=collection_name,
                embedding_function=self.embedding_model,
                persist_directory=persist_dir,
                # client_settings=client_settings #TODO Add client_settings for production #Settings(anonymized_telemetry=False)
            )
        else:
            logger.info("Creating new Chroma DB...")
            documents = self._get_documents_from_csv()
            text_splitter = RecursiveCharacterTextSplitter.from_language(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                language=Language.MARKDOWN,
            )
            split_docs = text_splitter.split_documents(documents)

            # filtered_docs = [doc for doc in split_docs if len(doc.page_content.strip()) >= 100]
            filtered_docs = []
            for chunk in split_docs:
                if len(chunk.page_content.strip()) < 100:
                    continue

                # Create a unique ID for the chunk
                chunk_id = str(uuid4())

                # Add/Update metadata to include original and chunk IDs
                new_metadata = dict(chunk.metadata)
                # new_metadata["scrape_id"] = original_id  # original document id
                new_metadata["chunk_id"] = chunk_id      # unique chunk id

                # Replace metadata with new metadata
                chunk.metadata = new_metadata

                filtered_docs.append(chunk)            

            logger.info(f"Total split docs before filtering: {len(split_docs)}")
            logger.info(f"Total split docs after filtering: {len(filtered_docs)}")
            
            ids = [doc.metadata["chunk_id"] for doc in filtered_docs]

            self.docSearch = Chroma.from_documents(
                documents=filtered_docs, 
                embedding=self.embedding_model, 
                collection_name=collection_name,
                persist_directory=persist_dir,
                ids=ids,
                # client_settings= client_settings #TODO Add client_settings for production #Settings(anonymized_telemetry=False)
            )
        
            self.docSearch.persist()

        return self.docSearch

    def search_papers(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search for papers by title, abstract, and content.
        Returns papers as complete documents, not chunks.
        
        Args:
            query: Search query
            top_k: Number of papers to return
        
        Returns:
            List of relevant papers with metadata
        """
        if self.paperSearch is None:
            self._setup_paper_vector_store()
        
        # Search papers
        retriever_papers = self.paperSearch.as_retriever(search_kwargs={"k": top_k})
        found_papers = retriever_papers.get_relevant_documents(query=query)
        
        # Format results similar to rag.py
        formatted_results = []
        for paper in found_papers:
            metadata = paper.metadata
            formatted_results.append({
                'paper_id': metadata.get('paper_id', ''),
                'title': metadata.get('title', ''),
                'link': metadata.get('link', ''),
                'abstract': metadata.get('abstract', '')[:300],
                'authors': metadata.get('authors', ''),
                'keywords': metadata.get('keywords', ''),
                'results': metadata.get('results', '')[:300],
                'document_preview': paper.page_content[:200]
            })
        
        return formatted_results

    def retrieve_documents(self, query: str, top_k_docs: int = 5) -> Tuple[List[Tuple[Document, float]], Dict[str, Any]]:
        """
        Retrieve relevant documents with optional query preprocessing.
        """
        retrieval_info = {
            'original_query': query,
            'query_transformation_applied': False,
            'preprocessing_info': {},
            'retrieval_metrics': {}
        }
        
        
        if self.documents is None:
            self._get_documents_from_csv()

        # Perform retrieval
        if not self.docSearch:
            self._setup_vector_store()
            # NOTE: not called--> self.setup_bm25_vector_store()

        retriever_chromadb = self.docSearch.as_retriever(search_kwargs={"k": top_k_docs})


        found_docs = retriever_chromadb.get_relevant_documents(query=query)

        # Add retrieval metrics
        retrieval_info['retrieval_metrics'] = {
            'total_docs_retrieved': len(found_docs),
        }
        
        return found_docs, retrieval_info

    def get_document_by_chunk_id(self, chunk_id: str):
        """
        Retrieve a specific document chunk by its chunk_id.
        
        Args:
            chunk_id: The unique chunk identifier
            
        Returns:
            Document object containing the chunk content and metadata
        """
        if not self.docSearch:
            self._setup_vector_store()
            logger.info("Vector store initialized.")
            
        
        try:
            # Use get_by_ids to retrieve by chunk_id
            if hasattr(self.docSearch, "get"):
                documents = self.docSearch.get(ids=[chunk_id])
                logger.info(f"Used get to retrieve document by chunk_id: {chunk_id}")
            else:
                documents = self.docSearch.similarity_search(
                    query="",  # empty query, you can put anything here
                    k=1,
                    filter={"chunk_id": chunk_id}
                )
                logger.info(f"Used similarity search to retrieve document by chunk_id: {chunk_id}")
            if documents:
                return documents["documents"][0]
            else:
                raise ValueError(f"No document found with chunk_id: {chunk_id}")
        except Exception as e:
            logger.error(f"Error retrieving document by chunk_id {chunk_id}: {str(e)}")
            raise
    
    def setup_qa_chain(self):
        """
        User can interact with the vector store and get a summarized response with the source documents.
        """
        if self.llm_model is None:
            raise ValueError("LLM model is not set")
        if self.docSearch is None:
            self._setup_vector_store()
        
        qa = RetrievalQA.from_chain_type(
            llm=self.llm_model,
            chain_type="stuff",
            retriever=self.docSearch.as_retriever(),
            return_source_documents=True
        )
        self.qa = qa
        return qa

    def get_qa_tool(self):
        if self.qa is None:
            self.setup_qa_chain()

        return Tool(
            name="DocumentQA",
            func=self.qa,   # could also use self.qa.invoke
            description="Answer questions based on the ingested source documents such as regulatory documents, investigatory brochures, company documents, project reports, etc."
        )        
