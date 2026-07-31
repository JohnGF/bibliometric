import matplotlib.pyplot as plt
import seaborn as sns
import polars as pl
import pandas as pd
from typing import Optional

class Visualization:
    def __init__(self, style: str = "whitegrid"):
        sns.set_style(style)
        plt.rcParams["figure.figsize"] = (12, 7)

    def plot_yearly_growth(self, df: pl.DataFrame, save_path: Optional[str] = None, max_year: int = 2024, min_year: int = 2014) -> Optional[pd.DataFrame]:
        """Plots publication counts and YoY growth percentages for complete historical years."""
        if df.is_empty():
            return None

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

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
        years = pdf["Year"].astype(str).tolist()

        # Plot 1: Counts
        for i, row in pdf.iterrows():
            ax1.bar(years[i], row["len"], color='skyblue', label='Observed Publications' if i == 0 else "")
            ax1.text(i, row["len"] + (row["len"] * 0.01), f'{int(row["len"]):,}', ha='center', va='bottom', fontsize=9, fontweight='bold')

        ax1.set_ylabel("Number of Publications", fontsize=11, fontweight='bold')
        ax1.set_title(f"Historical Publication Evolution ({min_year} - {max_year})", fontsize=14, pad=15, fontweight="bold")
        ax1.grid(axis='y', linestyle='--', alpha=0.7)
        ax1.legend(loc="upper left")

        # Plot 2: YoY Growth Rate (%)
        for i, row in pdf.iterrows():
            yval = row["growth_pct"]
            color = 'lightcoral' if yval >= 0 else 'lightskyblue'
            ax2.bar(years[i], yval, color=color, edgecolor='black', linewidth=0.5)
            offset = 0.5 if yval >= 0 else -2.5
            ax2.text(i, yval + offset, f'{yval:+.1f}%', ha='center', va='bottom' if yval >= 0 else 'top', fontsize=9, fontweight='bold')

        ax2.set_ylabel("YoY Growth Rate (%)", fontsize=11, fontweight='bold')
        ax2.axhline(0, color='grey', linewidth=0.8, linestyle='--')
        ax2.grid(axis='y', linestyle='--', alpha=0.7)

        plt.xticks(rotation=45)
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

    def plot_network(self, edges_df: pd.DataFrame, node_meta: pd.DataFrame, save_path: Optional[str] = None, top_per_community: int = 1, show_heatmap: bool = True):
        """
        Plots a high-resolution, static co-authorship network with fused edge density heatmaps
        and community-representative prominent labels.
        """
        import networkx as nx

        if edges_df.empty or node_meta.empty:
            return None
            
        fig, ax = plt.subplots(figsize=(16, 12))
        
        # Build NetworkX Graph
        G = nx.Graph()
        
        # Add nodes with attributes
        for _, row in node_meta.iterrows():
            G.add_node(
                row['vertex'], 
                name=row['author_name'], 
                partition=row['partition'],
                size=row.get('num_publications', 1)
            )
            
        # Add edges
        for _, row in edges_df.iterrows():
            G.add_edge(row['source_id'], row['dest_id'], weight=row['weight'])
            
        # Layout calculation: reuse pre-computed x, y coordinates if available in node_meta
        if 'x' in node_meta.columns and 'y' in node_meta.columns and not node_meta['x'].isnull().all():
            pos = {row['vertex']: (row['x'], row['y']) for _, row in node_meta.iterrows() if row['vertex'] in G}
        else:
            pos = nx.spring_layout(G, k=0.35, iterations=100, seed=42)
            # Cache coordinates back into node_meta for instant future re-renders
            node_meta['x'] = node_meta['vertex'].map(lambda v: pos[v][0] if v in pos else None)
            node_meta['y'] = node_meta['vertex'].map(lambda v: pos[v][1] if v in pos else None)
            if save_path:
                try:
                    nodes_csv = save_path.replace("network_graph.pdf", "network_nodes.csv")
                    if os.path.exists(nodes_csv):
                        node_meta.to_csv(nodes_csv, index=False)
                except Exception:
                    pass
            
        # 1. Edge Density Heatmap Layer
        if show_heatmap and len(G.edges) > 5:
            try:
                # Extract edge midpoint and endpoint positions for 2D KDE density
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
                        cmap="YlOrRd",
                        fill=True,
                        thresh=0.08,
                        levels=10,
                        alpha=0.3,
                        zorder=1
                    )
            except Exception:
                pass

        # Color mapping (community partitions)
        partitions = [G.nodes[n]['partition'] for n in G.nodes]
        unique_partitions = list(set(partitions))
        color_palette = sns.color_palette("tab10", len(unique_partitions))
        partition_colors = {p: color_palette[i % len(color_palette)] for i, p in enumerate(unique_partitions)}
        node_colors = [partition_colors[G.nodes[n]['partition']] for n in G.nodes]
        
        # Node sizing scaling
        node_sizes = [G.nodes[n]['size'] * 150 + 80 for n in G.nodes]
        
        # Edge weights scaling
        edge_widths = [G[u][v]['weight'] * 0.6 for u, v in G.edges]
        
        # Draw elements
        edges_collection = nx.draw_networkx_edges(G, pos, ax=ax, width=edge_widths, alpha=0.2, edge_color='gray')
        if edges_collection is not None:
            if isinstance(edges_collection, list):
                for e in edges_collection:
                    e.set_zorder(2)
            else:
                edges_collection.set_zorder(2)
                
        nodes_collection = nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=node_sizes, alpha=0.85, edgecolors='black', linewidths=0.5)
        if nodes_collection is not None:
            nodes_collection.set_zorder(3)
        
        # 2. Prominent Representative Labeling (Top N per community)
        community_nodes = {}
        for n in G.nodes:
            part = G.nodes[n]['partition']
            community_nodes.setdefault(part, []).append(n)
            
        # Determine minimum size threshold for label eligibility (90th percentile or min 5 publications)
        all_sizes = [G.nodes[n]['size'] for n in G.nodes]
        min_label_size = max(5, float(pd.Series(all_sizes).quantile(0.90))) if len(all_sizes) > 10 else 2

        candidate_nodes = []
        for part, nodes_in_part in community_nodes.items():
            sorted_nodes = sorted(nodes_in_part, key=lambda node: G.nodes[node]['size'], reverse=True)
            for rep_node in sorted_nodes[:top_per_community]:
                if G.nodes[rep_node]['size'] >= min_label_size:
                    candidate_nodes.append(rep_node)

        # Limit to top overall core leaders across the entire network (max 8-10 badges)
        candidate_nodes = sorted(candidate_nodes, key=lambda n: G.nodes[n]['size'], reverse=True)[:10]
        labels = {n: G.nodes[n]['name'] for n in candidate_nodes}
                
        # Draw popping labels with white rounded bounding boxes for top community leaders
        for node_id, label_text in labels.items():
            if node_id in pos:
                x, y = pos[node_id]
                ax.text(
                    x, y + 0.035, label_text,
                    fontsize=9, fontweight='bold', ha='center', va='bottom',
                    zorder=4,
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=partition_colors[G.nodes[node_id]['partition']], alpha=0.9, lw=1.2)
                )
        
        plt.title("Co-authorship Network Density & Key Community Leaders", fontsize=18, pad=15)
        plt.axis('off')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300)
            if save_path.endswith(".pdf"):
                png_path = save_path[:-4] + ".png"
                plt.savefig(png_path, dpi=200)
        return fig

    def plot_cocitation_network(self, cocit_df: pd.DataFrame, top_n: int = 30, save_path: Optional[str] = None):
        """Plots top co-cited papers network graph."""
        if cocit_df.empty:
            return None
            
        import networkx as nx
        top_cocit = cocit_df.nlargest(top_n * 2, "co_citation_count")
        G = nx.Graph()
        for _, row in top_cocit.iterrows():
            c1 = str(row['cited_1'])[:35]
            c2 = str(row['cited_2'])[:35]
            G.add_edge(c1, c2, weight=row['co_citation_count'])
            
        if G.number_of_nodes() == 0:
            return None
            
        fig, ax = plt.subplots(figsize=(16, 12))
        pos = nx.spring_layout(G, k=0.4, iterations=50, seed=42)
        
        degrees = dict(G.degree(weight='weight'))
        node_sizes = [degrees.get(n, 1) * 30 + 100 for n in G.nodes]
        
        nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.25, edge_color="gray", width=1.5)
        nx.draw_networkx_nodes(G, pos, ax=ax, node_size=node_sizes, node_color="#2b5c8f", alpha=0.85, edgecolors="black")
        
        top_labels = sorted(G.nodes, key=lambda n: degrees.get(n, 0), reverse=True)[:12]
        for n in top_labels:
            x, y = pos[n]
            ax.text(x, y + 0.04, n, fontsize=8, fontweight='bold', ha='center', va='bottom',
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#2b5c8f", alpha=0.9))
                    
        plt.title("Co-Citation Network (Top Frequently Co-Cited Reference Literature)", fontsize=16, pad=15)
        plt.axis('off')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300)
            if save_path.endswith(".pdf"):
                png_path = save_path[:-4] + ".png"
                plt.savefig(png_path, dpi=200)
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

