# API Integrations Documentation

## Table of Contents

- [Overview](#overview)
- [Internal API Endpoints](#internal-api-endpoints)
- [External API Integrations](#external-api-integrations)


## Overview

SpacePath integrates with multiple external APIs to provide comprehensive biological insights. The system uses a centralized API service layer to manage external integrations, handle authentication, implement rate limiting, and provide fallback mechanisms.

## Internal API Endpoints

### Base URL
```
http://localhost:8000
```

### 1. Query Processing

#### Extract Protein Name
- **Endpoint**: `POST /query`
- **Purpose**: Extract protein name from natural language query
- **Request Body**:
```json
{
  "query": "What happens to EGFR in microgravity conditions?"
}
```
- **Response**:
```json
{
  "protein_name": "EGFR"
}
```
- **Error Responses**:
  - `400`: Invalid request format
  - `500`: Internal server error

#### Get Research Summary
- **Endpoint**: `POST /get-research-summary`
- **Purpose**: Generate RAG-based research summary
- **Request Body**:
```json
{
  "query": "What happens to EGFR in microgravity conditions?"
}
```
- **Response**:
```json
{
  "summary": "Research indicates that EGFR signaling is significantly altered in microgravity conditions...",
  "relevant_papers": [
    "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1234567/",
    "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2345678/"
  ],
  "source_count": 5
}
```

### 2. Protein Information

#### Get Protein Details
- **Endpoint**: `POST /get-protein-info`
- **Purpose**: Retrieve protein information and clinical studies
- **Request Body**:
```json
{
  "protein_name": "EGFR"
}
```
- **Response**:
```json
{
  "protein_info": {
    "protein_name": "EGFR",
    "accession": "P00533",
    "alternate_names": ["Proto-oncogene c-ErbB-1", "Epidermal growth factor receptor"],
    "synonyms": ["ERBB1", "HER1", "EGFR"],
    "functions": [
      "Receptor tyrosine kinase that binds ligands of the EGF family",
      "Plays a role in cell growth, proliferation, and differentiation"
    ]
  },
  "clinical_studies": {
    "clinical_studies": [
      {
        "nct_id": "NCT01234567",
        "title": "EGFR Inhibitor Study in Lung Cancer",
        "brief_summary": "A phase II study evaluating EGFR inhibitors...",
        "link": "https://clinicaltrials.gov/study/NCT01234567",
        "publication_year": "2023"
      }
    ]
  }
}
```

#### Get Pathways
- **Endpoint**: `POST /get-pathways`
- **Purpose**: Retrieve KEGG pathways for a protein
- **Request Body**:
```json
{
  "protein_name": "EGFR"
}
```
- **Response**:
```json
[
  {
    "pathway_id": "hsa04012",
    "title": "ErbB signaling pathway",
    "page_url": "https://www.kegg.jp/pathway/hsa04012",
    "image_url": "https://www.kegg.jp/kegg/pathway/hsa/hsa04012.png"
  },
  {
    "pathway_id": "hsa04015",
    "title": "Rap1 signaling pathway",
    "page_url": "https://www.kegg.jp/pathway/hsa04015",
    "image_url": "https://www.kegg.jp/kegg/pathway/hsa/hsa04015.png"
  }
]
```

### 3. Health Check

#### System Health
- **Endpoint**: `GET /health`
- **Purpose**: Check system health and status
- **Response**:
```json
{
  "status": "healthy",
  "message": "SPACEPATH Backend is running",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "services": {
    "vector_db": "healthy",
    "llm_service": "healthy",
    "external_apis": "healthy"
  }
}
```

## External API Integrations

### 1. UniProt API

#### Purpose
Retrieve comprehensive protein information including functions, alternative names, and molecular details.

#### Base URL
```
https://rest.uniprot.org/uniprotkb
```

#### Key Endpoints

**Search Proteins by Gene Name**
```http
GET /search?query=gene:EGFR AND organism_id:9606&fields=accession,proteinDescription,genes,comments
```

**Get Protein Entry**
```http
GET /P00533
```

#### Request Example
```python
import requests

def get_protein_info(gene_name: str):
    search_url = "https://rest.uniprot.org/uniprotkb/search"
    params = {
        "query": f"gene:{gene_name} AND organism_id:9606",
        "fields": "accession,proteinDescription,genes,comments",
        "format": "json"
    }
    
    response = requests.get(search_url, params=params)
    return response.json()
```

#### Response Schema
```json
{
  "results": [
    {
      "primaryAccession": "P00533",
      "proteinDescription": {
        "recommendedName": {
          "fullName": {
            "value": "Epidermal growth factor receptor"
          }
        },
        "alternativeNames": [
          {
            "fullName": {
              "value": "Proto-oncogene c-ErbB-1"
            }
          }
        ]
      },
      "genes": [
        {
          "geneName": {
            "value": "EGFR"
          },
          "synonyms": [
            {"value": "ERBB1"},
            {"value": "HER1"}
          ]
        }
      ],
      "comments": [
        {
          "commentType": "FUNCTION",
          "texts": [
            {
              "value": "Receptor tyrosine kinase that binds ligands of the EGF family..."
            }
          ]
        }
      ]
    }
  ]
}
```

#### Rate Limits
- **Free Tier**: 10 requests per second
- **Paid Tier**: 100 requests per second
- **Caching**: 24 hours for protein entries

### 2. KEGG API

#### Purpose
Retrieve biological pathway information and pathway maps.

#### Base URL
```
https://rest.kegg.jp
```

#### Key Endpoints

**Get Pathways for Gene**
```http
GET /link/pathway/hsa:EGFR
```

**Get Pathway Information**
```http
GET /get/hsa04012
```

**Get Pathway Image**
```http
GET /pathway/hsa/hsa04012.png
```

#### Request Example
```python
def get_kegg_pathways(gene_name: str):
    # Get pathway links
    pathway_url = f"https://rest.kegg.jp/link/pathway/hsa:{gene_name}"
    response = requests.get(pathway_url)
    
    pathways = []
    for line in response.text.strip().split('\n'):
        if line:
            pathway_id, gene_id = line.split('\t')
            pathway_id = pathway_id.replace('path:', '')
            
            # Get pathway details
            detail_url = f"https://rest.kegg.jp/get/{pathway_id}"
            detail_response = requests.get(detail_url)
            
            pathways.append({
                "pathway_id": pathway_id,
                "title": extract_pathway_name(detail_response.text),
                "page_url": f"https://www.kegg.jp/pathway/{pathway_id}",
                "image_url": f"https://www.kegg.jp/kegg/pathway/hsa/{pathway_id}.png"
            })
    
    return pathways
```

#### Rate Limits
- **Free Tier**: 1 request per second
- **Caching**: 7 days for pathway data

### 3. ClinicalTrials.gov API

#### Purpose
Search for clinical trials related to specific proteins or drugs.

#### Base URL
```
https://clinicaltrials.gov/api/v2
```

#### Key Endpoints

**Search Studies**
```http
GET /studies?query=EGFR&format=json&pageSize=20
```

**Get Study Details**
```http
GET /studies/NCT01234567
```

#### Request Example
```python
def search_clinical_trials(protein_name: str):
    search_url = "https://clinicaltrials.gov/api/v2/studies"
    params = {
        "query": protein_name,
        "format": "json",
        "pageSize": 20,
        "filter.overallStatus": "RECRUITING|ACTIVE_NOT_RECRUITING|COMPLETED"
    }
    
    response = requests.get(search_url, params=params)
    return response.json()
```

#### Response Schema
```json
{
  "studies": [
    {
      "protocolSection": {
        "identificationModule": {
          "nctId": "NCT01234567",
          "briefTitle": "EGFR Inhibitor Study in Lung Cancer"
        },
        "statusModule": {
          "overallStatus": "RECRUITING",
          "startDateStruct": {
            "date": "2023-01-15"
          }
        },
        "descriptionModule": {
          "briefSummary": "A phase II study evaluating EGFR inhibitors..."
        }
      }
    }
  ]
}
```

#### Rate Limits
- **Free Tier**: 100 requests per hour
- **Caching**: 24 hours for search results

### 4. NASA APIs

#### OSDR (Open Science Data Repository)

**Purpose**: Access NASA's space biology datasets and research papers.

**Base URL**: `https://osdr.nasa.gov/api`

**Key Endpoints**:
```http
GET /datasets?query=microgravity&type=biological
GET /papers?protein=EGFR&condition=microgravity
```

#### GeneLab

**Purpose**: Access spaceflight experiment data.

**Base URL**: `https://genelab.nasa.gov/api`

**Key Endpoints**:
```http
GET /studies?organism=human&condition=microgravity
GET /studies/{study_id}/data
```

---

*This API integrations documentation provides comprehensive information about all external and internal API endpoints used by SpacePath. For implementation details, refer to the source code in the `fastapi_backend/utils/` directory.*
