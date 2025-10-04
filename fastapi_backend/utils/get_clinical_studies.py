#!/usr/bin/env python3
"""
Resolve a gene/protein name -> UniProt accession, names, function,
then query ClinicalTrials.gov (Switzerland) for top 10 studies mentioning that term(s).

Requirements: requests
"""

import requests
import html
from typing import List, Dict
from fastapi_backend.utils.extract_protein_details import extract_protein_details
from fastapi_backend.schema_models.model import ClinicalStudies, ClinicalStudiesResponse

USER_AGENT = "ctg-uniprot-integration/1.0 (example script)"

def get_uniprot_entry_by_gene(gene_name: str, organism_id: int = 9606) -> Dict:
    """
    Search UniProtKB by gene name (human by default) and return the first entry JSON.
    """
    search_url = "https://rest.uniprot.org/uniprotkb/search"
    params = {
        "query": f"gene:{gene_name} AND organism_id:{organism_id}",
        "fields": "accession,id,protein_name,gene_names,protein_description,comment(FUNCTION)",
        "format": "json",
        "size": 1
    }
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    r = requests.get(search_url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    j = r.json()
    results = j.get("results", [])
    if not results:
        raise ValueError(f"No UniProt entries found for gene {gene_name} (organism {organism_id})")
    # If you want to make sure you pick reviewed entries first, the search query can be refined.
    accession = results[0]["primaryAccession"]
    # Now fetch full entry (more reliable for structured fields)
    entry_url = f"https://rest.uniprot.org/uniprotkb/{accession}"
    r2 = requests.get(entry_url, headers=headers, timeout=30)
    r2.raise_for_status()
    return r2.json()


def extract_uniprot_info(entry_json: Dict) -> Dict:
    """
    Pull accession, recommended name, alternative names, gene synonyms and function text.
    """
    info = {}
    info["accession"] = entry_json.get("primaryAccession") or entry_json.get("accession")
    # proteinDescription recommendedName
    pdesc = entry_json.get("proteinDescription", {})
    rec = pdesc.get("recommendedName", {}).get("fullName", {}).get("value")
    info["recommended_name"] = rec
    alts = []
    for alt in pdesc.get("alternativeNames", []):
        fullname = alt.get("fullName", {}).get("value")
        if fullname:
            alts.append(fullname)
    info["alternate_names"] = alts

    # gene synonyms (geneNames)
    gene_names = []
    gn = entry_json.get("genes", [])  # UniProt JSON uses 'genes' array
    for g in gn:
        # 'geneName' is usually the primary, 'synonyms' is a list
        primary = g.get("geneName", {}).get("value")
        if primary:
            gene_names.append(primary)
        for s in g.get("synonyms", []):
            sval = s.get("value")
            if sval:
                gene_names.append(sval)
    # unique
    info["gene_synonyms"] = sorted(set(gene_names))

    # function comment(s)
    functions = []
    for comment in entry_json.get("comments", []):
        if comment.get("commentType") == "FUNCTION":
            for t in comment.get("texts", []):
                v = t.get("value")
                if v:
                    functions.append(v.strip())
    info["functions"] = functions
    return info


def build_ctg_query_terms(gene_name: str, uniprot_info: Dict) -> str:
    """
    Build a ClinicalTrials.gov 'condition' query string combining gene name, synonyms, and alt names.
    Terms will be OR-joined (ClinicalTrials.gov search is free-text-ish).
    """
    terms = set()
    terms.add(gene_name)
    for s in uniprot_info.get("synonyms", []):
        terms.add(s)
    for a in uniprot_info.get("alternate_names", []):
        # keep shorter alt names too
        if len(a) <= 80:
            terms.add(a)
    # Clean terms: remove empties and trim
    cleaned = [t.strip() for t in terms if t and len(t.strip()) > 0]
    # join with ' OR ' for expressive query (ClinicalTrials.gov will accept free text)
    # We'll URL-encode later through requests params.
    return " OR ".join(cleaned)


def query_clinicaltrials_gov(condition_query: str, location_str: str = "Switzerland", page_size: int = 10):
    """
    Query ClinicalTrials.gov API v2 studies endpoint.
    Returns a list of study dicts (raw JSON objects).
    Docs: ClinicalTrials.gov API v2 (/api/v2/studies) supports query.cond and query.locn.
    """
    url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query.cond": condition_query,
        "query.locn": location_str,
        "pageSize": page_size,
        "format": "json"
    }
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    j = r.json()
    # 'studies' key typically contains the array of study objects
    return j.get("studies", [])


def safe_get_study_field(study: Dict, path: List[str], default=None):
    """Helper to safely get nested fields from the ClinicalTrials.gov v2 JSON study object."""
    cur = study
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur


def clinicaltrials_link_from_nct(nctid: str) -> str:
    """
    Construct a user-friendly link to the study page on ClinicalTrials.gov.
    The canonical viewer URL is: https://clinicaltrials.gov/study/<NCTID>
    The classic CTG viewer also works: https://clinicaltrials.gov/ct2/show/<NCTID>
    We'll provide the ct2/show URL for compatibility.
    """
    return f"https://clinicaltrials.gov/ct2/show/{nctid}"


def get_protein_clinical_studies(gene_name: str = "EGFR"):
    print(f"Resolving UniProt entry for gene '{gene_name}' (human)...")
    # entry = get_uniprot_entry_by_gene(gene_name, organism_id=9606)
    # info = extract_uniprot_info(entry)
    protein_info = extract_protein_details(gene_name)
    print("UniProt accession:", protein_info.accession)
    if protein_info.alternate_names:
        print("Alternative protein names:", "; ".join(protein_info.alternate_names))
    if protein_info.synonyms:
        print("Gene synonyms:", ", ".join(protein_info.synonyms))
    if protein_info.functions:
        print("\nFunction (short):")
        # print the first function paragraph, truncated to ~300 chars
        func0 = protein_info.functions[0]
        print(func0[:600] + ("..." if len(func0) > 600 else ""))

    # Build ClinicalTrials.gov query
    cond_query = build_ctg_query_terms(gene_name, protein_info.to_dict())
    print("\nQuerying ClinicalTrials.gov for condition terms (Switzerland):")
    print("Condition query:", cond_query)

    studies = query_clinicaltrials_gov(cond_query, location_str="Switzerland", page_size=10)
    if not studies:
        print("No studies found for that query in Switzerland.")
        return

    clinical_studies: List[ClinicalStudies] = []

    print(f"\nTop {min(10, len(studies))} studies found (NCTId, title, brief summary):\n")
    for i, s in enumerate(studies, start=1):
        # Typical path to NCTId in v2: protocolSection -> identificationModule -> nctId
        nct = safe_get_study_field(s, ["protocolSection", "identificationModule", "nctId"])
        title = (
            safe_get_study_field(s, ["protocolSection", "identificationModule", "officialTitle"])
            or safe_get_study_field(s, ["protocolSection", "identificationModule", "briefTitle"])
            or "(no title)"
        )
        # brief summary may be under descriptionModule -> briefSummary -> briefSummaryValue (or text)
        brief = safe_get_study_field(s, ["protocolSection", "descriptionModule", "briefSummary", "text"])
        if brief is None:
            brief = safe_get_study_field(s, ["protocolSection", "descriptionModule", "briefSummary"])
        if brief is None:
            # also try outcome measures or designModule descriptions
            brief = "(no brief summary available)"
        # some summaries may include HTML entities; unescape them
        brief = html.unescape(brief) if isinstance(brief, str) else str(brief)

        link = clinicaltrials_link_from_nct(nct) if nct else "(no NCTId)"
        print(f"{i}. {nct} -- {title}")
        print(f"   Link: {link}")
        # print a short abstract/summary (truncate)
        print("   Summary:", (brief[:600] + "..." if len(brief) > 600 else brief))
        print()
        clinical_studies.append(ClinicalStudies(nct_id=nct, title=title, brief_summary=brief, link=link))


    return protein_info, ClinicalStudiesResponse(clinical_studies=clinical_studies)

if __name__ == "__main__":
    get_protein_clinical_studies("EGFR")
