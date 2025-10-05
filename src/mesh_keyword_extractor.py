import requests
from urllib.parse import quote_plus

MESH_LOOKUP = "https://id.nlm.nih.gov/mesh/lookup/descriptor?label={}&match=contains&limit=5"

def expand_with_mesh(topic, keywords, filters=None):
    terms = set([topic] + keywords)
    mesh_terms = set()
    for t in terms:
        r = requests.get(MESH_LOOKUP.format(quote_plus(t)))
        if r.ok:
            hits = r.json()
            for h in hits:
                mesh_terms.add(h.get("label"))
    # Compose PubMed query: prefer MeSH[MeSH Terms] OR keyword[tiab]
    mesh_query = " OR ".join(f'"{m}"[MeSH Terms]' for m in mesh_terms)
    kw_query = " OR ".join(f'("{k}"[tiab])' for k in keywords)
    base = "(" + " OR ".join(p for p in (mesh_query, kw_query) if p) + ")"
    # append filters if any (e.g., year, species)
    if filters:
        # simple example: filters={"year_from":2018}
        if "year_from" in filters:
            base += f' AND ("{filters["year_from"]}"[PDAT] : "3000"[PDAT])'
    return base

topic = "dystrophin glycoprotein complex"
keywords = ["cancer"]
filters = {"year_from":2018}

print(expand_with_mesh(topic, keywords, filters))