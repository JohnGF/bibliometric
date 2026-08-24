import logging
import argparse
import os
from src.orchestrators.pipeline_manager import PipelineManager

def main():
    parser = argparse.ArgumentParser(description="Bibliometric Research Pipeline CLI")
    parser.add_argument("--file", type=str, help="Path to local CSV/Parquet file")
    parser.add_argument("--refs-file", type=str, help="Path to external references CSV file")
    parser.add_argument("--query", type=str, help="Search query for autonomous collection")
    parser.add_argument("--query-file", type=str, help="Path to text file containing search query")
    parser.add_argument("--limit", type=int, default=100, help="Limit per source for collection")
    parser.add_argument("--start-year", type=int, help="Start year for collection")
    parser.add_argument("--end-year", type=int, help="End year for collection")
    parser.add_argument("--output", type=str, default="pipeline_results", help="Output directory")
    parser.add_argument("--openalex-email", type=str, help="Email for OpenAlex polite pool")
    parser.add_argument("--ss-api-key", type=str, help="API Key for Semantic Scholar")
    parser.add_argument("--crossref-email", type=str, help="Email for Crossref User-Agent")
    parser.add_argument("--pubmed-api-key", type=str, help="API Key for PubMed (optional)")
    parser.add_argument("--scopus-api-key", type=str, help="API Key for Elsevier Scopus")
    parser.add_argument("--scopus-inst-token", type=str, help="Institutional Token for Scopus (optional)")
    parser.add_argument("--wos-api-key", type=str, help="API Key for Web of Science")

    # Paper Screening & Source Options
    parser.add_argument("--screen-embeddings", action="store_true", help="Enable Option 1: Embedding semantic relevance filter")
    parser.add_argument("--embedding-threshold", type=float, default=0.35, help="Similarity threshold for embedding filter")
    parser.add_argument("--screen-llm", action="store_true", help="Enable Option 2: LLM zero-shot classification")
    parser.add_argument("--llm-model", type=str, default="llama3.2:3b", help="Model name for Ollama LLM screening")
    parser.add_argument("--include-preprints", action="store_true", help="Include preprints from arXiv and bioRxiv")

    # Modular Stage Control Options
    parser.add_argument("--top-per-community", type=int, default=1, help="Top N representative author leaders per community")
    parser.add_argument("--min-publications", type=int, default=1, help="Minimum publications threshold for network node inclusion")
    parser.add_argument("--stages", type=str, help="Comma-separated list of stages to run (options: growth,country,cagr,nlp,network,percolation)")
    parser.add_argument("--skip-nlp", action="store_true", help="Skip BERTopic modeling stage")
    parser.add_argument("--skip-network", action="store_true", help="Skip co-authorship network stage")
    parser.add_argument("--skip-cagr", action="store_true", help="Skip keyword CAGR stage")
    parser.add_argument("--skip-country", action="store_true", help="Skip country evolution stage")
    parser.add_argument("--skip-percolation", action="store_true", help="Skip percolation analysis stage")


    # Project Orchestration Options
    parser.add_argument("--project-dir", type=str, help="Path to project directory for end-to-end orchestration")
    parser.add_argument("--skip-collection", action="store_true", help="Skip data collection when running a project")

    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive graph parameter editor REPL session")

    # Meta-Analysis Options
    parser.add_argument("--meta-analysis", action="store_true", help="Run full-text PDF parsing, extraction, and meta-analysis stats")
    parser.add_argument("--picos-config", type=str, help="Path to PICOS configuration JSON file")

    args = parser.parse_args()

    if args.interactive:
        from scripts.interactive_viz import InteractiveVizSession
        session = InteractiveVizSession(output_dir=args.output)
        session.run_menu()
        return

    active_query = args.query
    if args.query_file and os.path.exists(args.query_file):
        with open(args.query_file, "r", encoding="utf-8") as qf:
            lines = [l.strip() for l in qf if l.strip() and not l.strip().startswith("#")]
            active_query = " ".join(lines)

    config = {}
    if args.openalex_email: config["openalex_email"] = args.openalex_email
    if args.ss_api_key: config["ss_api_key"] = args.ss_api_key
    if args.crossref_email: config["crossref_email"] = args.crossref_email
    if args.pubmed_api_key: config["pubmed_api_key"] = args.pubmed_api_key
    if args.scopus_api_key: config["scopus_api_key"] = args.scopus_api_key
    if args.scopus_inst_token: config["scopus_inst_token"] = args.scopus_inst_token
    if args.wos_api_key: config["wos_api_key"] = args.wos_api_key

    config["screen_embeddings"] = args.screen_embeddings
    config["embedding_threshold"] = args.embedding_threshold
    config["screen_llm"] = args.screen_llm
    config["llm_model"] = args.llm_model
    config["include_preprints"] = args.include_preprints

    if args.stages:
        config["stages"] = [s.strip().lower() for s in args.stages.split(",")]
    config["top_per_community"] = args.top_per_community
    config["min_publications"] = args.min_publications
    config["skip_nlp"] = args.skip_nlp
    config["skip_network"] = args.skip_network
    config["skip_cagr"] = args.skip_cagr
    config["skip_country"] = args.skip_country
    config["skip_percolation"] = args.skip_percolation
    config["meta_analysis"] = args.meta_analysis
    config["picos_config"] = args.picos_config


    manager = PipelineManager(output_dir=args.output, config=config)

    if args.project_dir:
        logger = logging.getLogger("project_orchestrator")
        project_dir = args.project_dir
        data_dir = os.path.join(project_dir, "data")
        results_dir = os.path.join(project_dir, "results")
        query_file = os.path.join(data_dir, "query.txt")
        dataset_file = os.path.join(data_dir, "collected_papers.csv")

        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(results_dir, exist_ok=True)

        # Redirect manager output
        manager.output_dir = results_dir
        manager.analysis_orch.output_dir = results_dir

        if not args.skip_collection:
            if not os.path.exists(query_file):
                logger.info(f"Query file not found at {query_file}. Creating an empty one.")
                with open(query_file, "w", encoding="utf-8") as f:
                    f.write("brain-computer interface\n")
                logger.warning(f"Created a default query file at {query_file}. Please update it with your desired query and re-run.")
                return

            logger.info("=== PHASE 1: DATA COLLECTION ===")
            with open(query_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
                project_query = " ".join(lines)

            logger.info(f"Fetching data for project query: {project_query}")

            # Use unified collector manually to enforce the exact project path
            from src.core.collection import UnifiedCollector
            collector = UnifiedCollector(config=config)
            df_pd = collector.fetch_all(
                query=project_query,
                limit_per_source=args.limit,
                start_year=args.start_year,
                end_year=args.end_year
            )
            df_pd = collector.deduplicate_dataframe(df_pd)
            df_pd.to_csv(dataset_file, index=False)
            logger.info(f"Data saved to {dataset_file}")

        if not os.path.exists(dataset_file):
            logger.error(f"Cannot proceed: {dataset_file} not found.")
            return

        logger.info("=== PHASE 2: PIPELINE ANALYSIS ===")
        manager.run(dataset_file, refs_path=args.refs_file)

        logger.info("=== PROJECT EXECUTION COMPLETE ===")
        return

    if active_query:

        manager.run_with_query(active_query, limit=args.limit, start_year=args.start_year, end_year=args.end_year)
    elif args.file:
        manager.run(args.file, refs_path=args.refs_file)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
