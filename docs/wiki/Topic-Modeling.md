# NLP Engine, Topic Modeling & Screening Filters

[Back to Wiki Home](file:///run/media/john/ssd%20external%20storage/git/bibliometric/docs/wiki/Home.md)

---

## Overview

The NLP and paper screening engines ([src/core/nlp.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/nlp.py) and [src/core/screening.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/screening.py)) extract thematic topics, track keyword growth rates, and filter out irrelevant or noisy papers.

---

## 1. BERTopic Modeling

Using **BERTopic** (transformer embeddings + UMAP + HDBSCAN + c-TF-IDF), the pipeline clusters paper abstracts into coherent research topics.

### Key Outputs
Output File | Content Description
--- | ---
`topic_info.csv` | Topic IDs, document counts, top keyword representations, and topic labels.
`topic_research_lines.csv` | Extracted core research themes and dominant paradigms.
`keywords_cagr.csv` | Compound Annual Growth Rate (CAGR) per keyword over the dataset year range.

---

## 2. Keyword CAGR Calculation

The Compound Annual Growth Rate (CAGR) measures the annual growth rate of keyword occurrences between start year ($Y_{start}$) and end year ($Y_{end}$):

$$\text{CAGR} = \left( \frac{\text{Count}_{Y_{end}}}{\text{Count}_{Y_{start}}} \right)^{\frac{1}{Y_{end} - Y_{start}}} - 1$$

Keywords with high positive CAGR represent emerging research frontiers.

---

## 3. Paper Screening Filters

[src/core/screening.py](file:///run/media/john/ssd%20external%20storage/git/bibliometric/src/core/screening.py) provides automated relevance filtering:

### Option 1: Embedding Semantic Search (`--screen-embeddings`)
- Computes cosine similarity between paper titles/abstracts and the search query embedding using `sentence-transformers`.
- Filters out records falling below `--embedding-threshold 0.35`.

### Option 2: LLM Zero-Shot Classification (`--screen-llm`)
- Uses local **Ollama** LLM (e.g., `--llm-model llama3.2:3b`) to classify papers.
- Evaluates domain relevance and tags papers with noise paradigms.
