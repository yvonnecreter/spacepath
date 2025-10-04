import requests
from fastapi_backend.schema_models.model import ProteinInfo

def get_alternative_names(gene_name: str, organism_id: int = 9606):
    """
    Given a gene/protein name (e.g., 'EGFR'), fetch its UniProt accession
    and alternative names (human by default: organism_id=9606).
    """
    # Step 1: Get UniProt accession by gene name
    search_url = f"https://rest.uniprot.org/uniprotkb/search"
    params = {
        "query": f"gene:{gene_name} AND organism_id:{organism_id}",
        "fields": "accession",
    }
    
    response = requests.get(search_url, params=params, headers={"Accept": "application/json"})
    response.raise_for_status()
    
    data = response.json()
    if not data.get("results"):
        raise ValueError(f"No UniProt accession found for gene {gene_name} in organism {organism_id}")
    
    accession = data["results"][0]["primaryAccession"]

    
    # Step 2: Fetch full UniProt entry by accession
    entry_url = f"https://rest.uniprot.org/uniprotkb/{accession}"
    entry_response = requests.get(entry_url, headers={"Accept": "application/json"})
    entry_response.raise_for_status()
    
    entry = entry_response.json()
    
    # Step 3: Extract alternative names
    protein_desc = entry.get("proteinDescription", {})
    alt_names = protein_desc.get("alternativeNames", [])
    
    # Step 4: Fetch synonyms
    synonyms = []
    genes = entry.get("genes", [])
    if genes and len(genes) > 0:
        synonym_list = genes[0].get('synonyms', [])
        for synonym in synonym_list:
            synonyms.append(synonym["value"])
    
    return accession, [alt["fullName"]["value"] for alt in alt_names if "fullName" in alt], synonyms

def get_protein_function(accession: str):
    """
    Given a UniProt accession (e.g. 'P00533'), return the function text.
    """
    url = f"https://rest.uniprot.org/uniprotkb/{accession}"
    response = requests.get(url, headers={"Accept": "application/json"})
    response.raise_for_status()
    
    data = response.json()
    functions = []
    
    # Look through comments for FUNCTION type
    for comment in data.get("comments", []):
        if comment.get("commentType") == "FUNCTION":
            texts = comment.get("texts", [])
            for t in texts:
                functions.append(t.get("value", ""))
    
    return functions


def extract_protein_details(protein_name: str):
    """
    Get protein information
    """
    accession, alt_names, synonyms = get_alternative_names(protein_name)
    functions = get_protein_function(accession)
    info = ProteinInfo(protein_name=protein_name, accession=accession, alternate_names=alt_names, synonyms=synonyms, functions=functions)
    return info
