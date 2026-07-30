import os
import sys
import pandas as pd
import logging

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.collection import UnifiedCollector
from src.core.scrapers import DBLPCollector, SpringerCollector

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("EnrichAndMerge")

def main():
    base_file = "data/collected_EEG_OR_Electroencephalography_OR_Brainwave_Monito.csv"
    if not os.path.exists(base_file):
        logger.error(f"Base dataset {base_file} not found!")
        return

    logger.info(f"Loading base dataset: {base_file}...")
    base_df = pd.read_csv(base_file)
    initial_count = len(base_df)
    logger.info(f"Base dataset loaded with {initial_count:,} papers.")

    query = "EEG OR Electroencephalography OR Brainwave"

    collected_dfs = [base_df]

    # Fetch DBLP
    try:
        logger.info("Fetching additional papers from DBLP...")
        dblp = DBLPCollector()
        dblp_df = dblp.fetch_papers(query, limit=500)
        if not dblp_df.empty:
            logger.info(f"Fetched {len(dblp_df):,} papers from DBLP.")
            collected_dfs.append(dblp_df)
    except Exception as e:
        logger.error(f"DBLP fetch failed: {e}")

    # Fetch Springer
    try:
        logger.info("Fetching additional papers from Springer...")
        springer = SpringerCollector()
        springer_df = springer.fetch_papers(query, limit=500)
        if not springer_df.empty:
            logger.info(f"Fetched {len(springer_df):,} papers from Springer.")
            collected_dfs.append(springer_df)
    except Exception as e:
        logger.error(f"Springer fetch failed: {e}")

    # Combine all
    logger.info("Combining all datasets for Union-Find deduplication...")
    combined_raw = pd.concat(collected_dfs, ignore_index=True)
    logger.info(f"Combined raw papers before deduplication: {len(combined_raw):,}")

    # Instantiate UnifiedCollector to reuse Union-Find deduplication engine
    unified = UnifiedCollector()
    
    # Run Union-Find deduplication across DOI and Title
    merged_df = unified.deduplicate_dataframe(combined_raw)

    output_path = "data/collected_EEG_expanded_merged.csv"
    merged_df.to_csv(output_path, index=False)

    logger.info("=" * 60)
    logger.info(f"SUCCESS: Merged & deduplicated dataset saved to {output_path}")
    logger.info(f"Initial paper count:     {initial_count:,}")
    logger.info(f"Final merged paper count: {len(merged_df):,}")
    logger.info(f"Net new unique papers:    {len(merged_df) - initial_count:,}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
