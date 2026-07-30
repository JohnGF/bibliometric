import os
import sys
import pandas as pd
import logging

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.collection import UnifiedCollector

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MergeMaster")

def main():
    file_18k = "data/collected_EEG_OR_Electroencephalography_OR_Brainwave_Monito.csv"
    file_33k = "data/collected_EEG_expanded_33k.csv"

    if not os.path.exists(file_18k) or not os.path.exists(file_33k):
        logger.error("Missing input files for master merge!")
        return

    logger.info("Loading 18k dataset...")
    df_18k = pd.read_csv(file_18k)
    logger.info(f"Loaded {len(df_18k):,} papers from 18k dataset.")

    logger.info("Loading 33k dataset...")
    df_33k = pd.read_csv(file_33k)
    logger.info(f"Loaded {len(df_33k):,} papers from 33k dataset.")

    # Combine both
    logger.info("Combining datasets...")
    combined_raw = pd.concat([df_18k, df_33k], ignore_index=True)
    logger.info(f"Total raw papers combined: {len(combined_raw):,}")

    # Deduplicate
    logger.info("Running Union-Find deduplication engine...")
    unified = UnifiedCollector()
    deduplicated_df = unified.deduplicate_dataframe(combined_raw)

    output_path = "data/collected_EEG_master_merged.csv"
    deduplicated_df.to_csv(output_path, index=False)

    logger.info("=" * 60)
    logger.info(f"SUCCESS: Master merged dataset saved to {output_path}")
    logger.info(f"18k dataset count:         {len(df_18k):,}")
    logger.info(f"33k dataset count:         {len(df_33k):,}")
    logger.info(f"Final unique paper count:  {len(deduplicated_df):,}")
    logger.info(f"Overlap papers removed:    {len(combined_raw) - len(deduplicated_df):,}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
