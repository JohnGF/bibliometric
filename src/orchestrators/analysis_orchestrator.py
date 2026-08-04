import logging
import os
import time
from typing import Optional, List
import polars as pl
import pandas as pd

from src.core.nlp import BERTopicPipeline
from src.core.network import NetworkAnalysis
from src.core.viz import Visualization
from src.core.countries import CountryAnalysis
from src.core.citations import CitationsAnalysis

logger = logging.getLogger(__name__)

def _print_stage_summary(title: str, bullets: List[str], elapsed_sec: Optional[float] = None):
    """Prints a clean ASCII bullet-point summary box to stdout."""
    time_header = f" (Execution: {elapsed_sec:.2f}s)" if elapsed_sec is not None else ""
    header = f"=== ANALYSIS SUMMARY: {title}{time_header} ==="
    border = "=" * max(len(header), 65)
    print(f"\n{border}\n{header}\n{border}")
    for bullet in bullets:
        print(f"  * {bullet}")
    if elapsed_sec is not None:
        print(f"  * Stage Execution Time: {elapsed_sec:.2f} seconds ({elapsed_sec/60:.2f} min)")
    print(f"{border}\n")

class AnalysisOrchestrator:
    """Handles the execution of analytical engines (Growth, Network, NLP, etc.)."""

    def __init__(self, output_dir: str, config: dict):
        self.output_dir = output_dir
        self.figures_dir = os.path.join(output_dir, "figures")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.figures_dir, exist_ok=True)
        self.config = config

        theme = self.config.get("theme", "whitegrid")
        self.viz = Visualization(style=theme)
        self.nlp = BERTopicPipeline()
        self.network = NetworkAnalysis()
        self.country_analyzer = CountryAnalysis()
        self.citation_analyzer = CitationsAnalysis()

        # State for stages that depend on each other
        self.last_cocit_df = None
        self.last_sparse_X = None
        self.last_ref_df = None
        self.last_edges_df = None

    def _should_run(self, stage_name: str, skip_flag: bool) -> bool:
        if skip_flag:
            return False
        stages = self.config.get("stages", None)
        if stages is not None:
            return stage_name in stages
        return True

    def analyze_references_dataset(self, df_pd: pd.DataFrame):
        """Dedicated path for pure reference datasets."""
        logger.info("Detected references dataset. Running co-citation and coupling analysis...")
        cocit_df, X = self.citation_analyzer.calculate_co_citation(df_pd)
        cocit_df.to_csv(os.path.join(self.output_dir, "network_cocitations.csv"), index=False)

        if not cocit_df.empty:
            logger.info("Running co-citation percolation threshold analysis...")
            try:
                percolation_df = self.citation_analyzer.perform_percolation_analysis(
                    cocit_df, 'cited_1', 'cited_2', 'co_citation_count'
                )
                if not percolation_df.empty:
                    percolation_df.to_csv(os.path.join(self.output_dir, "percolation_results.csv"), index=False)
                    self.viz.plot_percolation(
                        percolation_df, 'co_citation_count',
                        save_path=os.path.join(self.figures_dir, "percolation_analysis.pdf")
                    )
            except Exception as e:
                logger.exception(f"Error during percolation analysis: {e}")

        if X is not None:
            df_clean = df_pd[['source', 'destination']].dropna().drop_duplicates(subset=['source', 'destination'])
            source_codes, source_uniques = pd.factorize(df_clean['source'])
            coupling_df = self.citation_analyzer.calculate_bibliographic_coupling(X, source_uniques)
            coupling_df.to_csv(os.path.join(self.output_dir, "network_coupling.csv"), index=False)

        logger.info(f"References analysis complete. Outputs written to {self.output_dir}")

    def run_analysis(self, df_pd: pd.DataFrame, refs_path: Optional[str] = None):
        """Runs the main analysis pipeline on a validated publications dataframe."""
        df = pl.from_pandas(df_pd)
        df = df.filter(pl.col("Year").is_not_null())
        df = df.with_columns(pl.col("Year").cast(pl.Int64))

        t_pipeline_start = time.time()
        top_n_countries = self.config.get("top_n_countries", 10)
        min_pub = self.config.get("min_publications", 1)

        # 1. Growth
        if self._should_run("growth", False):
            print("\n>>> [STAGE 3.1] Yearly Growth & Projections - Generating growth charts and temporal data...")
            t_stage = time.time()
            logger.info("Generating yearly growth charts and projections...")
            growth_df = self.viz.plot_yearly_growth(df, save_path=os.path.join(self.figures_dir, "yearly_growth.pdf"))
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

        # 2. Country
        if self._should_run("country", self.config.get("skip_country", False)) and "Affiliations" in df_pd.columns:
            print("\n>>> [STAGE 3.2] Country Evolution - Parsing author affiliations and mapping world distribution...")
            t_stage = time.time()
            exploded_pub, country_ev = self.country_analyzer.process_countries(df)
            if not country_ev.empty:
                country_ev.to_csv(os.path.join(self.output_dir, "country_evolution.csv"), index=False)
                self.viz.plot_country_evolution(country_ev, top_n=top_n_countries, save_path=os.path.join(self.figures_dir, "country_evolution.pdf"))
                self.viz.plot_country_choropleth_map(country_ev, save_path=os.path.join(self.figures_dir, "country_world_map.pdf"))
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

        # 3. Keyword CAGR
        if self._should_run("cagr", self.config.get("skip_cagr", False)) and "Author Keywords" in df_pd.columns:
            print("\n>>> [STAGE 3.3] Keyword CAGR Analysis - Evaluating topic growth rates and compound trends...")
            t_stage = time.time()
            try:
                kw_df = self.nlp.preprocess_keywords(df, column="Author Keywords")
                if not kw_df.is_empty():
                    kw_counts = kw_df.group_by(["Year", "standardized_word"]).len().rename({"len": "count"})
                    cagr_df = self.nlp.calculate_cagr(kw_counts, count_col="count", year_col="Year")
                    if not cagr_df.is_empty():
                        cagr_pandas = cagr_df.to_pandas()
                        cagr_pandas.to_csv(os.path.join(self.output_dir, "keywords_cagr.csv"), index=False)
                        self.viz.plot_keywords_cagr(cagr_pandas, save_path=os.path.join(self.figures_dir, "keywords_cagr.pdf"))
                        top_5_cagr = cagr_pandas.nlargest(5, "cagr_percent")
                        top_5_kw_str = ", ".join([f"{r['standardized_word']} (+{r['cagr_percent']:.1f}%)" for _, r in top_5_cagr.iterrows()])
                        bullets = [
                            f"Total Unique Keywords Analyzed: {len(cagr_pandas):,}",
                            f"Top Trending Research Focus: '{top_5_cagr.iloc[0]['standardized_word']}' (+{top_5_cagr.iloc[0]['cagr_percent']:.1f}% CAGR)",
                            f"Top 5 Fastest Growing Keywords: {top_5_kw_str}",
                        ]
                        _print_stage_summary("Keyword CAGR Analysis", bullets, elapsed_sec=time.time() - t_stage)
            except Exception as e:
                print(f">>> [ERROR] Failed to run keyword CAGR analysis: {e}")
                logger.error(f"Failed to run keyword CAGR analysis: {e}")

        # 4. NLP
        if self._should_run("nlp", self.config.get("skip_nlp", False)):
            print("\n>>> [STAGE 3.4] Topic Modeling - Running BERTopic clustering and theme extraction...")
            t_stage = time.time()
            docs = df["Abstract"].drop_nulls().to_list()
            if len(docs) >= 10:
                topics, probs = self.nlp.fit_model(docs)
                topic_info = self.nlp.get_topics()
                if topic_info is not None:
                    topic_info.to_csv(os.path.join(self.output_dir, "topic_info.csv"), index=False)
                    self.viz.plot_topic_distribution(topic_info, save_path=os.path.join(self.figures_dir, "topic_word_scores.pdf"))

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
                print(">>> [WARNING] Too few abstracts for BERTopic (minimum 10 required). Skipping Stage 3.4.")
                logger.warning("Too few abstracts for BERTopic.")

        # 5. Network
        if self._should_run("network", self.config.get("skip_network", False)):
            print("\n>>> [STAGE 3.5] Co-Authorship Network - Constructing collaborator graphs and communities...")
            t_stage = time.time()
            edges_df, node_meta = self.network.build_co_authorship_graph(df)

            if hasattr(edges_df, "to_pandas"): edges_df = edges_df.to_pandas()
            if hasattr(node_meta, "to_pandas"): node_meta = node_meta.to_pandas()

            if min_pub > 1 and not node_meta.empty:
                node_meta = node_meta[node_meta['num_publications'] >= min_pub]
                valid_vertices = set(node_meta['vertex'])
                edges_df = edges_df[edges_df['source_id'].isin(valid_vertices) & edges_df['dest_id'].isin(valid_vertices)]

            edges_df.to_csv(os.path.join(self.output_dir, "network_edges.csv"), index=False)
            node_meta.to_csv(os.path.join(self.output_dir, "network_nodes.csv"), index=False)
            self.last_edges_df = edges_df

            if not edges_df.empty and not node_meta.empty:
                top_per_comm = self.config.get("top_per_community", 1)
                self.viz.plot_network(edges_df, node_meta, save_path=os.path.join(self.figures_dir, "network_graph.pdf"), top_per_community=top_per_comm)
                self.viz.plot_circular_community_network(edges_df, node_meta, save_path=os.path.join(self.figures_dir, "network_circular_chord.pdf"), top_per_community=top_per_comm)
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

        # 6. Co-Citation
        if self._should_run("cocitation", False):
            print("\n>>> [STAGE 3.6] Co-Citation Network - Processing reference coupling and citation paths...")
            t_stage = time.time()
            ref_df = None
            if refs_path and os.path.exists(refs_path):
                ref_df = pd.read_csv(refs_path)
            elif "References" in df_pd.columns and df_pd["References"].notnull().any():
                ref_df = self.citation_analyzer.extract_references_df(df_pd)

            if ref_df is not None and not ref_df.empty:
                cocit_df, X = self.citation_analyzer.calculate_co_citation(ref_df)
                if not cocit_df.empty:
                    cocit_df.to_csv(os.path.join(self.output_dir, "network_cocitations.csv"), index=False)
                    title_map = {}
                    if "Title" in df_pd.columns:
                        for _, r in df_pd.iterrows():
                            eid = str(r.get("EID", "") or "").strip()
                            doi = str(r.get("DOI", "") or "").strip()
                            t = str(r.get("Title", "") or "").strip()
                            url = f"https://doi.org/{doi}" if doi else (f"https://openalex.org/{eid}" if eid else "")
                            if eid:
                                title_map[eid] = {"title": t, "url": url}
                            if doi:
                                title_map[doi] = {"title": t, "url": url}

                    self.viz.plot_cocitation_network(cocit_df, title_map=title_map, save_path=os.path.join(self.figures_dir, "cocitation_graph.pdf"))
                    self.last_cocit_df, self.last_sparse_X, self.last_ref_df = cocit_df, X, ref_df
                    top_pair = cocit_df.iloc[0]
                    bullets = [
                        f"Total Reference Links Extracted: {len(ref_df):,}",
                        f"Unique Cited Publications: {ref_df['destination'].nunique():,}",
                        f"Co-Citation Connections Found: {len(cocit_df):,}",
                        f"Top Co-Cited Pair: '{str(top_pair['cited_1'])[:30]}' & '{str(top_pair['cited_2'])[:30]}' ({int(top_pair['co_citation_count']):,} co-citations)",
                    ]
                    _print_stage_summary("Co-Citation Network Analysis", bullets, elapsed_sec=time.time() - t_stage)

        # 7. Coupling
        if self._should_run("coupling", False) and self.last_sparse_X is not None and self.last_ref_df is not None:
            print("\n>>> [STAGE 3.7] Bibliographic Coupling - Mapping source intersections...")
            t_stage = time.time()
            df_clean = self.last_ref_df[['source', 'destination']].dropna().drop_duplicates(subset=['source', 'destination'])
            _, source_uniques = pd.factorize(df_clean['source'])
            coupling_df = self.citation_analyzer.calculate_bibliographic_coupling(self.last_sparse_X, source_uniques)
            if not coupling_df.empty:
                coupling_df.to_csv(os.path.join(self.output_dir, "network_coupling.csv"), index=False)
                bullets = [
                    f"Bibliographic Coupling Pairs Found: {len(coupling_df):,}",
                    f"Top Coupled Pair Weight: {int(coupling_df['coupling_weight'].max()):,} shared references",
                ]
                _print_stage_summary("Bibliographic Coupling Analysis", bullets, elapsed_sec=time.time() - t_stage)

        # 8. Percolation
        if self._should_run("percolation", self.config.get("skip_percolation", False)):
            print("\n>>> [STAGE 3.8] Percolation Threshold Analysis - Evaluating network resilience...")
            t_stage = time.time()
            edges_for_perc = self.last_edges_df
            if edges_for_perc is None and os.path.exists(os.path.join(self.output_dir, "network_edges.csv")):
                edges_for_perc = pd.read_csv(os.path.join(self.output_dir, "network_edges.csv"))

            if edges_for_perc is not None and not edges_for_perc.empty:
                s_col = 'source' if 'source' in edges_for_perc.columns else 'source_id'
                d_col = 'destination' if 'destination' in edges_for_perc.columns else 'dest_id'
                w_col = 'weight' if 'weight' in edges_for_perc.columns else edges_for_perc.columns[-1]

                percolation_df = self.citation_analyzer.perform_percolation_analysis(edges_for_perc, s_col, d_col, w_col)
                if not percolation_df.empty:
                    percolation_df.to_csv(os.path.join(self.output_dir, "percolation_results.csv"), index=False)
                    self.viz.plot_percolation(percolation_df, w_col, save_path=os.path.join(self.figures_dir, "percolation_analysis.pdf"))
                    num_steps = len(percolation_df)
                    max_lcc_pct = percolation_df['lcc_nodes_percentage_of_filtered'].max() if 'lcc_nodes_percentage_of_filtered' in percolation_df.columns else 0.0
                    bullets = [
                        f"Weight Cutoff Steps Evaluated: {num_steps}",
                        f"Peak Giant Component (LCC) Coverage: {max_lcc_pct:.1f}% of filtered network",
                        f"Results saved to: {os.path.join(self.output_dir, 'percolation_results.csv')}",
                    ]
                    _print_stage_summary("Percolation Analysis", bullets, elapsed_sec=time.time() - t_stage)

        # 9. Supplementary scaffold figures (query-neutral, generated so the
        #    compiled document always includes every figure referenced by the
        #    IEEEtran scaffold).
        print("\n>>> [STAGE 3.9] Generating Supplementary Scaffold Figures...")
        self._generate_supplementary_figures(df_pd)

        total_elapsed = time.time() - t_pipeline_start
        print(f"\n>>> [ANALYSIS STAGE COMPLETE] Main analytical routines finished in {total_elapsed:.2f} seconds.")
        logger.info(f"Analysis complete in {total_elapsed:.2f}s.")

    def _generate_supplementary_figures(self, df_pd: pd.DataFrame):
        """Regenerates temporal delta, LLM paradigm, and method x application figures."""
        from src.core.temporal_delta import TemporalDeltaAnalysis

        # Temporal delta shifts (Author Keywords + Year)
        if "Author Keywords" in df_pd.columns and "Year" in df_pd.columns:
            try:
                records = []
                for _, r in df_pd.dropna(subset=["Author Keywords", "Year"]).iterrows():
                    yr = int(r["Year"])
                    for k in str(r["Author Keywords"]).split(";"):
                        k_clean = k.strip().lower()
                        if k_clean:
                            records.append({"Keyword": k_clean, "Year": yr})
                kdf = pd.DataFrame(records)
                if not kdf.empty:
                    delta_df = TemporalDeltaAnalysis().compute_temporal_deltas(
                        kdf, category_col="Keyword", year_col="Year"
                    )
                    if delta_df is not None and not delta_df.empty:
                        self.viz.plot_temporal_delta_shifts(
                            delta_df,
                            title_suffix="Research Focus Areas",
                            save_path=os.path.join(self.figures_dir, "temporal_delta_shifts.pdf"),
                        )
                        logger.info("Generated temporal_delta_shifts.pdf")
            except Exception as e:
                logger.warning(f"Could not generate temporal delta shifts figure: {e}")

        # LLM noise treatment paradigm taxonomy (Title/Abstract heuristics)
        try:
            self.viz.plot_llm_noise_paradigm(
                df_pd, save_path=os.path.join(self.figures_dir, "llm_noise_paradigm.pdf")
            )
            logger.info("Generated llm_noise_paradigm.pdf")
        except Exception as e:
            logger.warning(f"Could not generate LLM noise paradigm figure: {e}")

        # Methodology x application field matrix (Title/Abstract heuristics)
        try:
            self.viz.plot_method_application_matrix(
                df_pd, save_path=os.path.join(self.figures_dir, "method_application_matrix.pdf")
            )
            logger.info("Generated method_application_matrix.pdf")
        except Exception as e:
            logger.warning(f"Could not generate methodology x application matrix figure: {e}")
