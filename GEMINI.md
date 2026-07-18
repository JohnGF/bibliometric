# Bibliometric Research Pipeline: Project Mandates

## 1. Architecture Overview
The project is a modular, schema-driven Python pipeline for bibliometric research, utilizing GPU acceleration (RAPIDS) for network analysis and advanced NLP (BERTopic) for topic modeling.

- **`src/core/collectors/`**: Modular API interfaces (OpenAlex, Semantic Scholar).
- **`src/core/collection.py`**: `UnifiedCollector` for multi-source fetching and deduplication.
- **`src/core/ingestion.py`**: Data loading and Pydantic schema validation.
- **`src/core/nlp.py`**: BERTopic modeling and CAGR calculations.
- **`src/core/network.py`**: GPU-accelerated co-authorship networks via `cuGraph`.
- **`src/core/viz.py`**: Centralized visualization logic.
- **`src/pipeline.py`**: Orchestration layer with CLI support.
- **`src/ui/app.py`**: Flet-based GUI for autonomous collection and pipeline execution.

## 2. Key Features
- **Autonomous Collection**: Fetch papers by query and year range from OpenAlex and Semantic Scholar.
- **Unified Schema**: All collectors map data to a standard format (Title, Abstract, Authors, Year, Affiliations, DOI, Cite Count).
- **GPU Acceleration**: Uses `cudf` and `cugraph` for high-performance network analysis.
- **Deduplication**: Automatically merges records from multiple sources based on DOI and Title.

## 3. Workflow Commands

### Run directly on Host Machine (Recommended)
You can run the entire application (both the FastAPI backend and Next.js frontend concurrently) directly on your machine's hardware:
```bash
python run_local.py
```
This script automatically resolves dependencies, handles environments, and runs both servers concurrently.

To run the CLI pipeline directly on the hardware:
```bash
.venv/bin/biblio-pipeline --query "brain-computer interface" --limit 100 --start-year 2020 --end-year 2024
```

### Run via Container (Legacy)

#### Run GUI (Web Mode)
```bash
podman run -it --rm --device nvidia.com/gpu=all -p 8550:8550 -v .:/app:z biblio-pipeline
```

#### Run CLI (Backend)
```bash
podman run -it --rm --device nvidia.com/gpu=all -v .:/app:z --entrypoint /bin/bash biblio-pipeline
# Inside container:
python -m src.pipeline --query "brain-computer interface" --start-year 2020 --end-year 2024 --limit 100
```

## 4. Hybrid Development Workflow (Recommended)
For the best developer experience, use a hybrid setup:

### A. Backend (Container with Auto-Reload)
Run the FastAPI server inside the container but mount your local source code. This enables GPU access with instant code updates:
```bash
podman run -it --rm \
  --device nvidia.com/gpu=all \
  -v .:/app:z \
  -p 8000:8000 \
  -e OPENALEX_EMAIL="your-email@example.com" \
  --entrypoint uvicorn \
  biblio-pipeline src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### B. Frontend (Local Next.js)
Run the frontend on your host machine for the fastest HMR (Hot Module Replacement):
```bash
cd frontend
npm install
npm run dev
# Dashboard accessible at http://localhost:3000
```

## 5. Development Standards
- **Adding Sources**: New collectors should be added to `src/core/collectors/` and registered in `UnifiedCollector`.
- **Validation**: Always validate data using `PublicationSchema` before processing.
- **GPU Safety**: Ensure RAPIDS libraries (`cudf`, `cugraph`) are only called within the container environment.
- **Modularity**: Keep core analysis logic independent of the UI or CLI entrypoints.
