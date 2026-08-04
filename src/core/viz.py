import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import polars as pl
import pandas as pd
from typing import Optional

class Visualization:
    def __init__(self, style: str = "whitegrid"):
        sns.set_style(style)
        plt.rcParams["figure.figsize"] = (12, 7)

    def plot_yearly_growth(self, df: pl.DataFrame, save_path: Optional[str] = None, max_year: Optional[int] = None, min_year: Optional[int] = None) -> Optional[pd.DataFrame]:
        """Plots publication counts and YoY growth percentages for complete historical years.

        The study window defaults to the date bounds in the query configuration
        file (data/query.txt) and is always expanded to cover the actual data range.
        """
        if df.is_empty():
            return None

        # Derive year bounds from the query config, falling back to the data range.
        from src.core.study_config import load_study_config
        cfg = load_study_config()

        data_years = df.select(pl.col("Year").cast(pl.Int64).drop_nulls())
        data_min = int(data_years.min().item()) if not data_years.is_empty() else None
        data_max = int(data_years.max().item()) if not data_years.is_empty() else None

        if min_year is None:
            min_year = cfg.get("start_year") or data_min
        if max_year is None:
            max_year = cfg.get("end_year") or data_max

        # Never truncate the available data.
        if data_min is not None and min_year is not None:
            min_year = min(min_year, data_min)
        if data_max is not None and max_year is not None:
            max_year = max(max_year, data_max)

        # Filter complete historical years (excluding incomplete/future indexing artifacts > max_year)
        filtered_df = df.filter((pl.col("Year") >= min_year) & (pl.col("Year") <= max_year))
        if filtered_df.is_empty():
            filtered_df = df

        yearly_counts = filtered_df.group_by("Year").len().sort("Year")
        yearly_counts = yearly_counts.with_columns(pl.col("len").cast(pl.Int64))
        
        pdf = yearly_counts.to_pandas()
        pdf["previous_year_len"] = pdf["len"].shift(1)
        pdf["growth_pct"] = ((pdf["len"] - pdf["previous_year_len"]) / pdf["previous_year_len"]) * 100
        pdf["growth_pct"] = pdf["growth_pct"].fillna(0.0)
        
        pdf["is_projected"] = False
        pdf["projected_len"] = pdf["len"]
        pdf["projected_growth_pct"] = pdf["growth_pct"]

        # Mark the current calendar year as partial (YTD) since it is still in progress.
        current_year = datetime.date.today().year
        pdf["is_partial"] = pdf["Year"] == current_year
        has_partial = bool(pdf["is_partial"].any())

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
        years = pdf["Year"].astype(str).tolist()

        # Plot 1: Counts
        partial_labeled = False
        observed_labeled = False
        for i, row in pdf.iterrows():
            if row["is_partial"]:
                label = "Partial Year (YTD)" if not partial_labeled else ""
                partial_labeled = True
                ax1.bar(years[i], row["len"], color='skyblue', edgecolor='black', linewidth=0.8,
                        hatch='///', alpha=0.85, label=label)
            else:
                label = "Observed Publications" if not observed_labeled else ""
                observed_labeled = True
                ax1.bar(years[i], row["len"], color='skyblue', label=label)
            ax1.text(i, row["len"] + (row["len"] * 0.01), f'{int(row["len"]):,}', ha='center', va='bottom', fontsize=9, fontweight='bold')

        ax1.set_ylabel("Number of Publications", fontsize=11, fontweight='bold')
        ax1.set_title(f"Historical Publication Evolution ({min_year} - {max_year})", fontsize=14, pad=15, fontweight="bold")
        ax1.grid(axis='y', linestyle='--', alpha=0.7)
        ax1.legend(loc="upper left")

        # Plot 2: YoY Growth Rate (%)
        partial_labeled = False
        for i, row in pdf.iterrows():
            yval = row["growth_pct"]
            color = 'lightcoral' if yval >= 0 else 'lightskyblue'
            if row["is_partial"]:
                label = "Partial Year (YTD)" if not partial_labeled else ""
                partial_labeled = True
                ax2.bar(years[i], yval, color=color, edgecolor='black', linewidth=0.8,
                        hatch='///', alpha=0.85, label=label)
            else:
                ax2.bar(years[i], yval, color=color, edgecolor='black', linewidth=0.5)
            offset = 0.5 if yval >= 0 else -2.5
            ytd_suffix = " (YTD)" if row["is_partial"] else ""
            ax2.text(i, yval + offset, f'{yval:+.1f}%{ytd_suffix}', ha='center', va='bottom' if yval >= 0 else 'top', fontsize=9, fontweight='bold')

        ax2.set_ylabel("YoY Growth Rate (%)", fontsize=11, fontweight='bold')
        ax2.axhline(0, color='grey', linewidth=0.8, linestyle='--')
        ax2.grid(axis='y', linestyle='--', alpha=0.7)
        ax2.legend(loc="best")

        plt.xticks(rotation=45)
        if has_partial:
            plt.figtext(0.5, 0.01,
                        f"Note: {current_year} is still in progress and shown as a partial year (YTD).",
                        ha='center', fontsize=9, style='italic', alpha=0.75)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            png_path = save_path.replace(".pdf", ".png")
            plt.savefig(png_path, dpi=300, bbox_inches="tight")
        plt.close()
        return pdf

    def plot_heatmap(self, matrix_df: pl.DataFrame, title: str, save_path: Optional[str] = None):
        """Generates a seaborn heatmap for correlation or co-occurrence matrices."""
        plt.figure(figsize=(14, 10))
        sns.heatmap(matrix_df.to_pandas().set_index(matrix_df.columns[0]), annot=False, cmap="YlGnBu")
        plt.title(title)
        if save_path:
            plt.savefig(save_path)
        return plt.gcf()

    def plot_country_evolution(self, df: pd.DataFrame, top_n: int = 10, save_path: Optional[str] = None):
        """
        Plots the temporal evolution of the top N countries.
        
        Args:
            df: DataFrame containing Year, Country, Count columns.
            top_n: Number of top countries to include based on total counts.
            save_path: Optional path to save the generated high-res PDF.
        """
        if df.empty:
            return None
            
        # Find top N countries by total contributions
        top_countries = df.groupby("Country")["Count"].sum().nlargest(top_n).index
        filtered_df = df[df["Country"].isin(top_countries)]
        
        plt.figure(figsize=(14, 8))
        sns.lineplot(data=filtered_df, x="Year", y="Count", hue="Country", marker="o", linewidth=2.5, palette="tab10")
        
        plt.title(f"Evolution of Top {top_n} Research Contributor Countries", fontsize=16, pad=15)
        plt.xlabel("Year", fontsize=12)
        plt.ylabel("Publication Count", fontsize=12)
        plt.legend(title="Countries", bbox_to_anchor=(1.05, 1), loc="upper left", frameon=True)
        plt.grid(True, linestyle="--", alpha=0.5)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300)
        return plt.gcf()

    def plot_country_choropleth_map(self, df: pd.DataFrame, save_path: Optional[str] = None):
        """
        Plots a global choropleth heatmap of research publication volume by country.
        """
        import os
        import numpy as np
        import logging
        logger = logging.getLogger(__name__)

        if df.empty or "Country" not in df.columns or "Count" not in df.columns:
            logger.warning("No country counts available for choropleth map.")
            return

        try:
            import geopandas as gpd
        except ImportError:
            logger.warning("geopandas not available; skipping country choropleth map.")
            return

        # Aggregate total counts per country
        country_totals = df.groupby("Country")["Count"].sum().reset_index()

        # Alias map for common name mismatches
        aliases = {
            "United States": "United States of America",
            "USA": "United States of America",
            "US": "United States of America",
            "UK": "United Kingdom",
            "Great Britain": "United Kingdom",
            "South Korea": "South Korea",
            "Korea": "South Korea",
            "Russia": "Russian Federation",
        }
        country_totals["Country"] = country_totals["Country"].replace(aliases)
        country_totals = country_totals.groupby("Country")["Count"].sum().reset_index()

        geojson_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates", "world.geojson"))
        if not os.path.exists(geojson_path):
            logger.warning("world.geojson not found; skipping choropleth map.")
            return

        try:
            world = gpd.read_file(geojson_path)
            world["Country"] = world["name"]
            merged = world.merge(country_totals, on="Country", how="left")
            merged["Count"] = merged["Count"].fillna(0)
            merged["LogCount"] = np.log1p(merged["Count"])

            fig, ax = plt.subplots(figsize=(14, 8))
            merged.plot(
                column="LogCount",
                cmap="YlOrRd",
                linewidth=0.4,
                ax=ax,
                edgecolor="#555555",
                legend=False,
                missing_kwds={'color': '#e0e0e0', 'edgecolor': '#cccccc'}
            )

            sm = plt.cm.ScalarMappable(cmap="YlOrRd", norm=plt.Normalize(vmin=0, vmax=merged["LogCount"].max()))
            sm._A = []
            cbar = fig.colorbar(sm, ax=ax, orientation="horizontal", pad=0.04, shrink=0.65)
            cbar.set_label("Publication Volume (Log Scale)", fontsize=11, fontweight="bold")

            ax.set_title("Global Research Output & Institutional Heatmap by Country", fontsize=16, pad=15, fontweight="bold")
            ax.set_axis_off()
            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches="tight")
                png_path = save_path.replace(".pdf", ".png")
                plt.savefig(png_path, dpi=300, bbox_inches="tight")
                logger.info(f"Saved country choropleth map to {save_path} and {png_path}")
            plt.close()
        except Exception as e:
            logger.warning(f"Could not render country choropleth map: {e}")

    def plot_temporal_delta_shifts(self, delta_df: pd.DataFrame, title_suffix: str = "Research Topics", save_path: Optional[str] = None):
        """
        Plots a horizontal Diverging Bar Chart showing the Market Share Delta (\Delta Share %)
        between baseline vs modern epochs.
        """
        import logging
        logger = logging.getLogger(__name__)

        if delta_df.empty or "Category" not in delta_df.columns or "Delta_Share_Pct" not in delta_df.columns:
            logger.warning("Invalid DataFrame for temporal delta plot.")
            return

        top_emerging = delta_df.nlargest(10, "Delta_Share_Pct")
        top_declining = delta_df.nsmallest(10, "Delta_Share_Pct")
        plot_df = pd.concat([top_emerging, top_declining]).drop_duplicates().sort_values("Delta_Share_Pct")

        colors = ["#2ca02c" if val >= 0 else "#d62728" for val in plot_df["Delta_Share_Pct"]]

        plt.figure(figsize=(12, 7))
        bars = plt.barh(plot_df["Category"], plot_df["Delta_Share_Pct"], color=colors, edgecolor="#333333", height=0.6)
        
        plt.axvline(0, color="black", linewidth=1, linestyle="--")
        plt.title(f"Scientific Temporal Shift (\\Delta Market Share %): {title_suffix}", fontsize=15, pad=15, fontweight="bold")
        plt.xlabel("Market Share Delta (\\Delta % Points between Baseline vs Modern Epoch)", fontsize=11, fontweight="bold")
        plt.ylabel(title_suffix, fontsize=11, fontweight="bold")
        plt.grid(True, linestyle="--", alpha=0.5)

        for bar in bars:
            val = bar.get_width()
            offset = 0.1 if val >= 0 else -0.5
            plt.text(val + offset, bar.get_y() + bar.get_height()/2, f"{val:+.2f}%", va="center", fontsize=9, fontweight="bold")

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            png_path = save_path.replace(".pdf", ".png")
            plt.savefig(png_path, dpi=300, bbox_inches="tight")
            logger.info(f"Saved temporal delta chart to {save_path} and {png_path}")
        plt.close()

    def plot_llm_noise_paradigm(self, df: pd.DataFrame, save_path: Optional[str] = None):
        """
        Plots a donut chart visualization of LLM / AI Noise Treatment Paradigms across papers.
        """
        import logging
        logger = logging.getLogger(__name__)

        if df.empty:
            return

        paradigm_col = "noise_paradigm" if "noise_paradigm" in df.columns else None
        if not paradigm_col:
            titles = df["Title"].fillna("").astype(str).str.lower() if "Title" in df.columns else pd.Series([""]*len(df))
            abstracts = df["Abstract"].fillna("").astype(str).str.lower() if "Abstract" in df.columns else pd.Series([""]*len(df))
            text = titles + " " + abstracts
            
            paradigms = []
            for t in text:
                if any(w in t for w in ["ica", "wavelet", "artifact removal", "filtering", "suppression", "denois"]):
                    paradigms.append("Artifact Filtering & Removal")
                elif any(w in t for w in ["stochastic", "resonance", "information", "entropy"]):
                    paradigms.append("Noise-as-Information")
                elif any(w in t for w in ["deep learning", "cnn", "robust", "decoding", "latent"]):
                    paradigms.append("Robust Latent Decoding")
                else:
                    paradigms.append("General BCI Analysis")
            counts = pd.Series(paradigms).value_counts()
        else:
            label_map = {
                "filtering_removal": "Artifact Filtering & Removal",
                "noise_as_information": "Noise-as-Information",
                "robust_decoding": "Robust Latent Decoding",
                "unspecified": "General BCI Analysis"
            }
            counts = df[paradigm_col].replace(label_map).value_counts()

        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"][:len(counts)]

        fig, ax = plt.subplots(figsize=(10, 7))
        wedges, texts, autotexts = ax.pie(
            counts.values, 
            labels=counts.index, 
            autopct="%1.1f%%", 
            startangle=140, 
            colors=colors,
            pctdistance=0.75,
            wedgeprops=dict(width=0.4, edgecolor="white", linewidth=2)
        )

        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_weight("bold")
            autotext.set_fontsize(11)

        ax.set_title("Ollama LLM Taxonomy: EEG Noise Treatment Paradigms", fontsize=15, pad=15, fontweight="bold")
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            png_path = save_path.replace(".pdf", ".png")
            plt.savefig(png_path, dpi=300, bbox_inches="tight")
            logger.info(f"Saved LLM noise paradigm chart to {save_path} and {png_path}")
        plt.close()

    def plot_method_application_matrix(self, df: pd.DataFrame, save_path: Optional[str] = None):
        """
        Plots a 2D Heatmap Matrix pairing Methodologies / Techniques with Application Fields.
        """
        import logging
        import seaborn as sns
        logger = logging.getLogger(__name__)

        if df.empty:
            return

        titles = df["Title"].fillna("").astype(str).str.lower() if "Title" in df.columns else pd.Series([""]*len(df))
        abstracts = df["Abstract"].fillna("").astype(str).str.lower() if "Abstract" in df.columns else pd.Series([""]*len(df))
        text = titles + " " + abstracts

        methods = []
        apps = []

        for t in text:
            if any(w in t for w in ["ica", "wavelet", "artifact removal", "filtering", "suppression", "denois"]):
                m = "ICA / Wavelet Denoising"
            elif any(w in t for w in ["deep learning", "cnn", "convolutional", "transformer", "neural network"]):
                m = "Deep Learning (CNN/DL)"
            elif any(w in t for w in ["csp", "fbcsp", "ssvep", "spatial pattern", "evoked"]):
                m = "Spatial Patterns (CSP/SSVEP)"
            elif any(w in t for w in ["stochastic", "resonance", "entropy", "variability"]):
                m = "Stochastic Noise Dynamics"
            else:
                m = "General Signal Processing"

            if any(w in t for w in ["motor imagery", "bci", "rehabilitation", "prosthetic", "neuroprosthet"]):
                a = "Motor Imagery BCI"
            elif any(w in t for w in ["epilepsy", "seizure", "hfo", "spike", "ictal"]):
                a = "Epilepsy & Seizures"
            elif any(w in t for w in ["emotion", "affective", "deap", "valence", "arousal"]):
                a = "Emotion Recognition"
            elif any(w in t for w in ["sleep", "somnology", "staging", "drowsiness"]):
                a = "Sleep Staging"
            elif any(w in t for w in ["workload", "fatigue", "driving", "cognitive", "mental"]):
                a = "Cognitive Workload"
            else:
                a = "General Clinical & Bio"

            methods.append(m)
            apps.append(a)

        ct = pd.crosstab(pd.Series(methods, name="Methodology"), pd.Series(apps, name="Application Field"))

        plt.figure(figsize=(11, 7))
        sns.heatmap(ct, annot=True, fmt="d", cmap="YlGnBu", linewidths=1, cbar_kws={'label': 'Publication Count'})
        plt.title("Methodology vs Application Field Cross-Tabulation Matrix", fontsize=15, pad=15, fontweight="bold")
        plt.xlabel("Application Field", fontsize=11, fontweight="bold")
        plt.ylabel("Methodology / Technique Used", fontsize=11, fontweight="bold")
        plt.xticks(rotation=30, ha="right")
        plt.yticks(rotation=0)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            png_path = save_path.replace(".pdf", ".png")
            plt.savefig(png_path, dpi=300, bbox_inches="tight")
            logger.info(f"Saved methodology vs application matrix to {save_path} and {png_path}")
        plt.close()

    def plot_network(self, edges_df: pd.DataFrame, node_meta: pd.DataFrame, save_path: Optional[str] = None, top_per_community: int = 2, show_heatmap: bool = True):
        """
        Plots a high-resolution, publication-grade co-authorship network focusing on the 
        Giant Connected Component and prominent core research communities.
        """
        import networkx as nx

        if edges_df.empty or node_meta.empty:
            return None
            
        fig, ax = plt.subplots(figsize=(16, 12))
        
        # Build full NetworkX Graph
        G_full = nx.Graph()
        for _, row in node_meta.iterrows():
            G_full.add_node(
                row['vertex'], 
                name=row['author_name'], 
                partition=row['partition'],
                size=row.get('num_publications', 1),
                citations=row.get('total_citations', 0)
            )
        for _, row in edges_df.iterrows():
            G_full.add_edge(row['source_id'], row['dest_id'], weight=row['weight'])
            
        # Filter for Giant Connected Component & prominent nodes to eliminate ugly isolated 2-node noise
        if len(G_full) > 150:
            # Extract components with at least 4 nodes or top 150 authors by citations/pubs
            components = [c for c in nx.connected_components(G_full) if len(c) >= 3]
            if components:
                nodes_to_keep = set().union(*components)
            else:
                nodes_to_keep = set(G_full.nodes())
                
            # Filter top 150 most prominent authors if network is huge
            top_nodes = sorted(nodes_to_keep, key=lambda n: (G_full.nodes[n]['size'], G_full.nodes[n]['citations']), reverse=True)[:150]
            G = G_full.subgraph(top_nodes).copy()
        else:
            G = G_full.copy()

        if len(G) == 0:
            G = G_full

        # Layout calculation: calculate clean spring layout with optimal node separation
        pos = nx.spring_layout(G, k=0.45, iterations=120, seed=42)
            
        # 1. Edge Density Heatmap Layer
        if show_heatmap and len(G.edges) > 5:
            try:
                edge_x = []
                edge_y = []
                for u, v in G.edges:
                    p1 = pos[u]
                    p2 = pos[v]
                    edge_x.extend([p1[0], p2[0], (p1[0] + p2[0]) / 2])
                    edge_y.extend([p1[1], p2[1], (p1[1] + p2[1]) / 2])
                
                if len(edge_x) > 10:
                    sns.kdeplot(
                        x=edge_x, y=edge_y,
                        ax=ax,
                        cmap="Blues",
                        fill=True,
                        thresh=0.05,
                        levels=12,
                        alpha=0.25,
                        zorder=1
                    )
            except Exception:
                pass

        # Color mapping (community partitions)
        partitions = [G.nodes[n]['partition'] for n in G.nodes]
        unique_partitions = list(set(partitions))
        color_palette = sns.color_palette("tab10", max(len(unique_partitions), 10))
        partition_colors = {p: color_palette[i % len(color_palette)] for i, p in enumerate(unique_partitions)}
        node_colors = [partition_colors[G.nodes[n]['partition']] for n in G.nodes]
        
        # Node sizing scaling
        all_sizes = [G.nodes[n]['size'] for n in G.nodes]
        max_s = max(all_sizes) if all_sizes else 1
        node_sizes = [(G.nodes[n]['size'] / max_s) * 600 + 120 for n in G.nodes]
        
        # Edge weights scaling
        all_w = [G[u][v]['weight'] for u, v in G.edges]
        max_w = max(all_w) if all_w else 1
        edge_widths = [(G[u][v]['weight'] / max_w) * 3.0 + 0.5 for u, v in G.edges]
        
        # Draw elements
        edges_collection = nx.draw_networkx_edges(G, pos, ax=ax, width=edge_widths, alpha=0.3, edge_color='#555555')
        if edges_collection is not None:
            if isinstance(edges_collection, list):
                for e in edges_collection:
                    e.set_zorder(2)
            else:
                edges_collection.set_zorder(2)
                
        nodes_collection = nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=node_sizes, alpha=0.9, edgecolors='white', linewidths=1.0)
        if nodes_collection is not None:
            nodes_collection.set_zorder(3)
        
        # 2. Prominent Representative Labeling (Top community leaders)
        community_nodes = {}
        for n in G.nodes:
            part = G.nodes[n]['partition']
            community_nodes.setdefault(part, []).append(n)

        candidate_nodes = []
        for part, nodes_in_part in community_nodes.items():
            sorted_nodes = sorted(nodes_in_part, key=lambda node: (G.nodes[node]['size'], G.nodes[node]['citations']), reverse=True)
            for rep_node in sorted_nodes[:top_per_community]:
                candidate_nodes.append(rep_node)

        # Limit to top 12 overall core leaders
        candidate_nodes = sorted(candidate_nodes, key=lambda n: G.nodes[n]['size'], reverse=True)[:12]
        labels = {n: G.nodes[n]['name'] for n in candidate_nodes}
                
        # Draw popping labels with crisp rounded callout boxes
        for node_id, label_text in labels.items():
            if node_id in pos:
                x, y = pos[node_id]
                ax.text(
                    x, y + 0.04, label_text,
                    fontsize=10, fontweight='bold', ha='center', va='bottom',
                    zorder=4,
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=partition_colors[G.nodes[node_id]['partition']], alpha=0.95, lw=1.5)
                )
        
        plt.title("Co-authorship Network Density & Key Community Leaders", fontsize=18, pad=15, fontweight="bold")
        plt.axis('off')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            if save_path.endswith(".pdf"):
                png_path = save_path[:-4] + ".png"
                plt.savefig(png_path, dpi=200, bbox_inches="tight")
        return fig

    def plot_circular_community_network(self, edges_df: pd.DataFrame, node_meta: pd.DataFrame, save_path: Optional[str] = None, top_per_community: int = 2, edge_alpha: float = 0.45, max_edge_width: float = 3.5):
        """
        Plots a publication-grade, uncluttered co-authorship network using a 
        Louvain-Grouped Circular Ring Layout with community-colored inter-community collaboration chords.
        """
        import networkx as nx
        import numpy as np
        import matplotlib.patches as mpatches
        from matplotlib.path import Path

        if edges_df.empty or node_meta.empty:
            return None
            
        fig, ax = plt.subplots(figsize=(16, 14))
        
        # Build full NetworkX Graph
        G_full = nx.Graph()
        for _, row in node_meta.iterrows():
            G_full.add_node(
                row['vertex'], 
                name=row['author_name'], 
                partition=row['partition'],
                size=row.get('num_publications', 1),
                citations=row.get('total_citations', 0)
            )
        for _, row in edges_df.iterrows():
            G_full.add_edge(row['source_id'], row['dest_id'], weight=row['weight'])
            
        # Select top prominent nodes across communities to keep visual presentation ultra-clean
        if len(G_full) > 100:
            top_nodes = sorted(G_full.nodes(), key=lambda n: (G_full.nodes[n]['size'], G_full.nodes[n]['citations']), reverse=True)[:100]
            G = G_full.subgraph(top_nodes).copy()
        else:
            G = G_full.copy()

        if len(G) == 0:
            G = G_full

        # --- LOUVAIN-GROUPED CIRCULAR LAYOUT ALGORITHM ---
        community_nodes = {}
        for n in G.nodes:
            part = G.nodes[n]['partition']
            community_nodes.setdefault(part, []).append(n)
            
        sorted_partitions = sorted(community_nodes.keys(), key=lambda p: len(community_nodes[p]), reverse=True)
        total_nodes = len(G.nodes)
        pos = {}
        angles = {}
        
        current_angle = 0.0
        gap_angle = (2 * np.pi * 0.15) / max(len(sorted_partitions), 1)
        available_angle = 2 * np.pi - (gap_angle * len(sorted_partitions))
        
        color_palette = sns.color_palette("tab10", max(len(sorted_partitions), 10))
        partition_colors = {p: color_palette[i % len(color_palette)] for i, p in enumerate(sorted_partitions)}

        radius = 1.0
        for i, part in enumerate(sorted_partitions):
            nodes_in_part = sorted(community_nodes[part], key=lambda n: G.nodes[n]['size'], reverse=True)
            part_angle_span = available_angle * (len(nodes_in_part) / total_nodes)
            
            angle_step = part_angle_span / max(len(nodes_in_part), 1)
            for j, node in enumerate(nodes_in_part):
                theta = current_angle + (j + 0.5) * angle_step
                pos[node] = (radius * np.cos(theta), radius * np.sin(theta))
                angles[node] = theta
                
            current_angle += part_angle_span + gap_angle

        # 1. Draw Community-Colored Inter-Community Collaboration Chords
        all_w = [G[u][v]['weight'] for u, v in G.edges]
        max_w = max(all_w) if all_w else 1
        
        for u, v in G.edges:
            p1, p2 = pos[u], pos[v]
            part1, part2 = G.nodes[u]['partition'], G.nodes[v]['partition']
            w = G[u][v]['weight']
            lw = (w / max_w) * max_edge_width + 0.8
            
            edge_c = partition_colors[part1]  # Color by source community
            
            if part1 == part2:
                # Intra-community edge (perimeter arc)
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=edge_c, alpha=edge_alpha + 0.1, lw=lw, zorder=2)
            else:
                # Inter-community curved chord
                path_data = [
                    (Path.MOVETO, p1),
                    (Path.CURVE3, (0.0, 0.0)),
                    (Path.CURVE3, p2)
                ]
                codes, verts = zip(*path_data)
                path = Path(verts, codes)
                patch = mpatches.PathPatch(path, facecolor='none', edgecolor=edge_c, alpha=edge_alpha, lw=lw, zorder=1)
                ax.add_patch(patch)

        # 2. Draw Nodes along Circular Ring
        all_sizes = [G.nodes[n]['size'] for n in G.nodes]
        max_s = max(all_sizes) if all_sizes else 1
        node_sizes = [(G.nodes[n]['size'] / max_s) * 500 + 100 for n in G.nodes]
        node_colors = [partition_colors[G.nodes[n]['partition']] for n in G.nodes]

        ax.scatter(
            [pos[n][0] for n in G.nodes],
            [pos[n][1] for n in G.nodes],
            s=node_sizes,
            c=node_colors,
            alpha=0.95,
            edgecolors='white',
            linewidths=1.2,
            zorder=3
        )

        # 3. Radial Outward Vector Labeling for ALL Nodes
        for node_id in G.nodes:
            if node_id in pos:
                theta = angles[node_id]
                r_label = radius + 0.04
                lx, ly = r_label * np.cos(theta), r_label * np.sin(theta)
                
                label_text = G.nodes[node_id]['name']
                deg_angle = np.degrees(theta) % 360
                
                # Polar angle text orientation (readable text math)
                if 90 < deg_angle <= 270:
                    rot = deg_angle + 180
                    ha = 'right'
                else:
                    rot = deg_angle
                    ha = 'left'
                
                # Font size scaled by publication importance
                size_ratio = G.nodes[node_id]['size'] / max_s
                fs = 7.0 + (size_ratio * 4.0)
                font_weight = 'bold' if size_ratio > 0.3 else 'normal'
                
                ax.text(
                    lx, ly, label_text,
                    fontsize=fs, fontweight=font_weight, ha=ha, va='center',
                    rotation=rot, rotation_mode='anchor',
                    color=partition_colors[G.nodes[node_id]['partition']],
                    zorder=4
                )

        ax.set_xlim(-1.65, 1.65)
        ax.set_ylim(-1.65, 1.65)
        plt.title("Louvain Community Clustered Co-authorship Ring Network", fontsize=18, pad=25, fontweight="bold")
        plt.axis('off')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            if save_path.endswith(".pdf"):
                png_path = save_path[:-4] + ".png"
                plt.savefig(png_path, dpi=200, bbox_inches="tight")
        return fig

    def plot_cocitation_network(self, cocit_df: pd.DataFrame, top_n: int = 30, title_map: Optional[dict] = None, save_path: Optional[str] = None):
        """
        Plots top co-cited papers network graph with short paper titles and 
        clickable OpenAlex / DOI hyperlinked badges.
        """
        if cocit_df.empty:
            return None
            
        import networkx as nx
        top_cocit = cocit_df.nlargest(top_n * 2, "co_citation_count")
        G = nx.Graph()
        
        # Built-in seminal paper titles dictionary for co-citation literature
        seminal_titles = {
            "W31182665": "Delorme et al. (2004) EEGLAB",
            "W2122816088": "Oostenveld et al. (2011) FieldTrip",
            "W2768132193": "Lawhern et al. (2018) EEGNet",
            "W2804784400": "Koelstra et al. (2012) DEAP Dataset",
            "W3003415550": "Goldberger et al. (2000) PhysioNet",
            "W4315754639": "Schirrmeister et al. (2017) Deep Learning",
            "W1861891407": "Makeig et al. (1996) BSS Artifact Removal",
            "W1877917243": "Wolpaw et al. (2002) Brain-Computer Interfaces",
            "W1502633200": "Ang et al. (2008) Filter Bank CSP",
            "W1502967669": "Pfurtscheller et al. (1999) Event-Related Sync",
            "W1593442063": "Polich et al. (2007) Updating P300",
            "W2137604100": "Klimesch et al. (1999) EEG Alpha Oscillations",
            "W2567564314": "Bell & Sejnowski (1995) InfoMax ICA",
            "W2125744415": "Brainard et al. (1997) Psychophysics Toolbox"
        }

        # Build node title lookup
        def _get_short_title(raw_id: str) -> str:
            clean_id = str(raw_id).strip().rstrip("/")
            wid = clean_id.split("/")[-1]
            if wid in seminal_titles:
                return seminal_titles[wid]
                
            if title_map:
                if clean_id in title_map and title_map[clean_id].get("title"):
                    words = title_map[clean_id]["title"].split()
                    return " ".join(words[:5]) + ("..." if len(words) > 5 else "")
                if wid in title_map and title_map[wid].get("title"):
                    words = title_map[wid]["title"].split()
                    return " ".join(words[:5]) + ("..." if len(words) > 5 else "")
                    
            if wid.startswith("W"):
                try:
                    import urllib.request, json
                    req = urllib.request.Request(f"https://api.openalex.org/works/{wid}", headers={"User-Agent": "BibliometricPipeline/1.0"})
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        res_data = json.loads(resp.read().decode('utf-8'))
                        t = res_data.get("display_name", "")
                        authors = res_data.get("authorships", [])
                        yr = res_data.get("publication_year", "")
                        if t:
                            words = t.split()
                            short_t = " ".join(words[:4]) + ("..." if len(words) > 4 else "")
                            if authors:
                                first_au = authors[0].get("author", {}).get("display_name", "").split()[-1]
                                title_str = f"{first_au} et al. ({yr}) {short_t}"
                            else:
                                title_str = short_t
                            seminal_titles[wid] = title_str
                            return title_str
                except Exception:
                    pass

            if "10." in clean_id:
                return f"DOI: {clean_id[:25]}..."
            return str(clean_id)[:30]

        def _get_url(raw_id: str) -> str:
            clean_id = str(raw_id).strip().rstrip("/")
            wid = clean_id.split("/")[-1]
            if title_map:
                if clean_id in title_map and title_map[clean_id].get("url"):
                    return title_map[clean_id]["url"]
                if wid in title_map and title_map[wid].get("url"):
                    return title_map[wid]["url"]
            if wid in seminal_titles:
                return f"https://openalex.org/{wid}"
            if wid.startswith("W"):
                return f"https://openalex.org/{wid}"
            elif "10." in clean_id:
                doi = clean_id[clean_id.find("10."):]
                return f"https://doi.org/{doi}"
            return f"https://openalex.org/{wid}"

        for _, row in top_cocit.iterrows():
            c1_raw = str(row['cited_1']).strip()
            c2_raw = str(row['cited_2']).strip()
            
            c1_label = _get_short_title(c1_raw)
            c2_label = _get_short_title(c2_raw)
            
            G.add_node(c1_label, raw_id=c1_raw, url=_get_url(c1_raw))
            G.add_node(c2_label, raw_id=c2_raw, url=_get_url(c2_raw))
            G.add_edge(c1_label, c2_label, weight=row['co_citation_count'])
            
        if G.number_of_nodes() == 0:
            return None
            
        fig, ax = plt.subplots(figsize=(16, 12))
        pos = nx.spring_layout(G, k=0.45, iterations=60, seed=42)
        
        degrees = dict(G.degree(weight='weight'))
        node_sizes = [degrees.get(n, 1) * 35 + 120 for n in G.nodes]
        
        nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.3, edge_color="#444444", width=1.5)
        
        # Draw node circles with hyperlinks attached
        for n in G.nodes:
            x, y = pos[n]
            sz = degrees.get(n, 1) * 35 + 120
            url = G.nodes[n].get("url", "")
            ax.scatter(x, y, s=sz, c="#1f77b4", alpha=0.9, edgecolors="white", linewidths=1.2, zorder=3, url=url)
        
        # Attach hyperlinked text badges for all nodes
        top_labels = sorted(G.nodes, key=lambda n: degrees.get(n, 0), reverse=True)
        for n in top_labels:
            x, y = pos[n]
            url = G.nodes[n].get("url", "")
            
            txt_obj = ax.text(
                x, y + 0.035, n, 
                fontsize=8.5, fontweight='bold', ha='center', va='bottom',
                url=url,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#1f77b4", alpha=0.95, lw=1.2)
            )
            txt_obj.set_url(url)
                    
        plt.title("Co-Citation Network (Top Frequently Co-Cited Reference Literature)", fontsize=16, pad=15, fontweight="bold")
        plt.axis('off')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            if save_path.endswith(".pdf"):
                png_path = save_path[:-4] + ".png"
                plt.savefig(png_path, dpi=200, bbox_inches="tight")
        return fig

    def plot_keywords_cagr(self, cagr_df: pd.DataFrame, top_n: int = 15, save_path: Optional[str] = None):
        """Plots the CAGR percentage of the top N keywords."""
        if cagr_df.empty:
            return None
        
        # Sort and get top N keywords
        top_data = cagr_df.nlargest(top_n, "cagr_percent")
        
        plt.figure(figsize=(14, 8))
        sns.barplot(data=top_data, x="cagr_percent", y="standardized_word", palette="viridis")
        
        plt.title(f"Top {top_n} Trending Research Focus Areas (Keyword CAGR %)", fontsize=16, pad=15)
        plt.xlabel("Compound Annual Growth Rate (CAGR %)", fontsize=12)
        plt.ylabel("Research Keyword", fontsize=12)
        plt.grid(True, axis="x", linestyle="--", alpha=0.5)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300)
        return plt.gcf()

    def plot_topic_distribution(self, topic_info_df: pd.DataFrame, top_n: int = 10, save_path: Optional[str] = None):
        """Plots the size (number of publications) of top BERTopic clusters."""
        if topic_info_df.empty:
            return None
            
        # Drop outlier topic (-1) if present
        df = topic_info_df[topic_info_df["Topic"] != -1].nlargest(top_n, "Count")
        
        plt.figure(figsize=(14, 8))
        sns.barplot(data=df, x="Count", y="Name", palette="mako")
        
        plt.title(f"Dominant Research Themes (Publications per Topic)", fontsize=16, pad=15)
        plt.xlabel("Number of Publications", fontsize=12)
        plt.ylabel("Topic Description (Top Words)", fontsize=12)
        plt.grid(True, axis="x", linestyle="--", alpha=0.5)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300)
        return plt.gcf()

    def plot_percolation(self, percolation_df: pd.DataFrame, weight_col: str, save_path: Optional[str] = None):
        """Plots 3-subplot percolation analysis (Network Size, Connected Components, and LCC % vs cutoff)."""
        if percolation_df.empty:
            return None

        plt.figure(figsize=(18, 7))

        # Subplot 1: Network Size (Log Scale)
        plt.subplot(1, 3, 1)
        plt.plot(percolation_df['cutoff'], percolation_df['num_edges'], marker='o', linestyle='-', color='blue', label='Number of Edges')
        plt.plot(percolation_df['cutoff'], percolation_df['num_nodes_in_filtered_graph'], marker='x', linestyle='--', color='green', label='Nodes in Filtered Graph')
        plt.title(f'Network Size vs. {weight_col} Cutoff')
        plt.xlabel(f'{weight_col} Cutoff (exclusive)')
        plt.ylabel('Count (Log Scale)')
        plt.yscale('log')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend()

        # Subplot 2: Number of Components
        plt.subplot(1, 3, 2)
        plt.plot(percolation_df['cutoff'], percolation_df['num_components'], marker='o', linestyle='-', color='orange', label='Number of Components')
        plt.title(f'Number of Components vs. {weight_col} Cutoff')
        plt.xlabel(f'{weight_col} Cutoff (exclusive)')
        plt.ylabel('Number of Components')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend()

        # Subplot 3: LCC Size (%)
        plt.subplot(1, 3, 3)
        plt.plot(percolation_df['cutoff'], percolation_df['lcc_nodes_percentage_of_filtered'], marker='o', linestyle='-', color='red', label='LCC % (of filtered nodes)')
        plt.plot(percolation_df['cutoff'], percolation_df['lcc_nodes_percentage_of_total_initial'], marker='x', linestyle='--', color='purple', label='LCC % (of total initial nodes)')
        plt.title(f'LCC Size (%) vs. {weight_col} Cutoff')
        plt.xlabel(f'{weight_col} Cutoff (exclusive)')
        plt.ylabel('LCC Size Percentage')
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend()

        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300)
            plt.close()
        return plt.gcf()

