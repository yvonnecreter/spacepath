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
except ImportError:
    print("⚠️ Please ensure rag.py and knowledgegraph.py are in the same directory")
    exit(1)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Global variables
rag_system = None
knowledge_graph = None

# Configuration
RAG_DIR = './medical_chroma_db'
COLLECTION_NAME = 'medical_papers'
KG_FILE = 'medical_knowledge_graph.pkl'

def initialize_systems():
    """Initialize RAG and KG systems if files exist."""
    global rag_system, knowledge_graph
    
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

@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')

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