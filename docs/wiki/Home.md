# Bibliometric Research Pipeline Wiki

Welcome to the **Bibliometric Research Pipeline Wiki**. This project is a modular, schema-driven Python and Web application designed for advanced bibliometric analysis, GPU-accelerated co-authorship network modeling, and NLP topic clustering.

---

## Wiki Table of Contents

- [1. System Architecture](file:///run/media/john/ssd%20external%20storage/git/bibliometric/docs/wiki/Architecture.md)
  - Core pipeline flow and data lifecycle
  - Pydantic schema validation (`PublicationSchema`)
  - Union-Find deduplication and metadata merging
- [2. Multi-Source Collectors & API Scrapers](file:///run/media/john/ssd%20external%20storage/git/bibliometric/docs/wiki/Collectors.md)
  - Supported APIs (OpenAlex, Semantic Scholar, Crossref, IEEE, ACM, PubMed, Scopus, WoS)
  - Preprint sources (arXiv, bioRxiv)
  - Specialized scrapers (DBLP, Springer, ACM Direct)
  - Registering custom data sources
- [3. Network Analysis & Graph Analytics](file:///run/media/john/ssd%20external%20storage/git/bibliometric/docs/wiki/Network-Analysis.md)
  - Co-authorship graph construction
  - Louvain community partitioning and PageRank scoring
  - Bibliographic coupling & co-citation matrix analysis
  - Percolation threshold analysis
- [4. NLP Engine & Topic Modeling](file:///run/media/john/ssd%20external%20storage/git/bibliometric/docs/wiki/Topic-Modeling.md)
  - BERTopic clustering on abstracts
  - Keyword Compound Annual Growth Rate (CAGR)
  - Paper screening filters (Embedding semantic search & LLM zero-shot classification)
- [5. Web Dashboard & Interactive Visualizer](file:///run/media/john/ssd%20external%20storage/git/bibliometric/docs/wiki/Web-Dashboard-and-Visualization.md)
  - FastAPI backend architecture
  - Next.js (React) web application
  - Live interactive `NetworkVisualizer.tsx` and control knobs
- [6. Command-Line Interface (CLI) Reference](file:///run/media/john/ssd%20external%20storage/git/bibliometric/docs/wiki/CLI-Reference.md)
  - Complete CLI flag reference
  - Execution modes (Autonomous vs. Local Dataset)
  - Stage execution control

---

## Quick Navigation & Execution

To run the entire application (Backend API + Next.js Web UI):
```bash
python run_local.py
```

To run the pipeline via CLI:
```bash
uv run biblio-pipeline --query "brain-computer interface" --limit 100 --start-year 2020 --end-year 2025
```
