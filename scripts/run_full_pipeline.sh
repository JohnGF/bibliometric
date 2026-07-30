#!/bin/bash
# ==============================================================================
# BIBLIOMETRIC RESEARCH PIPELINE - COMPLETE CLI EXECUTION SCRIPT
# ==============================================================================
# This script executes the autonomous collection, deduplication, CUDA embedding
# screening, BERTopic modeling, and cuGraph network analysis for 2015-2026.
#
# FLAG DOCUMENTATION & PURPOSE:
# ------------------------------------------------------------------------------
# --query-file          : Path to text file containing search query (reads original 33k query)
# --start-year 2015     : Start year for paper collection
# --end-year 2026       : End year for paper collection
# --limit 0             : Limit per source (0 = UNLIMITED; uses year-by-year & cursor streaming)
# --screen-embeddings   : Enables GPU vector embedding semantic relevance filter (SentenceTransformers)
# --embedding-threshold : Cosine similarity cutoff threshold for relevance (0.35)
# --output              : Output directory where all PDFs, CSVs, and topic models are saved
# ==============================================================================

uv run biblio-pipeline \
  --query-file data/original_33k_query.txt \
  --start-year 2015 \
  --end-year 2026 \
  --limit 0 \
  --screen-embeddings \
  --embedding-threshold 0.35 \
  --output pipeline_results_manuscript_33k
