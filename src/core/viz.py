import matplotlib.pyplot as plt
import seaborn as sns
import polars as pl
import pandas as pd
from typing import Optional

class Visualization:
    def __init__(self, style: str = "whitegrid"):
        sns.set_style(style)
        plt.rcParams["figure.figsize"] = (12, 7)

    def plot_yearly_growth(self, df: pl.DataFrame, save_path: Optional[str] = None) -> Optional[pd.DataFrame]:
        """Plots publication counts and growth percentages, including current-year annualized projections."""
        import datetime
        if df.is_empty():
            return None

        yearly_counts = df.group_by("Year").len().sort("Year")
        
        # Cast len to Int64 to prevent unsigned underflow when counts decrease
        yearly_counts = yearly_counts.with_columns(pl.col("len").cast(pl.Int64))
        
        # Convert to pandas for easier manipulation and plotting
        pdf = yearly_counts.to_pandas()
        pdf["previous_year_len"] = pdf["len"].shift(1)
        pdf["growth_pct"] = ((pdf["len"] - pdf["previous_year_len"]) / pdf["previous_year_len"]) * 100
        pdf["growth_pct"] = pdf["growth_pct"].fillna(0.0)
        
        # Detect current year projection
        now = datetime.datetime.now()
        current_year = now.year
        current_month = now.month
        
        pdf["is_projected"] = False
        pdf["projected_len"] = pdf["len"]
        pdf["projected_growth_pct"] = pdf["growth_pct"]
        
        if current_year in pdf["Year"].values:
            idx = pdf.index[pdf["Year"] == current_year][0]
            elapsed_fraction = max(current_month / 12.0, 1/12)
            actual_count = pdf.loc[idx, "len"]
            projected_count = int(round(actual_count / elapsed_fraction))
            pdf.loc[idx, "projected_len"] = projected_count
            pdf.loc[idx, "is_projected"] = True
            
            prev_len = pdf.loc[idx, "previous_year_len"]
            if pd.notnull(prev_len) and prev_len > 0:
                proj_growth = ((projected_count - prev_len) / prev_len) * 100
                pdf.loc[idx, "projected_growth_pct"] = proj_growth

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

        years = pdf["Year"].astype(str).tolist()

        # Plot 1: Counts
        for i, row in pdf.iterrows():
            if row["is_projected"]:
                actual_val = int(row["len"])
                proj_delta = int(row["projected_len"]) - actual_val
                # Solid base for YTD actual
                ax1.bar(years[i], actual_val, color='skyblue', label='Observed (YTD)' if i == 0 else "")
                # Hatched extension for projected full year
                if proj_delta > 0:
                    ax1.bar(years[i], proj_delta, bottom=actual_val, color='lightskyblue', edgecolor='royalblue', linestyle='--', hatch='//', label='Projected Full Year')
                ax1.text(i, row["projected_len"] + (row["projected_len"] * 0.01), f'Proj: {int(row["projected_len"]):,}\n(YTD: {actual_val:,})', ha='center', va='bottom', fontsize=8, fontweight='bold', color='royalblue')
            else:
                ax1.bar(years[i], row["len"], color='skyblue', label='Observed Publications' if i == 0 else "")
                ax1.text(i, row["len"] + (row["len"] * 0.01), f'{int(row["len"]):,}', ha='center', va='bottom', fontsize=8)

        ax1.set_ylabel("Number of Publications")
        ax1.set_title("Publication Evolution & Current Year Projections")
        ax1.grid(axis='y', linestyle='--', alpha=0.7)
        ax1.legend(loc="upper left")

        # Plot 2: Growth
        for i, row in pdf.iterrows():
            if row["is_projected"]:
                proj_growth = row["projected_growth_pct"]
                actual_growth = row["growth_pct"]
                ax2.bar(years[i], proj_growth, color='coral', edgecolor='firebrick', linestyle='--', hatch='//', alpha=0.85)
                ax2.text(i, proj_growth + (1.5 if proj_growth >= 0 else -3.0),
                         f'Proj: {proj_growth:.1f}%\n(YTD: {actual_growth:.1f}%)', ha='center', va='bottom' if proj_growth >= 0 else 'top',
                         fontsize=8, fontweight='bold', color='firebrick')
            else:
                yval = row["growth_pct"]
                ax2.bar(years[i], yval, color='lightcoral')
                ax2.text(i, yval + (0.5 if yval >= 0 else -1.5),
                         f'{yval:.1f}%', ha='center', va='bottom' if yval >= 0 else 'top',
                         fontsize=8)

        ax2.set_ylabel("Yearly Growth (%)")
        ax2.axhline(0, color='grey', linewidth=0.8)
        ax2.grid(axis='y', linestyle='--', alpha=0.7)

        plt.xticks(rotation=45)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300)
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
            
        labels = {}
        for part, nodes_in_part in community_nodes.items():
            # Sort nodes in community by size (publications count) descending
            sorted_nodes = sorted(nodes_in_part, key=lambda node: G.nodes[node]['size'], reverse=True)
            for rep_node in sorted_nodes[:top_per_community]:
                labels[rep_node] = G.nodes[rep_node]['name']
                
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

