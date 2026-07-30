# Command-Line Interface (CLI) Reference

[Back to Wiki Home](file:///run/media/john/ssd%20external%20storage/git/bibliometric/docs/wiki/Home.md)

---

## Command Invocation

Run using local venv or `uv`:

```bash
# Universal (venv)
.venv/bin/biblio-pipeline [OPTIONS]

# Modern Alternative (uv)
uv run biblio-pipeline [OPTIONS]
```

---

## 1. Primary Inputs & Data Collection Flags

Flag | Type | Default | Description
--- | --- | --- | ---
`--query` | `str` | `None` | Query string for autonomous collection across APIs.
`--query-file` | `str` | `None` | Path to text file containing search query.
`--file` | `str` | `None` | Path to local CSV/Parquet dataset file.
`--limit` | `int` | `100` | Limit per source for collection (`0` = unlimited / fetch all matching).
`--start-year` | `int` | `None` | Start year filter.
`--end-year` | `int` | `None` | End year filter.
`--output` | `str` | `pipeline_results` | Output directory path.

---

## 2. API Key & Authentication Flags

Flag | Description
--- | ---
`--openalex-email` | Email for OpenAlex polite pool.
`--ss-api-key` | API Key for Semantic Scholar.
`--crossref-email` | Email for Crossref User-Agent headers.
`--pubmed-api-key` | API Key for NCBI PubMed.
`--scopus-api-key` | API Key for Elsevier Scopus.
`--scopus-inst-token` | Institutional token for Scopus.
`--wos-api-key` | API Key for Clarivate Web of Science.

---

## 3. Visualization & Network Filter Flags

Flag | Type | Default | Description
--- | --- | --- | ---
`--top-per-community` | `int` | `1` | Top N representative author leaders per community to plot on static network PDF graphs.
`--min-publications` | `int` | `1` | Minimum publication count threshold for co-authorship network node inclusion.

---

## 4. Screening & Modular Stage Flags

Flag | Description
--- | ---
`--screen-embeddings` | Enable embedding semantic relevance filter.
`--embedding-threshold` | Cosine similarity threshold for embedding filter (default: `0.35`).
`--screen-llm` | Enable LLM zero-shot classification screening.
`--llm-model` | Model name for Ollama LLM screening (default: `llama3.2:3b`).
`--include-preprints` | Include preprints from arXiv and bioRxiv.
`--stages` | Comma-separated list of stages to run (`growth,country,cagr,nlp,network,percolation`).
`--skip-nlp` | Skip BERTopic topic modeling.
`--skip-network` | Skip co-authorship network graph generation.
`--skip-cagr` | Skip keyword CAGR calculation.
`--skip-country` | Skip country evolution analysis.
`--skip-percolation` | Skip percolation threshold analysis.
