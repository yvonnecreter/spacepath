"""
Flask Web Application for Medical Papers Knowledge System
File: app.py

Run with: python app.py
Then open: http://localhost:5000
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import json
import networkx as nx
from networkx.readwrite import json_graph
import pickle
from pathlib import Path

# Import custom modules
try:
    from rag import MedicalRAGVectorStore
    from knowledgegraph import MedicalKnowledgeGraph
    from llm_summarizer import LLMSummarizer
    from uniprot import UniProtHarvester
except ImportError:
    print("⚠️ Please ensure rag.py, knowledgegraph.py, and llm_summarizer.py are in the same directory")
    exit(1)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Global variables
rag_system = None
knowledge_graph = None
llm_summarizer = None

# Configuration
RAG_DIR = './chroma_backup'
COLLECTION_NAME = 'medical_papers'
KG_FILE = 'medical_knowledge_graph.pkl'
# Resolve KEGG file relative to project root (parent of this src folder)
KEGG_FILE = str((Path(__file__).resolve().parent.parent / 'data' / 'hsa05223_network.json').resolve())

# LLM Configuration - Change these as needed
LLM_BACKEND = os.getenv('LLM_BACKEND', 'ollama')  # 'ollama', 'openai', or 'anthropic'
LLM_MODEL = os.getenv('LLM_MODEL', 'granite3.3:2b')  # Model name

def initialize_systems():
    """Initialize RAG and KG systems if files exist."""
    global rag_system, knowledge_graph, llm_summarizer
    
    try:
        if os.path.exists(RAG_DIR):
            print(f"Initializing RAG system from {RAG_DIR}...")
            rag_system = MedicalRAGVectorStore(persist_directory=RAG_DIR)
            success = rag_system.load_collection(COLLECTION_NAME)
            if success:
                print("✓ RAG system loaded successfully")
            else:
                print("⚠ RAG directory exists but no collection found")
                rag_system = None
        else:
            print(f"⚠ RAG directory not found: {RAG_DIR}")
    except Exception as e:
        print(f"❌ Could not load RAG: {e}")
        rag_system = None
    
    try:
        if os.path.exists(KG_FILE):
            print(f"Loading Knowledge Graph from {KG_FILE}...")
            knowledge_graph = MedicalKnowledgeGraph()
            knowledge_graph.load_graph(KG_FILE)
            print("✓ Knowledge Graph loaded successfully")
        else:
            print(f"⚠ KG file not found: {KG_FILE}")
    except Exception as e:
        print(f"❌ Could not load KG: {e}")
        knowledge_graph = None
    
    # Initialize LLM Summarizer
    try:
        print(f"Initializing LLM Summarizer ({LLM_BACKEND}/{LLM_MODEL})...")
        llm_summarizer = LLMSummarizer(backend=LLM_BACKEND, model_name=LLM_MODEL)
        if llm_summarizer.backend:
            print("✓ LLM Summarizer initialized")
        else:
            print("⚠ LLM Summarizer not available - tooltips will use fallback")
    except Exception as e:
        print(f"⚠ Could not initialize LLM: {e}")
        llm_summarizer = None

@app.route('/')
def index():
    """Main page.

    If demo mode is enabled (via query param `demo-mode=true` or env `DEMO_MODE`),
    the template will conditionally embed the interactive relationship demo instead
    of the regular Knowledge Graph window.
    """
    # Determine demo mode from query param or environment
    q = (request.args.get('demo-mode') or '').strip().lower()
    env_demo = (os.getenv('DEMO_MODE') or '').strip().lower()
    truthy = {'1', 'true', 'yes', 'on'}
    demo_mode = (q in truthy) or (env_demo in truthy)

    return render_template('index.html', demo_mode=demo_mode)

@app.route('/demo-relationship')
def demo_relationship():
    """Serve the interactive relationship demo page as a standalone view."""
    return render_template('interactive_relationship_demo_ref.html')

@app.route('/api/status')
def get_status():
    """Get system status."""
    status = {
        'rag_loaded': False,
        'kg_loaded': knowledge_graph is not None,
        'rag_stats': None,
        'kg_stats': None,
        'rag_error': None
    }
    
    # Check RAG system
    if rag_system:
        try:
            stats = rag_system.get_collection_stats()
            if 'error' not in stats:
                status['rag_loaded'] = True
                status['rag_stats'] = stats
            else:
                status['rag_error'] = stats.get('error', 'Collection not loaded')
        except Exception as e:
            status['rag_error'] = str(e)
    else:
        status['rag_error'] = 'RAG system not initialized'
    
    # Check KG system
    if knowledge_graph:
        status['kg_stats'] = {
            'num_entities': knowledge_graph.graph.number_of_nodes(),
            'num_relationships': knowledge_graph.graph.number_of_edges(),
            'num_papers': len(knowledge_graph.paper_entities)
        }
    
    return jsonify(status)

@app.route('/api/reload', methods=['POST'])
def reload_systems():
    """Manually reload RAG and KG systems."""
    initialize_systems()
    return get_status()

def _parse_kegg_relations(rel_str):
    """Parse a KEGG relation string into a list of token groups and edge type.

    Example: "EGFR* -> GRB2 -> SOS -> RAS -| RAF" -> returns
    ([{"EGFR*"}, {"GRB2"}, {"SOS"}, {"RAS"}, {"RAF"}], ["->","->","->","-|"])
    """
    # Normalize arrows with spaces to split reliably
    rel_str = rel_str.replace('->', ' -> ').replace('-|', ' -| ')
    parts = [p.strip() for p in rel_str.split() if p.strip()]
    groups = []
    connectors = []

    current_tokens = []
    i = 0
    while i < len(parts):
        token = parts[i]
        if token in ('->', '-|'):
            # finalize previous group
            if current_tokens:
                groups.append(' '.join(current_tokens))
                current_tokens = []
            connectors.append(token)
        else:
            current_tokens.append(token)
        i += 1
    if current_tokens:
        groups.append(' '.join(current_tokens))

    def split_group(g):
        # remove wrapping parentheses
        g = g.strip()
        if g.startswith('(') and g.endswith(')'):
            g = g[1:-1]
        # split by comma to handle "STAT3,STAT5" cases
        items = []
        for part in g.split(','):
            part = part.strip()
            # split by '//' (parallel) into separate tokens
            subs = [s.strip() for s in part.split('//')]
            for sub in subs:
                # split by '+' if present (e.g., ERBB2*+EGFR)
                plus_parts = [pp.strip() for pp in sub.split('+')]
                for pp in plus_parts:
                    if pp:
                        items.append(pp)
        return set(items) if items else set()

    node_groups = [split_group(g) for g in groups]
    return node_groups, connectors

@app.route('/api/kegg-network')
def kegg_network():
    """Return KEGG network from data/hsa05223_network.json as nodes/links.

    - Unique entities as nodes
    - Unidirectional edges with type 'activation' for '->' and 'inhibition' for '-|'
    - Include pathways metadata on nodes and edges
    """
    try:
        # Load file
        if not os.path.exists(KEGG_FILE):
            return jsonify({'error': f'KEGG file not found: {KEGG_FILE}'}), 404
        with open(KEGG_FILE, 'r') as f:
            raw = json.load(f)

        nodes = {}
        edges = {}
        all_pathways = set()

        for key, entry in raw.items():
            pathways = entry.get('pathway', []) or []
            relations = entry.get('relations', []) or []
            for pw in pathways:
                all_pathways.add(pw)

            for rel in relations:
                node_groups, connectors = _parse_kegg_relations(rel)
                # Build nodes with pathways
                for group in node_groups:
                    for node_name in group:
                        if not node_name:
                            continue
                        if node_name not in nodes:
                            nodes[node_name] = {
                                'id': node_name,
                                'pathways': set()
                            }
                        nodes[node_name]['pathways'].update(pathways)

                # Build edges for adjacent groups (cartesian product)
                for gi in range(len(node_groups) - 1):
                    src_group = node_groups[gi]
                    tgt_group = node_groups[gi + 1]
                    conn = connectors[gi] if gi < len(connectors) else '->'
                    e_type = 'inhibition' if conn == '-|' else 'activation'
                    for s in src_group:
                        for t in tgt_group:
                            if not s or not t:
                                continue
                            ekey = (s, t)
                            if ekey not in edges:
                                edges[ekey] = {
                                    'source': s,
                                    'target': t,
                                    'type': e_type,
                                    'pathways': set(),
                                    'keys': set(),
                                }
                            edges[ekey]['pathways'].update(pathways)
                            edges[ekey]['keys'].add(key)

        # Convert sets to lists for JSON
        nodes_list = []
        for n in nodes.values():
            n['pathways'] = sorted(list(n['pathways']))
            nodes_list.append(n)

        links_list = []
        for e in edges.values():
            e['pathways'] = sorted(list(e['pathways']))
            e['keys'] = sorted(list(e['keys']))
            links_list.append(e)

        result = {
            'nodes': nodes_list,
            'links': links_list,
            'pathways': sorted(list(all_pathways))
        }
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/search', methods=['POST'])
def search():
    """Semantic search endpoint."""
    if not rag_system:
        return jsonify({'error': 'RAG system not loaded'}), 400
    
    data = request.json
    query = data.get('query', '')
    top_k = data.get('top_k', 5)
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    try:
        results = rag_system.search(query, top_k=top_k)
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search-summary', methods=['POST'])
def search_summary():
    """LLM-generated summary over papers for a given query.

    Body JSON: { query: str, top_k: int }
    Returns: { summary: str, total: int }
    """
    if not rag_system:
        return jsonify({'error': 'RAG system not loaded'}), 400

    data = request.json or {}
    query = data.get('query', '').strip()
    top_k = int(data.get('top_k', 8))
    if not query:
        return jsonify({'error': 'Query is required'}), 400

    try:
        results = rag_system.search(query, top_k=top_k)
        total = len(results)

        # Build a concise multi-paper prompt
        context_lines = [f"Query: {query}", f"Papers ({min(total, 8)} shown):"]
        for i, r in enumerate(results[:8], 1):
            title = r.get('title', '')
            abstract = r.get('abstract', '')
            context_lines.append(f"{i}. {title}\n   {abstract[:220]}...")
        context = "\n".join(context_lines)

        prompt = (
            f"{context}\n\n"
            "Summarize the main themes and findings across these papers in 3-5 concise sentences. "
            "Highlight key mechanisms, entities, and any clinical significance."
        )

        summary = None
        if llm_summarizer and llm_summarizer.backend:
            try:
                summary = llm_summarizer.generate_summary(prompt, max_tokens=260)
            except Exception as e:
                print(f"LLM search summary error: {e}")

        if not summary:
            # Fallback simple summary
            titles = "; ".join([r.get('title', '') for r in results[:5]])
            summary = (
                f"Found {total} papers related to '{query}'. Representative works include: {titles}. "
                "Themes involve mechanisms and relationships among key entities reported in the literature."
            )

        return jsonify({'summary': summary, 'total': total})
    except Exception as e:
        print("Error generating search summary", e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/entity/<entity_name>')
def get_entity(entity_name):
    """Get entity information."""
    if not knowledge_graph:
        return jsonify({'error': 'Knowledge Graph not loaded'}), 400
    
    try:
        entity_info = knowledge_graph.query_entity(entity_name)
        
        if 'error' in entity_info:
            return jsonify(entity_info), 404
        
        # Convert sets to lists for JSON serialization
        if isinstance(entity_info.get('papers'), set):
            entity_info['papers'] = list(entity_info['papers'])
        
        # Ensure all fields exist
        entity_info.setdefault('type', 'UNKNOWN')
        entity_info.setdefault('frequency', 0)
        entity_info.setdefault('papers', [])
        entity_info.setdefault('sections', {})
        entity_info.setdefault('outgoing_relationships', [])
        entity_info.setdefault('incoming_relationships', [])
        entity_info.setdefault('total_relationships', 0)
        
        return jsonify(entity_info)
    except Exception as e:
        print(f"Error querying entity '{entity_name}': {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/subgraph/<entity_name>')
def get_subgraph(entity_name):
    """Get subgraph around an entity."""
    if not knowledge_graph:
        return jsonify({'error': 'Knowledge Graph not loaded'}), 400
    
    depth = request.args.get('depth', 2, type=int)
    
    try:
        subgraph = knowledge_graph.get_subgraph(entity_name, depth=depth)
        
        if subgraph.number_of_nodes() == 0:
            return jsonify({'error': f'Entity "{entity_name}" not found'}), 404
        
        # Convert to JSON format
        data = json_graph.node_link_data(subgraph)
        
        # Add node attributes
        for node_data in data['nodes']:
            node_id = node_data['id']
            if node_id in subgraph.nodes:
                node_attrs = subgraph.nodes[node_id]
                node_data['entity_type'] = node_attrs.get('entity_type', 'UNKNOWN')
                node_data['frequency'] = node_attrs.get('frequency', 1)
                papers = node_attrs.get('papers', set())
                if isinstance(papers, set):
                    papers = list(papers)
                node_data['papers'] = papers[:5]  # Limit for size
                # include sources and domains for front-end shape mapping
                node_data['sources'] = list(node_attrs.get('sources', set()))
                node_data['domains'] = list(node_attrs.get('domains', set()))
        
        # Add edge attributes
        for link in data['links']:
            try:
                source_id = data['nodes'][link['source']]['id']
                target_id = data['nodes'][link['target']]['id']
                edge_data = subgraph.get_edge_data(source_id, target_id)
                
                if edge_data:
                    # Get first edge data (MultiDiGraph can have multiple edges)
                    first_edge = list(edge_data.values())[0] if edge_data else {}
                    link['relation'] = first_edge.get('relation', 'RELATED')
                    link['paper'] = first_edge.get('paper', '')[:50]
                else:
                    link['relation'] = 'RELATED'
                    link['paper'] = ''
            except (KeyError, IndexError, TypeError) as e:
                print(f"Warning: Error processing edge: {e}")
                link['relation'] = 'RELATED'
                link['paper'] = ''
        
        return jsonify(data)
    except Exception as e:
        print(f"Error getting subgraph for '{entity_name}': {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/find-path', methods=['POST'])
def find_path():
    """Find path between two entities."""
    if not knowledge_graph:
        return jsonify({'error': 'Knowledge Graph not loaded'}), 400
    
    data = request.json
    entity1 = data.get('entity1', '')
    entity2 = data.get('entity2', '')
    max_length = data.get('max_length', 4)
    
    if not entity1 or not entity2:
        return jsonify({'error': 'Both entities are required'}), 400
    
    try:
        paths = knowledge_graph.find_path(entity1, entity2, max_length=max_length)
        return jsonify({'paths': paths})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/entity-types')
def get_entity_types():
    """Get entity type distribution."""
    if not knowledge_graph:
        return jsonify({'error': 'Knowledge Graph not loaded'}), 400
    
    entity_types = {etype: len(entities) 
                   for etype, entities in knowledge_graph.entity_types.items()}
    
    return jsonify(entity_types)

@app.route('/api/analytics/relationships')
def get_relationships():
    """Get relationship type distribution."""
    if not knowledge_graph:
        return jsonify({'error': 'Knowledge Graph not loaded'}), 400
    
    relation_counts = {}
    for _, _, data in knowledge_graph.graph.edges(data=True):
        rel = data['relation']
        relation_counts[rel] = relation_counts.get(rel, 0) + 1
    
    # Sort by count
    sorted_relations = sorted(relation_counts.items(), key=lambda x: x[1], reverse=True)
    
    return jsonify(dict(sorted_relations[:20]))

@app.route('/api/analytics/top-entities')
def get_top_entities():
    """Get most connected entities."""
    if not knowledge_graph:
        return jsonify({'error': 'Knowledge Graph not loaded'}), 400
    
    entities = []
    for node in knowledge_graph.graph.nodes():
        in_degree = knowledge_graph.graph.in_degree(node)
        out_degree = knowledge_graph.graph.out_degree(node)
        total = in_degree + out_degree
        
        entities.append({
            'entity': node,
            'total': total,
            'incoming': in_degree,
            'outgoing': out_degree
        })
    
    entities.sort(key=lambda x: x['total'], reverse=True)
    
    return jsonify(entities[:30])

@app.route('/api/tooltip/entity/<entity_name>')
def get_entity_tooltip(entity_name):
    """Generate tooltip content for a keyword/entity using RAG (and KG if available).

    Works even if the entity is not present in the Knowledge Graph by
    summarizing top related papers from the RAG collection.
    """
    if not rag_system and not knowledge_graph:
        return jsonify({'error': 'No systems loaded'}), 400

    try:
        # Optional KG lookup
        entity_info = {
            'type': 'Unknown',
            'frequency': 0,
            'papers': []
        }
        if knowledge_graph:
            try:
                q = knowledge_graph.query_entity(entity_name)
                if 'error' not in q:
                    entity_info.update({
                        'type': q.get('type', 'Unknown'),
                        'frequency': q.get('frequency', 0),
                        'papers': q.get('papers', [])
                    })
            except Exception as e:
                # Non-fatal if entity not in KG
                pass

        # RAG search to gather related papers
        papers = []
        if rag_system:
            try:
                papers = rag_system.search(entity_name, top_k=5)
            except Exception as e:
                print(f"RAG search error in tooltip: {e}")

        # Build LLM prompt from RAG results if LLM available
        summary = None
        if llm_summarizer and llm_summarizer.backend and papers:
            try:
                context_lines = [f"Keyword: {entity_name}", "Related Papers:"]
                for i, p in enumerate(papers[:5], 1):
                    context_lines.append(f"{i}. {p.get('title','')}")
                    if p.get('abstract'):
                        context_lines.append(f"   {p['abstract'][:220]}...")
                prompt = "\n".join(context_lines) + "\n\nSummarize how this keyword appears across these papers in 2-3 sentences. Focus on mechanisms and relevance."
                summary = llm_summarizer.generate_summary(prompt, max_tokens=180)
            except Exception as e:
                print(f"LLM error: {e}")

        # Fallback summary
        if not summary:
            if papers:
                p0 = papers[0]
                summary = f"Found {len(papers)} related papers for '{entity_name}'. Example: {p0.get('title','')[:80]}..."
            else:
                summary = f"'{entity_name}' appears {entity_info.get('frequency', 0)} times in the knowledge graph."

        return jsonify({
            'entity': entity_name,
            'type': entity_info.get('type', 'Unknown'),
            'frequency': entity_info.get('frequency', 0),
            'summary': summary,
            'papers': [p.get('title','') for p in papers[:3]],
            'total_papers': len(entity_info.get('papers', []))
        })

    except Exception as e:
        print(f"Error generating tooltip: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/tooltip/relationship', methods=['POST'])
def get_relationship_tooltip():
    """Generate intelligent tooltip for a relationship using LLM + RAG."""
    if not knowledge_graph or not rag_system:
        return jsonify({'error': 'Systems not loaded'}), 400
    
    data = request.json
    source = data.get('source', '')
    target = data.get('target', '')
    relation = data.get('relation', 'RELATED')
    
    if not source or not target:
        return jsonify({'error': 'Source and target required'}), 400
    
    try:
        # Search for papers mentioning both entities
        query = f"{source} {target}"
        papers = []
        
        if rag_system:
            try:
                search_results = rag_system.search(query, top_k=3)
                papers = search_results
            except:
                pass
        
        # Generate summary using LLM
        summary = None
        if llm_summarizer and llm_summarizer.backend:
            try:
                summary = llm_summarizer.summarize_relationship(source, relation, target, papers)
            except Exception as e:
                print(f"LLM error: {e}")
        
        # Fallback
        if not summary:
            relation_text = relation.lower().replace('_', ' ')
            summary = f"Research shows that {source} {relation_text} {target}."
            if papers:
                summary += f" This relationship is discussed in: {papers[0]['title'][:80]}..."
        
        return jsonify({
            'source': source,
            'target': target,
            'relation': relation,
            'summary': summary,
            'supporting_papers': [p['title'] for p in papers[:2]]
        })
        
    except Exception as e:
        print(f"Error generating relationship tooltip: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/build', methods=['POST'])
def build_system():
    """Build new system from uploaded CSV."""
    global rag_system, knowledge_graph
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
    
    try:
        # Save uploaded file
        csv_path = 'temp_papers.csv'
        file.save(csv_path)
        
        # Build RAG system
        rag_system = MedicalRAGVectorStore(persist_directory=RAG_DIR)
        documents = rag_system.process_csv_to_documents(csv_path)
        rag_system.create_vector_store(documents, COLLECTION_NAME)
        
        # Build Knowledge Graph
        knowledge_graph = MedicalKnowledgeGraph()
        knowledge_graph.build_from_csv(csv_path)
        knowledge_graph.save_graph(KG_FILE)
        
        # Clean up
        os.remove(csv_path)
        
        return jsonify({
            'success': True,
            'message': 'System built successfully',
            'stats': {
                'documents': len(documents),
                'entities': knowledge_graph.graph.number_of_nodes(),
                'relationships': knowledge_graph.graph.number_of_edges()
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/uniprot/ingest', methods=['POST'])
def ingest_uniprot():
    """Ingest UniProt EGFR (or custom) into vector store and KG.

    Body JSON (optional): {"query":"Egfr", "organism":"human"}
    """
    try:
        data = request.json or {}
        query = data.get('query', 'Egfr')
        organism = data.get('organism', 'human')

        # Ensure RAG/KG structures exist
        persist_dir = RAG_DIR
        collection = COLLECTION_NAME

        # Store top UniProt result into vector store
        harvester = UniProtHarvester(persist_directory=persist_dir, collection_name=collection)
        store_summary = harvester.store_top_egfr_in_vectorstore() if (query.lower()=="egfr" and organism.lower()=="human") else None

        # Always gather info so we can add interactions into KG
        info = harvester.gather_egfr_human() if (query.lower()=="egfr" and organism.lower()=="human") else harvester.gather_egfr_human()

        # Initialize KG if needed
        global knowledge_graph
        if not knowledge_graph:
            knowledge_graph = MedicalKnowledgeGraph()
            # If an existing KG file is present, load it to append
            if os.path.exists(KG_FILE):
                try:
                    knowledge_graph.load_graph(KG_FILE)
                except Exception:
                    pass

        # Align KG patterns with RAG, if available
        try:
            patterns = MedicalRAGVectorStore.define_relationship_patterns()
            knowledge_graph.set_relationship_patterns(patterns)
        except Exception:
            pass

        # Add UniProt interactions
        added = knowledge_graph.add_uniprot_interactions(info)

        # Save/Export KG
        knowledge_graph.save_graph(KG_FILE)
        knowledge_graph.export_to_json('medical_knowledge_graph.json')

        # Optionally refresh RAG system collection handle
        global rag_system
        if rag_system:
            try:
                rag_system.load_collection(collection)
            except Exception:
                pass

        return jsonify({
            'success': True,
            'stored_to_vectorstore': bool(store_summary and store_summary.get('stored')),
            'vectorstore_summary': store_summary,
            'uniprot_accession': info.get('accession'),
            'uniprot_gene': info.get('gene_name'),
            'uniprot_protein': info.get('protein_name'),
            'interactions_added': added,
            'kg_entities': knowledge_graph.graph.number_of_nodes(),
            'kg_relationships': knowledge_graph.graph.number_of_edges(),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # Initialize systems
    initialize_systems()
    
    # Run app
    print("\n" + "="*70)
    print("🧬 Medical Papers Knowledge System")
    print("="*70)
    print("\n📍 Server starting at: http://localhost:5000")
    print("\n Press Ctrl+C to stop\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
