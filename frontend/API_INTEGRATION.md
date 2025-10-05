# API Integration Guide

This document describes the backend API integration for the Space Path frontend application.

## API Endpoints

The frontend integrates with the following FastAPI backend endpoints:

### 1. Extract Protein Name
- **Endpoint**: `POST /query`
- **Purpose**: Extract protein name from user query
- **Request**: `{ "query": "What happens to EGFR in microgravity?" }`
- **Response**: `{ "protein_name": "EGFR" }`

### 2. Get Protein Information
- **Endpoint**: `POST /get-protein-info`
- **Purpose**: Get protein details and clinical studies
- **Request**: `{ "protein_name": "EGFR" }`
- **Response**: 
```json
{
  "protein_info": {
    "protein_name": "EGFR",
    "accession": "P00533",
    "alternate_names": ["Proto-oncogene c-ErbB-1"],
    "synonyms": ["ERBB1", "HER1"],
    "functions": ["Receptor tyrosine kinase..."]
  },
  "clinical_studies": {
    "clinical_studies": [
      {
        "nct_id": "NCT123456",
        "title": "Study Title",
        "brief_summary": "Study summary...",
        "link": "https://clinicaltrials.gov/study/NCT123456"
      }
    ]
  }
}
```

### 3. Get Pathways
- **Endpoint**: `POST /get-pathways`
- **Purpose**: Get KEGG pathways for the protein
- **Request**: `{ "protein_name": "EGFR" }`
- **Response**: 
```json
[
  {
    "pathway_id": "hsa04012",
    "title": "ErbB signaling pathway",
    "page_url": "https://www.kegg.jp/pathway/hsa04012",
    "image_url": "https://www.kegg.jp/kegg/pathway/hsa/hsa04012.png"
  }
]
```

### 4. Get Research Summary
- **Endpoint**: `POST /get-research-summary`
- **Purpose**: Get RAG-generated research summary
- **Request**: `{ "query": "What happens to EGFR in microgravity?" }`
- **Response**:
```json
{
  "summary": "Research summary text...",
  "relevant_papers": ["https://paper1.com", "https://paper2.com"],
  "source_count": 5
}
```

## Frontend Architecture

### API Service (`src/services/api.ts`)
- Centralized API client with error handling
- Type-safe request/response handling
- Parallel execution for faster loading

### Custom Hook (`src/hooks/useQueryWorkflow.ts`)
- Manages the complete query workflow
- Handles loading states for each step
- Provides real-time updates to the UI

### Component Updates
- **InsightsPanel**: Shows protein info, research summary with loading states
- **PathwaysViewer**: Displays KEGG pathways with images
- **ClinicalTrialsList**: Shows clinical studies from ClinicalTrials.gov
- **ExplorerPanel**: Coordinates data flow to child components

## Loading States

The application implements progressive loading:

1. **Immediate**: User query appears
2. **Step 1**: Protein name extraction (fast)
3. **Step 2-3**: Protein info and pathways (parallel, moderate speed)
4. **Step 4**: Research summary (slowest, shows loading indicator)

## Error Handling

- Network errors are caught and displayed to users
- Failed API calls don't block other components
- Graceful degradation when services are unavailable

## Configuration

Update the API base URL in `src/services/api.ts`:
```typescript
const API_BASE_URL = 'http://localhost:8000'; // Change to your backend URL
```

## Usage

The integration is automatic - users simply ask questions and the system:
1. Extracts the protein name
2. Fetches protein information and clinical studies
3. Retrieves related pathways
4. Generates a research summary
5. Updates the UI progressively as data becomes available
