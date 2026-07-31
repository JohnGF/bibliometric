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
from src.core.screening import PaperScreener
from src.core.latex_exporter import LaTeXExporter
import os
import logging
import argparse

import time

# Auto-load .env if present
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                if key.strip() not in os.environ:
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def _print_stage_summary(title: str, bullets: List[str], elapsed_sec: Optional[float] = None):
    """Prints a clean ASCII bullet-point summary box to stdout with optional stage execution timing."""
    time_header = f" (Execution: {elapsed_sec:.2f}s)" if elapsed_sec is not None else ""
    header = f"=== ANALYSIS SUMMARY: {title}{time_header} ==="
    border = "=" * max(len(header), 65)
    print(f"\n{border}\n{header}\n{border}")
    for bullet in bullets:
        print(f"  * {bullet}")
    if elapsed_sec is not None:
        print(f"  * Stage Execution Time: {elapsed_sec:.2f} seconds ({elapsed_sec/60:.2f} min)")
    print(f"{border}\n")

class BibliometricPipeline:
    def __init__(self, output_dir: str = "pipeline_results", config: Optional[dict] = None):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.config = config or {}
        self.viz = Visualization()
        self.nlp = BERTopicPipeline()
        self.network = NetworkAnalysis()
        self.collector = UnifiedCollector(config=self.config)
        self.country_analyzer = CountryAnalysis()
        self.citation_analyzer = CitationsAnalysis()
        
        # Screening configuration (Option 1: Embeddings, Option 2: LLM)
        config = self.config
        use_screen_emb = config.get("screen_embeddings", False)
        use_screen_llm = config.get("screen_llm", False)
        emb_threshold = config.get("embedding_threshold", 0.35)
        llm_model = config.get("llm_model", "llama3.2:3b")
        
        if use_screen_emb or use_screen_llm:
            self.screener = PaperScreener(
                use_embedding_filter=use_screen_emb,
                embedding_threshold=emb_threshold,
                use_llm_categorization=use_screen_llm,
                llm_model=llm_model
            )
        else:
            self.screener = None

    def run_with_query(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None):
        """Fetches data and then runs the pipeline."""
        logging.info(f"Starting autonomous collection for query: {query} (Years: {start_year}-{end_year})")
        df_pd = self.collector.fetch_all(query, limit_per_source=limit, start_year=start_year, end_year=end_year)
        
        if df_pd.empty:
            logging.error("No data found for the given query.")
            return
 
        if self.screener:
            logging.info("Applying automated paper screening...")
            df_pd = self.screener.screen(df_pd)
            if df_pd.empty:
                logging.error("No papers retained after screening.")
                return

        # Save collected data
        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        import re
        safe_query = re.sub(r'[^a-zA-Z0-9_\-]', '_', query)
        safe_query = re.sub(r'_+', '_', safe_query)[:50].strip('_')
        papers_path = os.path.join(data_dir, f"collected_{safe_query}.csv")
        df_pd.to_csv(papers_path, index=False)
        logging.info(f"Data saved to {papers_path}")
        
        return self.run(papers_path)

    def run(self, papers_path: str, refs_path: Optional[str] = None, config: Optional[dict] = None):
        logging.info(f"Starting pipeline for {papers_path}")
        # 1. Ingestion & Validation
        df_pd = load_data(papers_path)
        
        if self.screener:
            logging.info("Applying automated paper screening on input file...")
            df_pd = self.screener.screen(df_pd)
            if df_pd.empty:
                logging.error("No papers retained after screening.")
                return
        
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
        df = df.with_columns(pl.col("Year").cast(pl.Int64))
        
        # 2. Basic Visualization (Growth)
        stages = config.get("stages", None)
        skip_nlp = config.get("skip_nlp", False)
        skip_network = config.get("skip_network", False)
        skip_country = config.get("skip_country", False)
        skip_cagr = config.get("skip_cagr", False)
        skip_percolation = config.get("skip_percolation", False)
        
        def should_run(stage_name: str, skip_flag: bool) -> bool:
            if skip_flag:
                return False
            if stages is not None:
                return stage_name in stages
            return True

        t_pipeline_start = time.time()

        if should_run("growth", False):
            t_stage = time.time()
            logging.info("Generating yearly growth charts and 2026 projections...")
            growth_df = self.viz.plot_yearly_growth(df, save_path=os.path.join(self.output_dir, "yearly_growth.pdf"))
            if growth_df is not None and not growth_df.empty:
                growth_df.to_csv(os.path.join(self.output_dir, "yearly_growth.csv"), index=False)
                total_pubs = int(growth_df["len"].sum())
                min_yr = int(growth_df["Year"].min())
                max_yr = int(growth_df["Year"].max())
                peak_idx = growth_df["len"].idxmax()
                peak_row = growth_df.loc[peak_idx]
                bullets = [
                    f"Total Publications: {total_pubs:,} across years {min_yr} to {max_yr}",
                    f"Peak Publication Year: {int(peak_row['Year'])} ({int(peak_row['len']):,} publications)",
                ]
                if "is_projected" in growth_df.columns and growth_df["is_projected"].any():
                    proj_row = growth_df[growth_df["is_projected"]].iloc[0]
                    bullets.append(f"Current Year ({int(proj_row['Year'])}): {int(proj_row['len']):,} YTD (Projected Full Year: {int(proj_row['projected_len']):,})")
                _print_stage_summary("Yearly Growth & Projections", bullets, elapsed_sec=time.time() - t_stage)
        
        # 3. Country Evolution Analysis
        if should_run("country", skip_country) and "Affiliations" in df_pd.columns:
            t_stage = time.time()
            logging.info("Running country evolution analysis...")
            exploded_pub, country_ev = self.country_analyzer.process_countries(df)
            if not country_ev.empty:
                country_ev.to_csv(os.path.join(self.output_dir, "country_evolution.csv"), index=False)
                self.viz.plot_country_evolution(country_ev, top_n=top_n_countries, save_path=os.path.join(self.output_dir, "country_evolution.pdf"))
                self.viz.plot_country_choropleth_map(country_ev, save_path=os.path.join(self.output_dir, "country_world_map.pdf"))
                country_totals = country_ev.groupby("Country")["Count"].sum().sort_values(ascending=False)
                top_5 = country_totals.head(5)
                top_5_str = ", ".join([f"{c} ({int(cnt):,})" for c, cnt in top_5.items()])
                top_country_name = country_totals.index[0]
                bullets = [
                    f"Total Contributing Countries Identified: {len(country_totals)}",
                    f"Top Contributor Country: {top_country_name} ({int(country_totals.iloc[0]):,} papers)",
                    f"Top 5 Countries: {top_5_str}",
                ]
                _print_stage_summary("Country Evolution", bullets, elapsed_sec=time.time() - t_stage)

        # 4. Keyword CAGR Analysis
        if should_run("cagr", skip_cagr) and "Author Keywords" in df_pd.columns:
            t_stage = time.time()
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
                        top_5_cagr = cagr_pandas.nlargest(5, "cagr_percent")
                        top_5_kw_str = ", ".join([f"{r['standardized_word']} (+{r['cagr_percent']:.1f}%)" for _, r in top_5_cagr.iterrows()])
                        bullets = [
                            f"Total Unique Keywords Analyzed: {len(cagr_pandas):,}",
                            f"Top Trending Research Focus: '{top_5_cagr.iloc[0]['standardized_word']}' (+{top_5_cagr.iloc[0]['cagr_percent']:.1f}% CAGR)",
                            f"Top 5 Fastest Growing Keywords: {top_5_kw_str}",
                        ]
                        _print_stage_summary("Keyword CAGR Analysis", bullets, elapsed_sec=time.time() - t_stage)
            except Exception as e:
                logging.error(f"Failed to run keyword CAGR analysis: {e}")

        # 5. NLP (Topics)
        if should_run("nlp", skip_nlp):
            t_stage = time.time()
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
                
                if topic_info is not None:
                    valid_topics = topic_info[topic_info["Topic"] != -1]
                    top_3_t = valid_topics.nlargest(3, "Count")
                    top_3_str = "; ".join([f"Topic {r['Topic']} ({r['Name'][:30]}...): {r['Count']} papers" for _, r in top_3_t.iterrows()])
                    bullets = [
                        f"Abstracts Modeled: {len(docs):,}",
                        f"Discovered Distinct Topics: {len(valid_topics)}",
                        f"Top 3 Dominant Themes: {top_3_str}",
                        f"High-Level Research Lines Generated: {len(research_lines)}"
                    ]
                    _print_stage_summary("Topic Modeling (BERTopic)", bullets, elapsed_sec=time.time() - t_stage)
            else:
                logging.warning(f"Too few abstracts ({len(docs)}) for topic modeling. Skipping BERTopic.")
        else:
            logging.info("Skipping BERTopic modeling as requested.")

        # 6. Network Analysis (Co-authorship)
        if should_run("network", skip_network):
            t_stage = time.time()
            logging.info("Building co-authorship network...")
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
                top_per_comm = self.config.get("top_per_community", 1)
                self.viz.plot_network(edges_df, node_meta, save_path=os.path.join(self.output_dir, "network_graph.pdf"), top_per_community=top_per_comm)
                
                num_nodes = len(node_meta)
                num_edges = len(edges_df)
                num_comms = node_meta['partition'].nunique() if 'partition' in node_meta.columns else 0
                leaders = []
                if 'partition' in node_meta.columns and 'author_name' in node_meta.columns and 'num_publications' in node_meta.columns:
                    for _, group in node_meta.groupby('partition'):
                        top_author = group.sort_values('num_publications', ascending=False).iloc[0]['author_name']
                        leaders.append(top_author)
                leaders_str = ", ".join(leaders[:5]) if leaders else "N/A"
                bullets = [
                    f"Author Network Nodes: {num_nodes:,}",
                    f"Co-authorship Connections (Edges): {num_edges:,}",
                    f"Author Communities Discovered: {num_comms}",
                    f"Top Community Representative Leaders: {leaders_str}",
                ]
                _print_stage_summary("Co-Authorship Network", bullets, elapsed_sec=time.time() - t_stage)

        else:
            logging.info("Skipping network analysis as requested.")

        # 7. Co-Citation Network Stage
        if should_run("cocitation", False):
            t_stage = time.time()
            logging.info("Running Co-Citation Network analysis stage...")
            ref_df = None
            if refs_path and os.path.exists(refs_path):
                logging.info(f"Loading external references file from {refs_path}...")
                ref_df = pd.read_csv(refs_path)
            elif "References" in df_pd.columns and df_pd["References"].notnull().any():
                logging.info("Extracting reference links from publication dataset...")
                ref_df = self.citation_analyzer.extract_references_df(df_pd)

            if ref_df is not None and not ref_df.empty:
                try:
                    cocit_df, X = self.citation_analyzer.calculate_co_citation(ref_df)
                    if not cocit_df.empty:
                        cocit_df.to_csv(os.path.join(self.output_dir, "network_cocitations.csv"), index=False)
                        logging.info("Generating static Co-Citation network PDF graph...")
                        self.viz.plot_cocitation_network(cocit_df, save_path=os.path.join(self.output_dir, "cocitation_graph.pdf"))
                        
                        top_pair = cocit_df.iloc[0]
                        bullets = [
                            f"Total Reference Links Extracted: {len(ref_df):,}",
                            f"Unique Cited Publications: {ref_df['destination'].nunique():,}",
                            f"Co-Citation Connections Found: {len(cocit_df):,}",
                            f"Top Co-Cited Pair: '{str(top_pair['cited_1'])[:30]}' & '{str(top_pair['cited_2'])[:30]}' ({int(top_pair['co_citation_count']):,} co-citations)",
                        ]
                        _print_stage_summary("Co-Citation Network Analysis", bullets, elapsed_sec=time.time() - t_stage)
                        
                        self.last_cocit_df = cocit_df
                        self.last_sparse_X = X
                        self.last_ref_df = ref_df
                except Exception as e:
                    logging.exception(f"Error during co-citation analysis: {e}")
            else:
                logging.warning("No reference data available for co-citation analysis.")

        # 8. Bibliographic Coupling Stage
        if should_run("coupling", False):
            t_stage = time.time()
            logging.info("Running Bibliographic Coupling analysis stage...")
            if hasattr(self, 'last_sparse_X') and self.last_sparse_X is not None and hasattr(self, 'last_ref_df') and self.last_ref_df is not None:
                try:
                    df_clean = self.last_ref_df[['source', 'destination']].dropna().drop_duplicates(subset=['source', 'destination'])
                    source_codes, source_uniques = pd.factorize(df_clean['source'])
                    coupling_df = self.citation_analyzer.calculate_bibliographic_coupling(self.last_sparse_X, source_uniques)
                    if not coupling_df.empty:
                        coupling_df.to_csv(os.path.join(self.output_dir, "network_coupling.csv"), index=False)
                        bullets = [
                            f"Bibliographic Coupling Pairs Found: {len(coupling_df):,}",
                            f"Top Coupled Pair Weight: {int(coupling_df['coupling_weight'].max()):,} shared references",
                        ]
                        _print_stage_summary("Bibliographic Coupling Analysis", bullets, elapsed_sec=time.time() - t_stage)
                except Exception as e:
                    logging.exception(f"Error during bibliographic coupling analysis: {e}")

        # 7. Percolation Analysis Stage
        if should_run("percolation", skip_percolation):
            t_stage = time.time()
            logging.info("Running percolation threshold analysis stage...")
            edges_for_perc = None
            if 'edges_df' in locals() and not edges_df.empty:
                edges_for_perc = edges_df
            else:
                edges_csv = os.path.join(self.output_dir, "network_edges.csv")
                if os.path.exists(edges_csv):
                    logging.info(f"Loading existing network edges from {edges_csv}...")
                    edges_for_perc = pd.read_csv(edges_csv)
                else:
                    logging.info("Building co-authorship network for percolation analysis...")
                    edges_for_perc, _ = self.network.build_co_authorship_graph(df)
                    if hasattr(edges_for_perc, "to_pandas"):
                        edges_for_perc = edges_for_perc.to_pandas()

            if edges_for_perc is not None and not edges_for_perc.empty:
                try:
                    s_col = 'source' if 'source' in edges_for_perc.columns else 'source_id'
                    d_col = 'destination' if 'destination' in edges_for_perc.columns else 'dest_id'
                    w_col = 'weight' if 'weight' in edges_for_perc.columns else ('co_citation_count' if 'co_citation_count' in edges_for_perc.columns else edges_for_perc.columns[-1])
                    
                    percolation_df = self.citation_analyzer.perform_percolation_analysis(
                        edges_for_perc, s_col, d_col, w_col
                    )
                    if not percolation_df.empty:
                        percolation_df.to_csv(os.path.join(self.output_dir, "percolation_results.csv"), index=False)
                        logging.info("Generating static percolation analysis PDF graph...")
                        self.viz.plot_percolation(
                            percolation_df, w_col,
                            save_path=os.path.join(self.output_dir, "percolation_analysis.pdf")
                        )
                        num_steps = len(percolation_df)
                        max_lcc_pct = percolation_df['lcc_nodes_percentage_of_filtered'].max() if 'lcc_nodes_percentage_of_filtered' in percolation_df.columns else 0.0
                        bullets = [
                            f"Weight Cutoff Steps Evaluated: {num_steps}",
                            f"Peak Giant Component (LCC) Coverage: {max_lcc_pct:.1f}% of filtered network",
                            f"Results saved to: {os.path.join(self.output_dir, 'percolation_results.csv')}",
                        ]
                        _print_stage_summary("Percolation Analysis", bullets, elapsed_sec=time.time() - t_stage)
                except Exception as e:
                    logging.exception(f"Error during percolation analysis stage: {e}")
            else:
                logging.warning("No edge data available to run percolation analysis.")
        else:
            logging.info("Skipping percolation stage as requested.")

        try:
            exporter = LaTeXExporter(self.output_dir)
            exporter.export_all()
        except Exception as e:
            logging.warning(f"Could not export LaTeX templates: {e}")

        total_elapsed = time.time() - t_pipeline_start
        logging.info(f"Pipeline complete in {total_elapsed:.2f}s ({total_elapsed/60:.2f} min). All results saved to {self.output_dir}")

def main():
    parser = argparse.ArgumentParser(description="Bibliometric Research Pipeline CLI")
    parser.add_argument("--file", type=str, help="Path to local CSV/Parquet file")
    parser.add_argument("--refs-file", type=str, help="Path to external references CSV file")
    parser.add_argument("--query", type=str, help="Search query for autonomous collection")
    parser.add_argument("--query-file", type=str, help="Path to text file containing search query")
    parser.add_argument("--limit", type=int, default=100, help="Limit per source for collection (set to 0 for unlimited / fetch all matching papers)")
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
    parser.add_argument("--embedding-threshold", type=float, default=0.35, help="Similarity threshold for embedding filter (default: 0.35)")
    parser.add_argument("--screen-llm", action="store_true", help="Enable Option 2: LLM zero-shot classification & noise paradigm tagging")
    parser.add_argument("--llm-model", type=str, default="llama3.2:3b", help="Model name for Ollama LLM screening (default: llama3.2:3b)")
    parser.add_argument("--include-preprints", action="store_true", help="Include preprints from arXiv and bioRxiv (disabled by default for peer-reviewed only)")

    # Modular Stage Control Options
    parser.add_argument("--top-per-community", type=int, default=1, help="Top N representative author leaders per community to show in static network graph (default: 1)")
    parser.add_argument("--min-publications", type=int, default=1, help="Minimum publications threshold for network node inclusion (default: 1)")
    parser.add_argument("--stages", type=str, help="Comma-separated list of stages to run (options: growth,country,cagr,nlp,network,percolation)")
    parser.add_argument("--skip-nlp", action="store_true", help="Skip BERTopic modeling stage")
    parser.add_argument("--skip-network", action="store_true", help="Skip co-authorship network stage")
    parser.add_argument("--skip-cagr", action="store_true", help="Skip keyword CAGR stage")
    parser.add_argument("--skip-country", action="store_true", help="Skip country evolution stage")
    parser.add_argument("--skip-percolation", action="store_true", help="Skip percolation analysis stage")

    # Interactive Visualization Engine Option
    parser.add_argument("--interactive", "-i", action="store_true", help="Launch interactive graph parameter editor REPL session")

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
    if args.openalex_email:
        config["openalex_email"] = args.openalex_email
    if args.ss_api_key:
        config["ss_api_key"] = args.ss_api_key
    if args.crossref_email:
        config["crossref_email"] = args.crossref_email
    if args.pubmed_api_key:
        config["pubmed_api_key"] = args.pubmed_api_key
    if args.scopus_api_key:
        config["scopus_api_key"] = args.scopus_api_key
    if args.scopus_inst_token:
        config["scopus_inst_token"] = args.scopus_inst_token
    if args.wos_api_key:
        config["wos_api_key"] = args.wos_api_key

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

    pipeline = BibliometricPipeline(output_dir=args.output, config=config)

    if active_query:
        pipeline.run_with_query(active_query, limit=args.limit, start_year=args.start_year, end_year=args.end_year)
    elif args.file:
        pipeline.run(args.file, refs_path=args.refs_file, config=config)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
