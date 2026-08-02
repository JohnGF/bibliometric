import os
import logging
import pandas as pd
from src.core.collection import UnifiedCollector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("missing_years_run")

def main():
    query_file = "data/original_33k_query.txt"
    if not os.path.exists(query_file):
        raise FileNotFoundError(f"Query file {query_file} not found!")

    with open(query_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        query = " ".join(lines)

    start_year = 2025
    end_year = 2026
    
    logger.info(f"=== FETCHING MISSING YEARS ({start_year} - {end_year}) FOR STRICT 33K QUERY ===")
    logger.info(f"Query: {query[:120]}...")

    config = {
        "openalex_email": os.environ.get("OPENALEX_EMAIL", "researcher@example.com"),
        "ieee_api_key": "bf2ff295fw2cfysbx3v5evuk",
    }
    
    collector = UnifiedCollector(config=config)
    sources = ["openalex", "ieee", "semantic_scholar", "pubmed"]
    logger.info(f"Target sources: {sources}")
    
    # Fetch 2025-2026 papers for the 33k query
    new_df = collector.fetch_all(
        query=query,
        limit_per_source=0, # Max records for 2025-2026
        sources=sources,
        start_year=start_year,
        end_year=end_year
    )
    
    logger.info(f"Fetched {len(new_df)} unique new papers for {start_year}-{end_year}.")
    
    # Save standalone 2025-2026 dataset
    recent_path = "data/collected_EEG_2025_2026.csv"
    new_df.to_csv(recent_path, index=False)
    logger.info(f"Saved recent dataset to {recent_path}")
    
    # Load strict 33k dataset for 2014-2024
    strict_2014_2024_path = "data/collected_EEG_expanded_33k.csv"
    if os.path.exists(strict_2014_2024_path):
        base_33k_df = pd.read_csv(strict_2014_2024_path, low_memory=False)
        logger.info(f"Loaded strict 2014-2024 33k query dataset ({len(base_33k_df)} papers).")
        combined = pd.concat([base_33k_df, new_df], ignore_index=True)
    else:
        combined = new_df
        
    logger.info("Running deduplication for strict 33k query dataset (2014-2026)...")
    final_strict_master = collector.deduplicate_dataframe(combined)
    
    # Overwrite master merged file so it contains STRICTLY the 33k query dataset
    master_path = "data/collected_EEG_master_merged.csv"
    final_strict_master.to_csv(master_path, index=False)
    
    # Also save as dedicated strict file
    strict_path = "data/collected_EEG_33k_strict_2014_2026.csv"
    final_strict_master.to_csv(strict_path, index=False)
    
    logger.info(f"SUCCESS! Master Dataset ({master_path}) is now STRICTLY the 33k query dataset containing {len(final_strict_master)} unique records for 2014-2026.")

if __name__ == "__main__":
    main()
