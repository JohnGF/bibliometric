import os
import sys
import pandas as pd
import logging

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.collection import UnifiedCollector
from src.core.scrapers import DBLPCollector, SpringerCollector

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CollectAndMerge33k")

def main():
    query_file = "data/original_33k_query.txt"
    if not os.path.exists(query_file):
        logger.error(f"Query file {query_file} not found!")
        return

    with open(query_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        query = " ".join(lines)

    logger.info(f"Loaded 33k query string:\n{query}\n")

    # Load existing broad dataset as base
    base_file = "data/collected_EEG_OR_Electroencephalography_OR_brain_wave_OR_br.csv"
    if os.path.exists(base_file):
        logger.info(f"Loading base dataset: {base_file}...")
        base_df = pd.read_csv(base_file)
        initial_count = len(base_df)
        logger.info(f"Base dataset loaded with {initial_count:,} papers.")
    else:
        logger.info("No base dataset found. Starting fresh collection.")
        base_df = pd.DataFrame()
        initial_count = 0

    collected_dfs = [base_df] if not base_df.empty else []

    # Initialize UnifiedCollector
    unified = UnifiedCollector()

    # 1. Fetch OpenAlex using the proper Boolean query
    try:
        logger.info("Fetching papers from OpenAlex (limit=45000)...")
        oa_df = unified.collectors["openalex"].fetch_papers(query, limit=45000)
        if not oa_df.empty:
            logger.info(f"Fetched {len(oa_df):,} papers from OpenAlex.")
            collected_dfs.append(oa_df)
    except Exception as e:
        logger.error(f"OpenAlex fetch failed: {e}")

    # 2. Fetch Semantic Scholar
    try:
        logger.info("Fetching papers from Semantic Scholar (limit=20000)...")
        ss_df = unified.collectors["semantic_scholar"].fetch_papers(query, limit=20000)
        if not ss_df.empty:
            logger.info(f"Fetched {len(ss_df):,} papers from Semantic Scholar.")
            collected_dfs.append(ss_df)
    except Exception as e:
        logger.error(f"Semantic Scholar fetch failed: {e}")

    # 3. Fetch IEEE (via OpenAlex or Official API)
    try:
        logger.info("Fetching papers from IEEE (limit=10000)...")
        ieee_df = unified.collectors["ieee"].fetch_papers(query, limit=10000)
        if not ieee_df.empty:
            logger.info(f"Fetched {len(ieee_df):,} papers from IEEE.")
            collected_dfs.append(ieee_df)
    except Exception as e:
        logger.error(f"IEEE fetch failed: {e}")

    # 4. Fetch ACM
    try:
        logger.info("Fetching papers from ACM (limit=10000)...")
        acm_df = unified.collectors["acm"].fetch_papers(query, limit=10000)
        if not acm_df.empty:
            logger.info(f"Fetched {len(acm_df):,} papers from ACM.")
            collected_dfs.append(acm_df)
    except Exception as e:
        logger.error(f"ACM fetch failed: {e}")

    # 5. Fetch DBLP
    try:
        logger.info("Fetching papers from DBLP (limit=10000)...")
        dblp = DBLPCollector()
        dblp_df = dblp.fetch_papers(query, limit=10000)
        if not dblp_df.empty:
            logger.info(f"Fetched {len(dblp_df):,} papers from DBLP.")
            collected_dfs.append(dblp_df)
    except Exception as e:
        logger.error(f"DBLP fetch failed: {e}")

    # 6. Fetch Springer
    try:
        logger.info("Fetching papers from Springer (limit=10000)...")
        springer = SpringerCollector()
        springer_df = springer.fetch_papers(query, limit=10000)
        if not springer_df.empty:
            logger.info(f"Fetched {len(springer_df):,} papers from Springer.")
            collected_dfs.append(springer_df)
    except Exception as e:
        logger.error(f"Springer fetch failed: {e}")

    # Combine all
    logger.info("Combining all raw papers for Union-Find deduplication...")
    combined_raw = pd.concat(collected_dfs, ignore_index=True)
    logger.info(f"Combined raw papers before deduplication: {len(combined_raw):,}")

    # Run Union-Find deduplication across DOI and Title
    merged_df = unified.deduplicate_dataframe(combined_raw)

    output_path = "data/collected_EEG_expanded_33k.csv"
    merged_df.to_csv(output_path, index=False)

    logger.info("=" * 60)
    logger.info(f"SUCCESS: Expanded 33k dataset saved to {output_path}")
    logger.info(f"Initial paper count:     {initial_count:,}")
    logger.info(f"Final merged paper count: {len(merged_df):,}")
    logger.info(f"Net new unique papers:    {len(merged_df) - initial_count:,}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
