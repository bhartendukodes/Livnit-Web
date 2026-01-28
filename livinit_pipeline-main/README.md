# Livinit Pipeline

AI-powered interior design automation that generates personalized furniture selections and optimized 3D room layouts.

## Architecture

```
                              LIVINIT PIPELINE
    ============================================================================

    INPUT                     PROCESSING                              OUTPUT
    -----                     ----------                              ------

    +----------------+        +------------------------------------------+
    | User Intent    |------->|                                          |
    | "modern living |        |  +----------------+    +---------------+ |
    |  room with..." |        |  | Asset Layer    |    | Layout Layer  | |
    +----------------+        |  |                |    |               | |
                              |  | Load Assets    |--->| Initial       | |
    +----------------+        |  |      |         |    | Layout (LLM)  | |
    | Budget         |------->|  |      v         |    |      |        | |
    | $5000          |        |  | RAG Filter     |    |      v        | |
    +----------------+        |  | (pgvector)     |    | Layout        | |
                              |  |      |         |    | Criteria      | |
    +----------------+        |  |      v         |    |      |        | |
    | Room           |------->|  | Select Assets  |    |      v        | |
    | (USDZ/dims)    |        |  | (LLM + LP)     |    | LayoutVLM     | |
    +----------------+        |  |      |         |    | Optimizer     | |
                              |  |      v         |    | (PyTorch)     | |
                              |  | Validate &     |--->|      |        | |
                              |  | Cost           |    |      v        | |
                              |  +----------------+    +---------------+ |
                              |                                          |
                              +------------------------------------------+
                                                |
                                                v
                              +------------------------------------------+
                              |              OUTPUTS                     |
                              |  - final_layout.json                     |
                              |  - selected_assets.json                  |
                              |  - optimization.gif                      |
                              |  - cost_summary                          |
                              +------------------------------------------+
```

## Pipeline Flows

### Simple Pipeline (`main.py`)
For rectangular rooms without complex geometry.

```
Load Assets -> Select (LLM+LP) -> Validate -> Layout Criteria -> Initial Layout -> LayoutVLM
```

### Advanced Pipeline (`pipeline.py`)
Full-featured with USDZ room extraction and RAG-based selection.

```
Load Assets -> Extract Room (USDZ) -> Init Vector Store -> Refine Intent
     |
     v
RAG Scope -> Select (LLM) -> Validate -> Initial Layout -> Layout Criteria -> LayoutVLM
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| LLM Client | `pipeline/core/llm.py` | Gemini API integration |
| Asset Manager | `pipeline/core/asset_manager.py` | Output file organization |
| Pipeline Nodes | `pipeline/nodes/` | Stage implementations |
| Layout Solver | `pipeline/nodes/run_layoutvlm.py` | PyTorch-based optimization |
| Vector Store | `pipeline/nodes/init_vector_store.py` | pgvector semantic search |
| API | `api.py` | FastAPI REST service |

## Tech Stack

- **LLM**: Google Gemini 3.5 Flash
- **Pipeline**: LangGraph
- **Optimization**: scipy MILP, PyTorch
- **Embeddings**: SigLIP2
- **Search**: PostgreSQL + pgvector
- **3D**: Pixar USD, Shapely
- **API**: FastAPI + Mangum (Lambda)

## Usage

```bash
# Simple pipeline
python main.py

# Advanced pipeline
python pipeline.py

# API server
docker-compose up
```

## Output Structure

```
runs/YYYYMMDD_HHMMSS/
├── 00_meta/              # Run metadata
├── 01_load_assets/       # Asset catalog
├── 04_select_assets/     # Selection results
├── 05_validate_and_cost/ # Cost validation
├── 06_initial_layout/    # LLM-generated layout
├── 07_layout_criteria/   # Constraint program
└── 08_layoutvlm/         # Optimized layout + GIF
```
