import os
import logging
import pandas as pd
from src.core.collection import UnifiedCollector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("33k_full_run")

def main():
    query_file = "data/original_33k_query.txt"
    if not os.path.exists(query_file):
        raise FileNotFoundError(f"Query file {query_file} not found!")

    with open(query_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        query = " ".join(lines)

    logger.info("=== STARTING FULL 33K QUERY COLLECTION (2014 - 2026) ===")
    logger.info(f"Query length: {len(query)} characters")
    logger.info(f"Query: {query[:120]}...")

    start_year = 2014
    end_year = 2026
    
    config = {
        "openalex_email": os.environ.get("OPENALEX_EMAIL", "researcher@example.com"),
        "ieee_api_key": "bf2ff295fw2cfysbx3v5evuk",
    }
    
    collector = UnifiedCollector(config=config)
    
    # Target peer-reviewed sources
    sources = ["openalex", "ieee", "semantic_scholar", "pubmed"]
    logger.info(f"Target sources: {sources}")
    
    # Fetch data (unlimited/max per source)
    full_df = collector.fetch_all(
        query=query,
        limit_per_source=0, # 0 means max/unlimited pagination
        sources=sources,
        start_year=start_year,
        end_year=end_year
    )
    
    logger.info(f"Collection and deduplication complete! Total unique papers retrieved: {len(full_df)}")
    
    # Save standalone expanded dataset
    expanded_path = "data/collected_EEG_expanded_33k_2014_2026.csv"
    full_df.to_csv(expanded_path, index=False)
    logger.info(f"Saved expanded dataset to {expanded_path}")
    
    # Merge into Master Dataset
    master_path = "data/collected_EEG_master_merged.csv"
    if os.path.exists(master_path):
        existing_master = pd.read_csv(master_path, low_memory=False)
        combined = pd.concat([existing_master, full_df], ignore_index=True)
        final_master = collector.deduplicate_dataframe(combined)
    else:
        final_master = full_df
        
    final_master.to_csv(master_path, index=False)
    logger.info(f"Updated Master Dataset ({master_path}) now contains {len(final_master)} unique records.")

if __name__ == "__main__":
    main()
