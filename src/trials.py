"""
FastAPI service to scrape papers related to a query (default: EGFR),
enrich with local LLM like in RAG, and optionally ingest into the
existing vector store and knowledge graph.

Run:
  uvicorn src.trials:app --reload --port 8001

Endpoints:
  - GET  /health
  - POST /scrape            {"query": "EGFR", "max_results": 10}
  - POST /ingest            {"query": "EGFR", "max_results": 5, "ingest": true}

Notes:
  - Uses local LLM backend via LLMSummarizer (same as RAG).
  - Scrapes PubMed (and optionally ClinicalTrials.gov) summaries.
  - Ingestion adds to existing Chroma collection and updates the KG.
"""

from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode, urljoin
from pathlib import Path
import os
import json
import time

# Local imports from project
# Support running as a module (uvicorn src.trials:app) and as a script (python src/trials.py)
try:
    from .rag import MedicalRAGVectorStore
    from .knowledgegraph import MedicalKnowledgeGraph
except Exception:
    import sys
    from pathlib import Path as _Path
    _here = _Path(__file__).resolve()
    _src = _here.parent
    _root = _src.parent
    for p in (str(_src), str(_root)):
        if p not in sys.path:
            sys.path.append(p)
    try:
        from rag import MedicalRAGVectorStore  # type: ignore
        from knowledgegraph import MedicalKnowledgeGraph  # type: ignore
    except Exception as e:
        raise e


RAG_DIR = './medical_chroma_db'
COLLECTION_NAME = 'medical_papers'
KG_FILE = 'medical_knowledge_graph.pkl'


class ScrapeRequest(BaseModel):
    query: str = Field(default="EGFR")
    max_results: int = Field(default=10, ge=1, le=50)
    include_trials: bool = Field(default=False, description="Also scrape clinicaltrials.gov")


class PaperItem(BaseModel):
    title: str
    link: str
    abstract: Optional[str] = None
    authors: Optional[str] = None
    date: Optional[str] = None


class IngestRequest(ScrapeRequest):
    ingest: bool = Field(default=True)


class IngestResponse(BaseModel):
    success: bool
    message: str
    added: int = 0
    items: List[PaperItem] = []


app = FastAPI(title="Trials Scraper + Ingestor", version="0.1.0")


@app.get("/health")
def health():
    return {"ok": True}


def scrape_pubmed(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Scrape PubMed search page for basic paper metadata.

    Returns a list of dicts: {title, link, authors, date}
    """
    base = "https://pubmed.ncbi.nlm.nih.gov/"
    params = {"term": query}
    url = f"{base}?{urlencode(params)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116 Safari/537.36"
    }
    out: List[Dict[str, Any]] = []
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article.full-docsum")
        for art in articles[:max_results]:
            title_el = art.select_one("a.docsum-title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href") or ""
            link = urljoin(base, href)

            # Authors and date (best effort)
            authors = None
            date = None
            au_el = art.select_one("span.docsum-authors.full-authors") or art.select_one("span.docsum-authors")
            if au_el:
                authors = au_el.get_text(strip=True)
            j_el = art.select_one("span.docsum-journal-citation.full-journal-citation") or art.select_one("span.docsum-journal-citation")
            if j_el:
                date = j_el.get_text(strip=True).split(';')[0]

            out.append({"title": title, "link": link, "authors": authors, "date": date})
    except Exception as e:
        print(f"PubMed scrape error: {e}")
    return out


def scrape_clinical_trials(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Scrape ClinicalTrials.gov search page for basic trial metadata."""
    base = "https://clinicaltrials.gov/search"
    params = {"term": query}
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116 Safari/537.36"
    }
    out: List[Dict[str, Any]] = []
    try:
        resp = requests.get(base, params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # The site structure can change; best-effort selectors
        cards = soup.select(".ct-result-group .ct-result-title a, a.ct-study-list-item")
        for a in cards[:max_results]:
            title = a.get_text(strip=True)
            href = a.get("href") or ""
            link = urljoin("https://clinicaltrials.gov", href)
            out.append({"title": title, "link": link})
    except Exception as e:
        print(f"ClinicalTrials scrape error: {e}")
    return out


def fetch_abstract(rag: MedicalRAGVectorStore, link: str) -> Dict[str, str]:
    """Use RAG's fetcher to get abstract/results if possible."""
    try:
        return rag.fetch_paper_content(link)
    except Exception as e:
        print(f"fetch_abstract error for {link}: {e}")
        return {"abstract": "", "results": "", "full_text": ""}


@app.post("/scrape", response_model=List[PaperItem])
def scrape(req: ScrapeRequest):
    items = scrape_pubmed(req.query, req.max_results)
    if req.include_trials:
        items.extend(scrape_clinical_trials(req.query, req.max_results))
    # Attempt to fetch abstracts for pubmed links
    try:
        rag = MedicalRAGVectorStore(persist_directory=RAG_DIR)
        for it in items:
            if it.get('link'):
                content = fetch_abstract(rag, it['link'])
                it['abstract'] = (content.get('abstract') or '')[:1200]
    except Exception:
        pass
    return [PaperItem(**it) for it in items]


def _ensure_collection(rag: MedicalRAGVectorStore):
    """Ensure we have a writable collection; create if missing."""
    try:
        if not rag.load_collection(COLLECTION_NAME):
            # Create empty collection
            rag.collection = rag.chroma_client.create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
        return True
    except Exception as e:
        print(f"ensure_collection error: {e}")
        return False


@app.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest):
    items = scrape_pubmed(req.query, req.max_results)
    if req.include_trials:
        items.extend(scrape_clinical_trials(req.query, req.max_results))

    if not items:
        return IngestResponse(success=False, message="No items found", added=0, items=[])

    # Initialize systems
    rag = MedicalRAGVectorStore(persist_directory=RAG_DIR)
    _ensure_collection(rag)

    kg = MedicalKnowledgeGraph()
    try:
        if os.path.exists(KG_FILE):
            kg.load_graph(KG_FILE)
    except Exception as e:
        print(f"KG load error: {e}")

    added = 0
    ids = []
    embeddings = []
    metadatas = []
    documents_text = []

    for it in items:
        title = it.get('title') or ''
        link = it.get('link') or ''
        # Fetch content and extract keywords with local LLM
        content = fetch_abstract(rag, link)
        kws = rag.extract_medical_keywords(content.get('abstract', ''), content.get('results', ''))

        # Prepare metadata
        md = {
            'title': title[:500],
            'link': link,
            'abstract': (content.get('abstract') or '')[:1000],
            'results': (content.get('results') or '')[:1000],
            'authors': (it.get('authors') or '')[:500],
            'date': (it.get('date') or '')[:50],
            'yake_keywords': json.dumps(kws.get('llm_keywords', [])[:10]),
            'combined_keywords': json.dumps(kws.get('combined_keywords', [])[:20])
        }

        # Build document text for embedding
        text_for_embedding = rag._create_enhanced_text(title, content.get('abstract', ''), content.get('results', ''), kws.get('combined_keywords', []))
        documents_text.append(text_for_embedding)
        metadatas.append(md)
        ids.append(f"ing-{int(time.time()*1000)}-{added}")
        added += 1

        # Add to KG (LLM relations handled inside KG)
        try:
            kg.process_paper(title, content, link=link)
        except Exception as e:
            print(f"KG process error for {title}: {e}")

    # Generate embeddings and add to collection
    try:
        if documents_text:
            embs = rag.embedding_model.encode(documents_text, show_progress_bar=False, batch_size=16).tolist()
            rag.collection.add(ids=ids, embeddings=embs, metadatas=metadatas, documents=documents_text)
    except Exception as e:
        print(f"Vector add error: {e}")

    # Save KG
    try:
        kg.save_graph(KG_FILE)
        kg.export_to_json('medical_knowledge_graph.json')
    except Exception as e:
        print(f"KG save error: {e}")

    return IngestResponse(success=True, message=f"Processed {len(items)} items", added=added, items=[PaperItem(**it) for it in items])


if __name__ == "__main__":
    # Optional: run with built-in server for quick testing
    try:
        import uvicorn
        uvicorn.run("src.trials:app", host="0.0.0.0", port=8001, reload=True)
    except Exception as e:
        print("Start with:")
        print("  uvicorn src.trials:app --reload --port 8001")
