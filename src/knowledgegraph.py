import pandas as pd
import requests
from bs4 import BeautifulSoup
import spacy
import networkx as nx
import json
import re
from typing import List, Dict, Tuple, Set
from collections import defaultdict, Counter
import matplotlib.pyplot as plt
from tqdm import tqdm
import pickle
import time

class MedicalKnowledgeGraph:
    """
    Build a knowledge graph from medical paper abstracts and results sections.
    Extracts entities (diseases, proteins, chemicals, etc.) and their relationships.
    """
    
    def __init__(self):
        """Initialize the knowledge graph builder."""
        self.graph = nx.MultiDiGraph()  # Directed graph with multiple edges
        self.entity_types = defaultdict(set)
        self.paper_entities = {}  # Maps paper titles to their entities
        self.relationship_counts = Counter()
        
        # Load spaCy model
        try:
            self.nlp = spacy.load("en_core_sci_sm")
            print("✓ Loaded scispacy biomedical model")
        except:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                print("✓ Loaded standard spacy model (install scispacy for better results)")
            except:
                raise Exception("Please install spacy: pip install spacy && python -m spacy download en_core_web_sm")
        
        # Relationship patterns for medical texts
        self.relationship_patterns = self._define_relationship_patterns()
        
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
        """Fetch and extract abstract and results sections."""
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
                'methods': '',
                'discussion': ''
            }
            
            # Extract abstract
            abstract_section = soup.find(['div', 'section', 'p'], 
                                        class_=re.compile(r'abstract', re.I))
            if not abstract_section:
                abstract_section = soup.find(['div', 'section'], 
                                            id=re.compile(r'abstract', re.I))
            if abstract_section:
                content['abstract'] = abstract_section.get_text(strip=True, separator=' ')
            
            # Extract results
            results_section = soup.find(['div', 'section'], 
                                       class_=re.compile(r'results?', re.I))
            if not results_section:
                results_section = soup.find(['div', 'section'], 
                                          id=re.compile(r'results?', re.I))
            if results_section:
                content['results'] = results_section.get_text(strip=True, separator=' ')
            
            # Extract methods (optional but helpful)
            methods_section = soup.find(['div', 'section'], 
                                       class_=re.compile(r'method', re.I))
            if methods_section:
                content['methods'] = methods_section.get_text(strip=True, separator=' ')
            
            # Extract discussion (optional)
            discussion_section = soup.find(['div', 'section'], 
                                          class_=re.compile(r'discussion', re.I))
            if discussion_section:
                content['discussion'] = discussion_section.get_text(strip=True, separator=' ')
            
            # Clean up
            for key in content:
                content[key] = re.sub(r'\s+', ' ', content[key]).strip()
            
            return content
            
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return {'abstract': '', 'results': '', 'methods': '', 'discussion': ''}
    
    def extract_entities(self, text: str, section_type: str = 'abstract') -> List[Dict]:
        """
        Extract biomedical entities using spaCy NER.
        
        Returns:
            List of entity dictionaries with text, label, and context
        """
        if not text:
            return []
        
        doc = self.nlp(text[:100000])  # Limit length
        
        entities = []
        for ent in doc.ents:
            # Filter out very short or very long entities
            if len(ent.text) < 3 or len(ent.text) > 100:
                continue
            
            # Clean entity text
            entity_text = ent.text.strip()
            entity_text = re.sub(r'\s+', ' ', entity_text)
            
            entities.append({
                'text': entity_text,
                'label': ent.label_,
                'start': ent.start_char,
                'end': ent.end_char,
                'section': section_type
            })
        
        return entities
    
    def extract_relationships(self, text: str, entities: List[Dict]) -> List[Dict]:
        """
        Extract relationships between entities using dependency parsing
        and pattern matching.
        
        Returns:
            List of relationship tuples (entity1, relation, entity2)
        """
        if not text or len(entities) < 2:
            return []
        
        doc = self.nlp(text[:100000])
        relationships = []
        
        # Create entity position map
        entity_map = {}
        for ent_dict in entities:
            for token in doc:
                if (token.idx >= ent_dict['start'] and 
                    token.idx < ent_dict['end']):
                    entity_map[token.i] = ent_dict['text']
        
        # Extract relationships using dependency parsing
        for token in doc:
            # Check if token is a verb that indicates a relationship
            if token.pos_ == 'VERB':
                verb_lemma = token.lemma_.lower()
                
                # Find matching relationship type
                relation_type = None
                for pattern in self.relationship_patterns:
                    if verb_lemma in [v.lower() for v in pattern['verbs']]:
                        relation_type = pattern['relation']
                        break
                
                if relation_type:
                    # Find subject and object entities
                    subject_entities = []
                    object_entities = []
                    
                    for child in token.children:
                        if child.dep_ in ['nsubj', 'nsubjpass']:
                            # Subject entity
                            for desc in child.subtree:
                                if desc.i in entity_map:
                                    subject_entities.append(entity_map[desc.i])
                        
                        elif child.dep_ in ['dobj', 'pobj', 'attr']:
                            # Object entity
                            for desc in child.subtree:
                                if desc.i in entity_map:
                                    object_entities.append(entity_map[desc.i])
                    
                    # Create relationships
                    for subj in subject_entities:
                        for obj in object_entities:
                            if subj != obj:
                                relationships.append({
                                    'source': subj,
                                    'target': obj,
                                    'relation': relation_type,
                                    'verb': token.text,
                                    'context': text[max(0, token.idx-50):token.idx+50]
                                })
        
        # Also extract co-occurrence relationships (entities in same sentence)
        for sent in doc.sents:
            sent_entities = []
            for ent_dict in entities:
                if (ent_dict['start'] >= sent.start_char and 
                    ent_dict['end'] <= sent.end_char):
                    sent_entities.append(ent_dict['text'])
            
            # Create co-occurrence relationships
            if len(sent_entities) >= 2:
                for i, ent1 in enumerate(sent_entities):
                    for ent2 in sent_entities[i+1:]:
                        if ent1 != ent2:
                            relationships.append({
                                'source': ent1,
                                'target': ent2,
                                'relation': 'CO_OCCURS_WITH',
                                'verb': None,
                                'context': sent.text[:100]
                            })
        
        return relationships
    
    def add_entity_to_graph(self, entity: str, entity_type: str, 
                           paper_title: str, section: str):
        """Add an entity node to the graph."""
        # Normalize entity name
        entity = entity.strip().lower()
        
        # Add or update node
        if entity not in self.graph:
            self.graph.add_node(entity, 
                               entity_type=entity_type,
                               papers=set(),
                               sections=defaultdict(int),
                               frequency=0)
        
        # Update node attributes
        self.graph.nodes[entity]['papers'].add(paper_title)
        self.graph.nodes[entity]['sections'][section] += 1
        self.graph.nodes[entity]['frequency'] += 1
        self.entity_types[entity_type].add(entity)
    
    def add_relationship_to_graph(self, source: str, target: str, 
                                 relation: str, paper_title: str,
                                 context: str = '', verb: str = ''):
        """Add a relationship edge to the graph."""
        source = source.strip().lower()
        target = target.strip().lower()
        
        # Add edge
        self.graph.add_edge(source, target,
                           relation=relation,
                           paper=paper_title,
                           context=context[:200],
                           verb=verb)
        
        # Count relationship
        self.relationship_counts[(source, relation, target)] += 1
    
    def process_paper(self, title: str, content: Dict[str, str]):
        """Process a single paper and extract entities and relationships."""
        print(f"\nProcessing: {title[:70]}...")
        
        paper_entities = []
        
        # Process abstract and results (primary focus)
        for section_name in ['abstract', 'results']:
            section_text = content.get(section_name, '')
            if not section_text:
                continue
            
            print(f"  Extracting from {section_name}...")
            
            # Extract entities
            entities = self.extract_entities(section_text, section_name)
            print(f"    Found {len(entities)} entities")
            
            # Add entities to graph
            for ent in entities:
                self.add_entity_to_graph(
                    ent['text'], 
                    ent['label'],
                    title,
                    section_name
                )
                paper_entities.append(ent)
            
            # Extract relationships
            relationships = self.extract_relationships(section_text, entities)
            print(f"    Found {len(relationships)} relationships")
            
            # Add relationships to graph
            for rel in relationships:
                self.add_relationship_to_graph(
                    rel['source'],
                    rel['target'],
                    rel['relation'],
                    title,
                    rel.get('context', ''),
                    rel.get('verb', '')
                )
        
        # Store paper entities
        self.paper_entities[title] = paper_entities
        
        return len(paper_entities)
    
    def build_from_csv(self, csv_path: str):
        """Build knowledge graph from CSV of papers."""
        df = self.load_csv(csv_path)
        
        print(f"\n{'='*70}")
        print(f"Building Knowledge Graph from {len(df)} papers")
        print(f"{'='*70}")
        
        for idx, row in df.iterrows():
            title = row['title']
            link = row['link']
            
            print(f"\n[{idx+1}/{len(df)}]", end=' ')
            
            # Fetch content
            content = self.fetch_paper_content(link)
            
            if not content['abstract'] and not content['results']:
                print(f"  ⚠ No abstract or results found, skipping")
                continue
            
            # Process paper
            self.process_paper(title, content)
            
            # Be respectful with requests
            time.sleep(1)
        
        print(f"\n{'='*70}")
        print("Knowledge Graph Construction Complete!")
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
                                     reverse=True):
            print(f"    {etype}: {len(entities)}")
        
        print(f"\n  Top 10 Relationship Types:")
        relation_counts = Counter()
        for _, _, data in self.graph.edges(data=True):
            relation_counts[data['relation']] += 1
        
        for rel, count in relation_counts.most_common(10):
            print(f"    {rel}: {count}")
        
        print(f"\n  Top 10 Most Frequent Entities:")
        entity_freqs = [(node, data['frequency']) 
                       for node, data in self.graph.nodes(data=True)]
        entity_freqs.sort(key=lambda x: x[1], reverse=True)
        
        for entity, freq in entity_freqs[:10]:
            print(f"    {entity}: {freq}")
    
    def query_entity(self, entity_name: str) -> Dict:
        """Query information about a specific entity."""
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
            'outgoing_relationships': outgoing[:10],
            'incoming_relationships': incoming[:10],
            'total_relationships': len(outgoing) + len(incoming)
        }
    
    def find_path(self, entity1: str, entity2: str, max_length: int = 4) -> List:
        """Find connection path between two entities."""
        entity1 = entity1.strip().lower()
        entity2 = entity2.strip().lower()
        
        if entity1 not in self.graph or entity2 not in self.graph:
            return []
        
        try:
            paths = list(nx.all_simple_paths(self.graph, entity1, entity2, 
                                            cutoff=max_length))
            return paths[:5]  # Return up to 5 paths
        except nx.NetworkXNoPath:
            return []
    
    def get_subgraph(self, entity: str, depth: int = 1) -> nx.MultiDiGraph:
        """Get subgraph around a specific entity."""
        entity = entity.strip().lower()
        
        if entity not in self.graph:
            return nx.MultiDiGraph()
        
        # Get neighbors up to specified depth
        nodes = {entity}
        current_layer = {entity}
        
        for _ in range(depth):
            next_layer = set()
            for node in current_layer:
                next_layer.update(self.graph.successors(node))
                next_layer.update(self.graph.predecessors(node))
            nodes.update(next_layer)
            current_layer = next_layer
        
        return self.graph.subgraph(nodes).copy()
    
    def save_graph(self, filename: str = 'knowledge_graph.pkl'):
        """Save the knowledge graph to file."""
        data = {
            'graph': self.graph,
            'entity_types': dict(self.entity_types),
            'paper_entities': self.paper_entities,
            'relationship_counts': dict(self.relationship_counts)
        }
        
        with open(filename, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"✓ Knowledge graph saved to {filename}")
    
    def load_graph(self, filename: str = 'knowledge_graph.pkl'):
        """Load knowledge graph from file."""
        with open(filename, 'rb') as f:
            data = pickle.load(f)
        
        self.graph = data['graph']
        self.entity_types = defaultdict(set, data['entity_types'])
        self.paper_entities = data['paper_entities']
        self.relationship_counts = Counter(data['relationship_counts'])
        
        print(f"✓ Knowledge graph loaded from {filename}")
        self.print_statistics()
    
    def export_to_json(self, filename: str = 'knowledge_graph.json'):
        """Export graph to JSON format."""
        # Convert graph to JSON-serializable format
        nodes_data = []
        for node, data in self.graph.nodes(data=True):
            nodes_data.append({
                'id': node,
                'type': data['entity_type'],
                'frequency': data['frequency'],
                'papers': list(data['papers']),
                'sections': dict(data['sections'])
            })
        
        edges_data = []
        for source, target, data in self.graph.edges(data=True):
            edges_data.append({
                'source': source,
                'target': target,
                'relation': data['relation'],
                'paper': data['paper'],
                'context': data.get('context', '')
            })
        
        graph_data = {
            'nodes': nodes_data,
            'edges': edges_data,
            'statistics': {
                'num_nodes': len(nodes_data),
                'num_edges': len(edges_data),
                'num_papers': len(self.paper_entities)
            }
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Knowledge graph exported to {filename}")
    
    def visualize_subgraph(self, entity: str, depth: int = 1, 
                          filename: str = 'subgraph.png'):
        """Visualize a subgraph around an entity."""
        subgraph = self.get_subgraph(entity, depth)
        
        if subgraph.number_of_nodes() == 0:
            print(f"Entity '{entity}' not found")
            return
        
        plt.figure(figsize=(15, 10))
        
        # Layout
        pos = nx.spring_layout(subgraph, k=2, iterations=50)
        
        # Draw nodes
        nx.draw_networkx_nodes(subgraph, pos, 
                              node_color='lightblue',
                              node_size=1000,
                              alpha=0.7)
        
        # Draw edges with labels
        nx.draw_networkx_edges(subgraph, pos,
                              edge_color='gray',
                              arrows=True,
                              arrowsize=20,
                              alpha=0.5)
        
        # Draw labels
        nx.draw_networkx_labels(subgraph, pos, 
                               font_size=8,
                               font_weight='bold')
        
        # Draw edge labels (relations)
        edge_labels = {}
        for source, target, data in subgraph.edges(data=True):
            if (source, target) not in edge_labels:
                edge_labels[(source, target)] = data['relation']
        
        nx.draw_networkx_edge_labels(subgraph, pos, edge_labels,
                                     font_size=6)
        
        plt.title(f"Knowledge Graph around '{entity}' (depth={depth})")
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"✓ Visualization saved to {filename}")
        plt.close()


# Example usage
if __name__ == "__main__":
    # Initialize knowledge graph
    kg = MedicalKnowledgeGraph()
    
    # Build from CSV
    kg.build_from_csv('SB_publications/SB_publication_PMC.csv')
    
    # Save the graph
    kg.save_graph('medical_knowledge_graph.pkl')
    
    # Export to JSON
    kg.export_to_json('medical_knowledge_graph.json')
    
    # Example queries
    print("\n" + "="*70)
    print("Example Queries:")
    print("="*70)
    
    # Query specific entity
    print("\n1. Querying 'oxidative stress':")
    result = kg.query_entity('oxidative stress')
    if 'error' not in result:
        print(f"   Type: {result['type']}")
        print(f"   Frequency: {result['frequency']}")
        print(f"   Appears in {len(result['papers'])} papers")
        print(f"   Top relationships:")
        for target, relation in result['outgoing_relationships'][:5]:
            print(f"     - {relation} -> {target}")
    
    # Find paths between entities
    print("\n2. Finding path between entities:")
    paths = kg.find_path('nadph oxidase', 'cell death')
    if paths:
        print(f"   Found {len(paths)} paths:")
        for i, path in enumerate(paths[:3], 1):
            print(f"   Path {i}: {' -> '.join(path)}")
    
    # Visualize subgraph
    print("\n3. Creating visualization...")
    kg.visualize_subgraph('er stress', depth=2, filename='er_stress_graph.png')
    
    print("\n" + "="*70)
    print("Knowledge graph construction complete!")
    print("Files created:")
    print("  - medical_knowledge_graph.pkl (binary format)")
    print("  - medical_knowledge_graph.json (JSON format)")
    print("  - er_stress_graph.png (visualization)")