import argparse
import os
import sys
import logging
import pandas as pd

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.collection import UnifiedCollector
from src.pipeline import BibliometricPipeline
from src.core.latex_exporter import LaTeXExporter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("project_orchestrator")

def main():
    parser = argparse.ArgumentParser(description="Run a full bibliometric project pipeline.")
    parser.add_argument("--project-dir", type=str, required=True, help="Path to the project directory")
    parser.add_argument("--limit", type=int, default=100, help="Limit per source for collection (set to 0 for unlimited)")
    parser.add_argument("--start-year", type=int, help="Start year for collection")
    parser.add_argument("--end-year", type=int, help="End year for collection")
    parser.add_argument("--skip-collection", action="store_true", help="Skip data collection and only run analysis on existing data")
    parser.add_argument("--skip-scaffold", action="store_true", help="Skip LaTeX scaffold generation")

    args = parser.parse_args()

    project_dir = args.project_dir
    data_dir = os.path.join(project_dir, "data")
    results_dir = os.path.join(project_dir, "results")
    query_file = os.path.join(data_dir, "query.txt")
    dataset_file = os.path.join(data_dir, "collected_papers.csv")

    # Ensure directories exist
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    # Setup query file
    if not os.path.exists(query_file) and not args.skip_collection:
        logger.info(f"Query file not found at {query_file}. Creating an empty one.")
        with open(query_file, "w", encoding="utf-8") as f:
            f.write("brain-computer interface\n")
        logger.warning(f"Created a default query file at {query_file}. Please update it with your desired query and re-run.")
        return

    if not args.skip_collection:
        logger.info(f"=== PHASE 1: DATA COLLECTION ===")
        with open(query_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
            query = " ".join(lines)

        logger.info(f"Loaded Query: {query}")

        config = {
            "openalex_email": os.environ.get("OPENALEX_EMAIL", "researcher@example.com"),
        }

        # Add API keys if present in env
        for key in ["IEEE_API_KEY", "SS_API_KEY", "SCOPUS_API_KEY", "PUBMED_API_KEY", "WOS_API_KEY"]:
            if key in os.environ:
                config[key.lower()] = os.environ[key]

        collector = UnifiedCollector(config=config)
        sources = ["openalex", "semantic_scholar"] # Default sources

        # Optionally allow fetching from all by adding more sources based on available keys

        try:
            logger.info("Fetching data...")
            full_df = collector.fetch_all(
                query=query,
                limit_per_source=args.limit,
                sources=sources,
                start_year=args.start_year,
                end_year=args.end_year
            )

            logger.info(f"Collection complete. Deduplicating {len(full_df)} records...")
            final_df = collector.deduplicate_dataframe(full_df)

            final_df.to_csv(dataset_file, index=False)
            logger.info(f"Saved {len(final_df)} unique records to {dataset_file}")

        except Exception as e:
            logger.error(f"Error during data collection: {e}")
            return
    else:
        logger.info("Skipping collection phase.")
        if not os.path.exists(dataset_file):
            logger.error(f"Cannot skip collection: dataset file not found at {dataset_file}")
            return

    logger.info(f"=== PHASE 2: PIPELINE ANALYSIS ===")

    # Initialize pipeline
    pipeline_config = {
        "screen_embeddings": False,
        "screen_llm": False,
    }

    pipeline = BibliometricPipeline(output_dir=results_dir, config=pipeline_config)

    try:
        # Run pipeline
        pipeline.run(file_path=dataset_file)
        logger.info(f"Pipeline analysis complete. Results saved to {results_dir}")
    except Exception as e:
        logger.error(f"Error during pipeline execution: {e}")
        return

    if not args.skip_scaffold:
        logger.info(f"=== PHASE 3: PAPER SCAFFOLD GENERATION ===")
        try:
            exporter = LaTeXExporter(results_dir)
            exporter.export_all()
            logger.info(f"LaTeX scaffold generated in {results_dir}")
        except Exception as e:
            logger.error(f"Error generating LaTeX scaffold: {e}")

    logger.info("=== PROJECT EXECUTION COMPLETE ===")
    logger.info(f"Check {results_dir} for network_cocitations.csv and other outputs.")

if __name__ == "__main__":
    main()
