import requests

def get_human_kegg_pathways_for_gene(gene_symbol: str, limit: int = 5):
    """
    Given a human gene symbol (e.g., EGFR),
    return KEGG human pathways (hsaXXXX) that the gene participates in.
    """
    # Step 1: Find KEGG gene ID for human
    gene_url = f"https://rest.kegg.jp/find/genes/{gene_symbol}"
    gene_res = requests.get(gene_url)
    gene_res.raise_for_status()
    
    # Filter for human (hsa:)
    lines = [l for l in gene_res.text.strip().split("\n") if l.startswith("hsa:")]
    if not lines:
        raise ValueError(f"No human KEGG gene found for {gene_symbol}")
    
    gene_id = lines[0].split("\t")[0]  # e.g., 'hsa:1956'
    print(f"KEGG gene ID: {gene_id}")
    
    # Step 2: Get linked pathways for that gene
    link_url = f"https://rest.kegg.jp/link/pathway/{gene_id}"
    link_res = requests.get(link_url)
    link_res.raise_for_status()
    
    pathways = []
    for line in link_res.text.strip().split("\n")[:limit]:
        cols = line.split("\t")
        if len(cols) < 2:
            continue
        gene_col, path_col = cols  # e.g. hsa:1956    path:hsa04012
        pid = path_col.replace("path:", "")  # ✅ correct column now
        
        # Step 3: Fetch pathway info using /get instead of /list
        get_url = f"https://rest.kegg.jp/get/{pid}"
        info_res = requests.get(get_url)
        info_res.raise_for_status()
        
        # Extract pathway name
        name_line = next((line for line in info_res.text.split("\n") if line.startswith("NAME")), None)
        name = name_line.split("NAME")[1].strip() if name_line else "Unknown Pathway"
        
        # Step 4: Construct pathway URLs
        pathways.append({
            "pathway_id": pid,
            "title": name,
            "page_url": f"https://www.kegg.jp/pathway/{pid}",
            "image_url": f"https://www.kegg.jp/kegg/pathway/hsa/{pid}.png"
        })
    
    return pathways


# Example usage
if __name__ == "__main__":
    results = get_human_kegg_pathways_for_gene("EGFR", limit=5)
    for p in results:
        print(f"{p['pathway_id']} - {p['title']}")
        print(f"Page: {p['page_url']}")
        print(f"Image: {p['image_url']}\n")
