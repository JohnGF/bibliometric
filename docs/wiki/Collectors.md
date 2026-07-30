# Multi-Source Collectors & API Scrapers

[Back to Wiki Home](file:///run/media/john/ssd%20external%20storage/git/bibliometric/docs/wiki/Home.md)

---

## Overview

The collector layer in [src/core/collectors/](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/collectors/) provides a unified interface for fetching bibliometric metadata across diverse APIs and scrapers.

All collectors inherit or implement `fetch_papers(query, limit, start_year, end_year)` and map data into standard `PublicationSchema` format.

---

## Supported Standard Collectors

Source | Module Path | Authentication | Notes
--- | --- | --- | ---
**OpenAlex** | [openalex.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/collectors/openalex.py) | Optional Email (`OPENALEX_EMAIL`) | Uses cursor-based pagination and polite pool API key.
**Semantic Scholar** | [semantic_scholar.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/collectors/semantic_scholar.py) | Optional Key (`SS_API_KEY`) | Provides citation counts and author IDs.
**Crossref** | [crossref.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/collectors/crossref.py) | Optional Email (`CROSSREF_EMAIL`) | Uses Crossref REST API for journal & conference DOIs.
**PubMed** | [pubmed.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/collectors/pubmed.py) | Optional Key (`PUBMED_API_KEY`) | NCBI Entrez E-utilities interface for biomedical literature.
**Elsevier Scopus** | [elsevier.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/collectors/elsevier.py) | API Key (`SCOPUS_API_KEY`) | Elsevier Scopus API for indexed publications.
**Web of Science** | [wos.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/collectors/wos.py) | API Key (`WOS_API_KEY`) | Clarivate Web of Science Starter API.
**IEEE Xplore** | [ieee.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/collectors/ieee.py) | API Key / OpenAlex fallback | IEEE API collector with OpenAlex publisher lineage fallback.
**ACM Digital Library** | [acm.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/collectors/acm.py) | OpenAlex Lineage Index | ACM Publisher index query via OpenAlex `p4310319965`.
**arXiv** | [arxiv.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/collectors/arxiv.py) | None | Preprints in computer science, physics, and math.
**bioRxiv** | [biorxiv.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/collectors/biorxiv.py) | None | Biological and life sciences preprints.

---

## Extended Scrapers & Alternative Collectors

Located in [src/core/scrapers/](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/scrapers/):

1. **DBLP Collector (`dblp.py`)**: Computer science bibliography query engine.
2. **Springer Collector (`springer.py`)**: Springer Nature API & Crossref member ID index.
3. **ACM Direct Scraper (`acm_dl.py`)**: Direct HTML parser for ACM Digital Library.

---

## Programmatic Usage Example

```python
from src.core.collection import UnifiedCollector

# Instantiate collector with polite pool email
collector = UnifiedCollector(config={"openalex_email": "user@example.com"})

# Fetch peer-reviewed literature
df = collector.fetch_all(
    query="brain computer interface",
    limit_per_source=100,
    start_year=2020,
    end_year=2025,
    include_preprints=False
)

print(f"Collected and deduplicated {len(df)} unique records.")
```
