"""
Test and Build Script for Medical Papers System
This script helps you build and verify the RAG and KG systems.

Usage:
    python test_system.py build papers.csv      # Build from CSV
    python test_system.py test                  # Test existing system
    python test_system.py status                # Check status
"""

import sys
import os
from pathlib import Path

def check_files():
    """Check if required files exist."""
    print("\n" + "="*70)
    print("📋 Checking System Files")
    print("="*70)
    
    files_to_check = {
        'src/rag.py': 'RAG system module',
        'src/knowledgegraph.py': 'Knowledge Graph module',
        'src/app.py': 'Flask application',
        'src/templates/index.html': 'Web interface'
    }
    
    all_exist = True
    for file, desc in files_to_check.items():
        if os.path.exists(file):
            print(f"✓ {desc}: {file}")
        else:
            print(f"✗ {desc}: {file} - NOT FOUND")
            all_exist = False
    
    return all_exist

def check_dependencies():
    """Check if required packages are installed."""
    print("\n" + "="*70)
    print("📦 Checking Dependencies")
    print("="*70)
    
    required = [
        'flask', 'pandas', 'chromadb', 'sentence_transformers',
        'networkx', 'spacy', 'yake', 'sklearn', 'bs4', 'requests'
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} - NOT INSTALLED")
            missing.append(package)
    
    if missing:
        print("\n⚠ Install missing packages:")
        print(f"pip install {' '.join(missing)}")
        return False
    
    return True

def check_spacy_model():
    """Check if spaCy model is installed."""
    print("\n" + "="*70)
    print("🔤 Checking spaCy Models")
    print("="*70)
    
    try:
        import spacy
        try:
            nlp = spacy.load("en_core_sci_sm")
            print("✓ Biomedical model: en_core_sci_sm (recommended)")
            return True
        except:
            try:
                nlp = spacy.load("en_core_web_sm")
                print("✓ Standard model: en_core_web_sm")
                print("ℹ Consider installing biomedical model for better results:")
                print("  pip install scispacy")
                print("  pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.1/en_core_sci_sm-0.5.1.tar.gz")
                return True
            except:
                print("✗ No spaCy model found")
                print("Install with: python -m spacy download en_core_web_sm")
                return False
    except ImportError:
        print("✗ spaCy not installed")
        return False

def check_status():
    """Check status of existing system."""
    print("\n" + "="*70)
    print("📊 System Status")
    print("="*70)
    
    # Check RAG
    rag_dir = './medical_chroma_db'
    if os.path.exists(rag_dir):
        print(f"✓ RAG database found: {rag_dir}")
        try:
            from rag import MedicalRAGVectorStore
            rag = MedicalRAGVectorStore(persist_directory=rag_dir)
            success = rag.load_collection('medical_papers')
            if success:
                stats = rag.get_collection_stats()
                print(f"  - Collection: {stats['collection_name']}")
                print(f"  - Documents: {stats['document_count']}")
            else:
                print("  ✗ Could not load collection")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    else:
        print(f"✗ RAG database not found: {rag_dir}")
    
    # Check KG
    kg_file = 'medical_knowledge_graph.pkl'
    if os.path.exists(kg_file):
        print(f"✓ Knowledge Graph found: {kg_file}")
        try:
            from knowledgegraph import MedicalKnowledgeGraph
            kg = MedicalKnowledgeGraph()
            kg.load_graph(kg_file)
            print(f"  - Entities: {kg.graph.number_of_nodes()}")
            print(f"  - Relationships: {kg.graph.number_of_edges()}")
            print(f"  - Papers: {len(kg.paper_entities)}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    else:
        print(f"✗ Knowledge Graph not found: {kg_file}")

def build_system(csv_file):
    """Build RAG and KG systems from CSV."""
    if not os.path.exists(csv_file):
        print(f"✗ CSV file not found: {csv_file}")
        return False
    
    print("\n" + "="*70)
    print(f"🔨 Building System from {csv_file}")
    print("="*70)
    
    try:
        # Build RAG
        print("\n1️⃣ Building RAG System...")
        print("-" * 70)
        from rag import MedicalRAGVectorStore
        
        rag = MedicalRAGVectorStore(persist_directory='./medical_chroma_db')
        documents = rag.process_csv_to_documents(csv_file)
        rag.create_vector_store(documents, 'medical_papers')
        
        print("\n✅ RAG system built successfully!")
        
        # Build KG
        print("\n2️⃣ Building Knowledge Graph...")
        print("-" * 70)
        from knowledgegraph import MedicalKnowledgeGraph
        
        kg = MedicalKnowledgeGraph()
        kg.build_from_csv(csv_file)
        kg.save_graph('medical_knowledge_graph.pkl')
        kg.export_to_json('medical_knowledge_graph.json')
        
        print("\n✅ Knowledge Graph built successfully!")
        
        # Test the systems
        print("\n3️⃣ Testing Systems...")
        print("-" * 70)
        
        # Test RAG search
        print("\nTesting RAG search...")
        results = rag.search("oxidative stress", top_k=2)
        print(f"✓ Found {len(results)} results")
        if results:
            print(f"  Top result: {results[0]['title'][:60]}...")
        
        # Test KG query
        print("\nTesting Knowledge Graph...")
        test_entities = list(kg.graph.nodes())[:3]
        print(f"✓ Sample entities: {', '.join(test_entities)}")
        
        print("\n" + "="*70)
        print("✅ System Build Complete!")
        print("="*70)
        print("\nYou can now run: python app.py")
        print("Then open: http://localhost:5000")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error building system: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_system():
    """Test existing system."""
    print("\n" + "="*70)
    print("🧪 Testing System")
    print("="*70)
    
    try:
        # Test RAG
        print("\n1️⃣ Testing RAG System...")
        from rag import MedicalRAGVectorStore
        
        rag = MedicalRAGVectorStore(persist_directory='./medical_chroma_db')
        if rag.load_collection('medical_papers'):
            results = rag.search("test query", top_k=1)
            print(f"✓ RAG search working - found {len(results)} result(s)")
        else:
            print("✗ RAG collection not loaded")
            return False
        
        # Test KG
        print("\n2️⃣ Testing Knowledge Graph...")
        from knowledgegraph import MedicalKnowledgeGraph
        
        kg = MedicalKnowledgeGraph()
        kg.load_graph('medical_knowledge_graph.pkl')
        print(f"✓ KG loaded - {kg.graph.number_of_nodes()} entities")
        
        # Test entity query
        test_entity = list(kg.graph.nodes())[0]
        info = kg.query_entity(test_entity)
        if 'error' not in info:
            print(f"✓ Entity query working - tested '{test_entity}'")
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function."""
    print("\n🧬 Medical Papers Knowledge System - Test & Build")
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python test_system.py status              # Check system status")
        print("  python test_system.py build papers.csv    # Build from CSV")
        print("  python test_system.py test                # Test existing system")
        print("  python test_system.py check               # Check dependencies")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'check':
        check_files()
        check_dependencies()
        check_spacy_model()
        
    elif command == 'status':
        if not check_files():
            return
        check_status()
        
    elif command == 'build':
        if len(sys.argv) < 3:
            print("Error: Please provide CSV file")
            print("Usage: python test_system.py build papers.csv")
            return
        
        csv_file = sys.argv[2]
        
        # Run checks first
        if not check_files():
            print("\n⚠ Some files are missing. Please check.")
            return
        
        if not check_dependencies():
            print("\n⚠ Please install missing dependencies first.")
            return
        
        check_spacy_model()
        
        # Build
        build_system(csv_file)
        
    elif command == 'test':
        if not check_files():
            return
        test_system()
        
    else:
        print(f"Unknown command: {command}")
        print("Available commands: check, status, build, test")

if __name__ == "__main__":
    main()