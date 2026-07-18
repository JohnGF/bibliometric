from typing import Optional, List
import polars as pl
import pandas as pd
from src.core.ingestion import load_data, validate_publications
from src.core.nlp import BERTopicPipeline
from src.core.network import NetworkAnalysis
from src.core.viz import Visualization
from src.core.collection import UnifiedCollector
from src.core.countries import CountryAnalysis
from src.core.citations import CitationsAnalysis
import os
import logging
import argparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class BibliometricPipeline:
    def __init__(self, output_dir: str = "pipeline_results", config: Optional[dict] = None):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.viz = Visualization()
        self.nlp = BERTopicPipeline()
        self.network = NetworkAnalysis()
        self.collector = UnifiedCollector(config=config)
        self.country_analyzer = CountryAnalysis()
        self.citation_analyzer = CitationsAnalysis()

    def run_with_query(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None):
        """Fetches data and then runs the pipeline."""
        logging.info(f"Starting autonomous collection for query: {query} (Years: {start_year}-{end_year})")
        df_pd = self.collector.fetch_all(query, limit_per_source=limit, start_year=start_year, end_year=end_year)
        
        if df_pd.empty:
            logging.error("No data found for the given query.")
            return
 
        # Save collected data
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        safe_query = query.replace(' ', '_').replace('/', '_')
        papers_path = os.path.join(data_dir, f"collected_{safe_query}.csv")
        df_pd.to_csv(papers_path, index=False)
        logging.info(f"Data saved to {papers_path}")
        
        return self.run(papers_path)

    def run(self, papers_path: str, refs_path: Optional[str] = None, config: Optional[dict] = None):
        logging.info(f"Starting pipeline for {papers_path}")
        # 1. Ingestion & Validation
        df_pd = load_data(papers_path)
        
        # Parse runtime configurations
        config = config or {}
        theme = config.get("theme", "whitegrid")
        top_n_countries = config.get("top_n_countries", 10)
        min_pub = config.get("min_publications", 1)
        
        # Re-initialize visualization style dynamically
        self.viz = Visualization(style=theme)
        
        # Check if this is a references dataset
        is_references_dataset = "source" in df_pd.columns and "destination" in df_pd.columns
        
        if is_references_dataset:
            logging.info("Detected references dataset. Running co-citation and coupling analysis...")
            cocit_df, X = self.citation_analyzer.calculate_co_citation(df_pd)
            cocit_df.to_csv(os.path.join(self.output_dir, "network_cocitations.csv"), index=False)
            
            # Run percolation threshold analysis on co-citation network
            if not cocit_df.empty:
                logging.info("Running co-citation percolation threshold analysis...")
                try:
                    percolation_df = self.citation_analyzer.perform_percolation_analysis(
                        cocit_df, 'cited_1', 'cited_2', 'co_citation_count'
                    )
                    if not percolation_df.empty:
                        percolation_df.to_csv(os.path.join(self.output_dir, "percolation_results.csv"), index=False)
                        logging.info("Generating static co-citation percolation analysis PDF graph...")
                        self.viz.plot_percolation(
                            percolation_df, 'co_citation_count',
                            save_path=os.path.join(self.output_dir, "percolation_analysis.pdf")
                        )
                except Exception as e:
                    logging.exception(f"Error during percolation analysis: {e}")

            if X is not None:
                # Clean source names to align with factorized sparse matrix rows
                df_clean = df_pd[['source', 'destination']].dropna().drop_duplicates(subset=['source', 'destination'])
                source_codes, source_uniques = pd.factorize(df_clean['source'])
                coupling_df = self.citation_analyzer.calculate_bibliographic_coupling(X, source_uniques)
                coupling_df.to_csv(os.path.join(self.output_dir, "network_coupling.csv"), index=False)
                
            logging.info(f"References analysis complete. Outputs written to {self.output_dir}")
            return
            
        # Standard publication dataset validation
        validate_publications(df_pd)
        df = pl.from_pandas(df_pd)
        df = df.filter(pl.col("Year").is_not_null())
        
        # 2. Basic Visualization (Growth)
        logging.info("Generating yearly growth charts...")
        self.viz.plot_yearly_growth(df, save_path=os.path.join(self.output_dir, "yearly_growth.pdf"))
        
        # 3. Country Evolution Analysis
        if "Affiliations" in df_pd.columns:
            logging.info("Running country evolution analysis...")
            exploded_pub, country_ev = self.country_analyzer.process_countries(df)
            if not country_ev.empty:
                country_ev.to_csv(os.path.join(self.output_dir, "country_evolution.csv"), index=False)
                self.viz.plot_country_evolution(country_ev, top_n=top_n_countries, save_path=os.path.join(self.output_dir, "country_evolution.pdf"))

        # 4. Keyword CAGR Analysis
        if "Author Keywords" in df_pd.columns:
            logging.info("Running keyword CAGR analysis...")
            try:
                kw_df = self.nlp.preprocess_keywords(df, column="Author Keywords")
                if not kw_df.is_empty():
                    kw_counts = kw_df.group_by(["Year", "standardized_word"]).len().rename({"len": "count"})
                    cagr_df = self.nlp.calculate_cagr(kw_counts, count_col="count", year_col="Year")
                    if not cagr_df.is_empty():
                        cagr_pandas = cagr_df.to_pandas()
                        cagr_pandas.to_csv(os.path.join(self.output_dir, "keywords_cagr.csv"), index=False)
                        self.viz.plot_keywords_cagr(cagr_pandas, save_path=os.path.join(self.output_dir, "keywords_cagr.pdf"))
            except Exception as e:
                logging.error(f"Failed to run keyword CAGR analysis: {e}")

        # 5. NLP (Topics)
        logging.info("Running BERTopic modeling...")
        docs = df["Abstract"].drop_nulls().to_list()
        # BERTopic requires at least 10 documents to cluster successfully
        if len(docs) >= 10:
            topics, probs = self.nlp.fit_model(docs)
            topic_info = self.nlp.get_topics()
            if topic_info is not None:
                topic_info.to_csv(os.path.join(self.output_dir, "topic_info.csv"), index=False)
                self.viz.plot_topic_distribution(topic_info, save_path=os.path.join(self.output_dir, "topic_word_scores.pdf"))
            
            # Generate and save high-level Research Lines
            logging.info("Generating high-level Research Lines...")
            research_lines = self.nlp.get_research_lines(nr_clusters=5)
            if not research_lines.empty:
                research_lines.to_csv(os.path.join(self.output_dir, "topic_research_lines.csv"), index=False)
        else:
            logging.warning(f"Too few abstracts ({len(docs)}) for topic modeling. Skipping BERTopic.")
            
        # 6. Network Analysis (Co-authorship)
        edges_df, node_meta = self.network.build_co_authorship_graph(df)
        
        # Ensure outputs are CSV compatible (convert to pandas if they are cudf/polars)
        if hasattr(edges_df, "to_pandas"):
            edges_df = edges_df.to_pandas()
        if hasattr(node_meta, "to_pandas"):
            node_meta = node_meta.to_pandas()

        # Apply min publications filter if specified in config
        if min_pub > 1 and not node_meta.empty:
            logging.info(f"Filtering co-authorship network with min_publications >= {min_pub}...")
            node_meta = node_meta[node_meta['num_publications'] >= min_pub]
            valid_vertices = set(node_meta['vertex'])
            edges_df = edges_df[edges_df['source_id'].isin(valid_vertices) & edges_df['dest_id'].isin(valid_vertices)]

        edges_df.to_csv(os.path.join(self.output_dir, "network_edges.csv"), index=False)
        node_meta.to_csv(os.path.join(self.output_dir, "network_nodes.csv"), index=False)
        
        # Renders the publication-ready co-authorship Network PDF graph
        if not edges_df.empty and not node_meta.empty:
            logging.info("Generating static co-authorship network PDF graph...")
            self.viz.plot_network(edges_df, node_meta, save_path=os.path.join(self.output_dir, "network_graph.pdf"))
        
        logging.info(f"Pipeline complete. All results saved to {self.output_dir}")

def main():
    parser = argparse.ArgumentParser(description="Bibliometric Research Pipeline CLI")
    parser.add_argument("--file", type=str, help="Path to local CSV/Parquet file")
    parser.add_argument("--query", type=str, help="Search query for autonomous collection")
    parser.add_argument("--limit", type=int, default=100, help="Limit per source for autonomous collection")
    parser.add_argument("--start-year", type=int, help="Start year for collection")
    parser.add_argument("--end-year", type=int, help="End year for collection")
    parser.add_argument("--output", type=str, default="pipeline_results", help="Output directory")
    parser.add_argument("--openalex-email", type=str, help="Email for OpenAlex polite pool")
    parser.add_argument("--ss-api-key", type=str, help="API Key for Semantic Scholar")
    parser.add_argument("--crossref-email", type=str, help="Email for Crossref User-Agent")

    args = parser.parse_args()
    
    config = {}
    if args.openalex_email:
        config["openalex_email"] = args.openalex_email
    if args.ss_api_key:
        config["ss_api_key"] = args.ss_api_key
    if args.crossref_email:
        config["crossref_email"] = args.crossref_email

    pipeline = BibliometricPipeline(output_dir=args.output, config=config)

    if args.query:
        pipeline.run_with_query(args.query, limit=args.limit, start_year=args.start_year, end_year=args.end_year)
    elif args.file:
        pipeline.run(args.file)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
