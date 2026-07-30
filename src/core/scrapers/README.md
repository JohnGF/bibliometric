# Extended Scrapers & Alternative Collectors

This directory contains optional, specialized collectors and scrapers that are **not automatically triggered** by default in `UnifiedCollector`.

They are fully compatible with the standard `PublicationSchema` and can be imported and executed independently or passed to `UnifiedCollector` when needed.

## Available Collectors

### 1. `DBLPCollector` (`dblp.py`)
* **Source**: DBLP Computer Science Bibliography (`https://dblp.org`)
* **Description**: Dedicated computer science index covering IEEE, ACM, Springer CS, and USENIX publications.
* **Usage**:
```python
from src.core.scrapers import DBLPCollector

collector = DBLPCollector()
df = collector.fetch_papers("quantum computing", limit=50)
```

### 2. `SpringerCollector` (`springer.py`)
* **Source**: Springer Nature API & Crossref Member Filter (Member ID `297`)
* **Description**: Collects Springer Nature journal articles and book chapters. Supports optional `SPRINGER_API_KEY` or falls back to Crossref member index.
* **Usage**:
```python
from src.core.scrapers import SpringerCollector

collector = SpringerCollector()
df = collector.fetch_papers("brain computer interface", limit=50)
```

### 3. `ACMDirectScraper` (`acm_dl.py`)
* **Source**: ACM Digital Library (`https://dl.acm.org`)
* **Description**: Direct HTML parser for ACM Digital Library search results. Useful when institutional proxies or direct HTML extractions are preferred over API indices.
* **Usage**:
```python
from src.core.scrapers import ACMDirectScraper

scraper = ACMDirectScraper()
df = scraper.fetch_papers("deep learning", limit=50)
```
