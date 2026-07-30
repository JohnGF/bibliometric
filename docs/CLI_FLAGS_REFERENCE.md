# Bibliometric Pipeline CLI Flags Reference

This document provides a comprehensive reference for all command-line interface (CLI) flags supported by `biblio-pipeline` (`src/pipeline.py`).

---

## 1. Input & Search Query Flags

| Flag | Argument Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--query` | `str` | `None` | Search query string for autonomous multi-source API collection. |
| `--query-file` | `str` | `None` | Path to text file containing search query (e.g. `data/original_33k_query.txt`). Useful for long, multi-line Boolean queries. |
| `--file` | `str` | `None` | Path to local CSV or Parquet file (e.g. exports from Scopus, Web of Science, or PubMed). |
| `--start-year` | `int` | `None` | Start publication year for collection filter (e.g. `2015`). |
| `--end-year` | `int` | `None` | End publication year for collection filter (e.g. `2026`). |
| `--limit` | `int` | `100` | Max papers per API source. **Set to `0` for unlimited fetching** across OpenAlex, PubMed, and Scopus. |

---

## 2. API Credentials Flags

| Flag | Argument Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--openalex-email` | `str` | `env.OPENALEX_EMAIL` | Email for OpenAlex Polite Pool (10x faster rate limits). |
| `--pubmed-api-key` | `str` | `env.PUBMED_API_KEY` | NCBI PubMed API Key (boosts rate limit from 3 to 10 req/sec). |
| `--scopus-api-key` | `str` | `env.SCOPUS_API_KEY` | Elsevier Scopus API Key (enables year-by-year 27k+ paper streaming). |
| `--scopus-inst-token`| `str` | `env.SCOPUS_INST_TOKEN`| Institutional Token for Scopus (optional). |
| `--crossref-email` | `str` | `env.CROSSREF_EMAIL` | Email for Crossref User-Agent polite pool. |
| `--ss-api-key` | `str` | `env.SS_API_KEY` | Semantic Scholar API Key (optional). |
| `--wos-api-key` | `str` | `env.WOS_API_KEY` | Web of Science API Key (optional). |
| `--ieee-api-key` | `str` | `env.IEEE_API_KEY` | Official IEEE Xplore API Key (falls back to OpenAlex IEEE index if absent). |

---

## 3. Paper Screening & LLM Options

| Flag | Argument Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--screen-embeddings` | `switch` | `False` | Enables Option 1: GPU Vector Embedding Relevance Filter (SentenceTransformers `all-MiniLM-L6-v2`). |
| `--embedding-threshold`| `float` | `0.35` | Cosine similarity threshold for embedding relevance filter. |
| `--screen-llm` | `switch` | `False` | Enables Option 2: Zero-shot LLM classification & noise treatment paradigm tagging. |
| `--llm-model` | `str` | `"llama3.2:3b"`| Model name for Ollama local LLM screening. |
| `--include-preprints` | `switch` | `False` | Includes preprints from arXiv and bioRxiv (disabled by default for peer-reviewed papers only). |

---

## 4. Output Options

| Flag | Argument Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--output` | `str` | `"pipeline_results"` | Destination directory where all PDFs, CSVs, BERTopic models, and co-authorship networks are saved. |

---

## Example Usage

### Full 33,525 Manuscript Corpus Fetch (Unlimited & Screened)
```bash
uv run biblio-pipeline \
  --query-file data/original_33k_query.txt \
  --start-year 2015 \
  --end-year 2026 \
  --limit 0 \
  --screen-embeddings \
  --embedding-threshold 0.35 \
  --output pipeline_results_manuscript_33k
```
