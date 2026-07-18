import matplotlib.pyplot as plt
import seaborn as sns
import polars as pl
import pandas as pd
from typing import Optional

class Visualization:
    def __init__(self, style: str = "whitegrid"):
        sns.set_style(style)
        plt.rcParams["figure.figsize"] = (12, 7)

    def plot_yearly_growth(self, df: pl.DataFrame, save_path: Optional[str] = None):
        """Plots publication counts and growth percentages."""
        yearly_counts = df.group_by("Year").len().sort("Year")
        
        # Calculate growth
        yearly_counts = yearly_counts.with_columns(
            pl.col("len").shift(1).alias("previous_year_len")
        ).with_columns(
            pl.when(pl.col("previous_year_len").is_null() | (pl.col("previous_year_len") == 0))
            .then(0.0)
            .otherwise(((pl.col("len") - pl.col("previous_year_len")) / pl.col("previous_year_len") * 100))
            .alias("growth_pct")
        )

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

        # Plot 1: Counts
        ax1.bar(yearly_counts["Year"], yearly_counts["len"], color='skyblue')
        ax1.set_ylabel("Number of Publications")
        ax1.set_title("Publication Evolution")
        ax1.grid(axis='y', linestyle='--', alpha=0.7)

        # Plot 2: Growth
        bars = ax2.bar(yearly_counts["Year"], yearly_counts["growth_pct"], color='lightcoral')
        ax2.set_ylabel("Yearly Growth (%)")
        ax2.axhline(0, color='grey', linewidth=0.8)
        ax2.grid(axis='y', linestyle='--', alpha=0.7)

        # Add labels
        for bar in bars:
            yval = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2, yval + (0.5 if yval >= 0 else -1.5),
                     f'{yval:.1f}%', ha='center', va='bottom' if yval >= 0 else 'top',
                     fontsize=9)

        plt.xticks(yearly_counts["Year"], rotation=45)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path)
        return fig

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

    def plot_network(self, edges_df: pd.DataFrame, node_meta: pd.DataFrame, save_path: Optional[str] = None):
        """
        Plots a high-resolution, static co-authorship network with Louvain community colors.
        
        Args:
            edges_df: DataFrame with source_id, dest_id, weight columns.
            node_meta: DataFrame with vertex, partition (community), author_name, num_publications columns.
            save_path: Optional path to save the generated PDF.
        """
        import networkx as nx
        if edges_df.empty or node_meta.empty:
            return None
            
        plt.figure(figsize=(16, 12))
        
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
            
        # Layout calculation
        pos = nx.spring_layout(G, k=0.18, iterations=100, seed=42)
        
        # Color mapping (community partitions)
        partitions = [G.nodes[n]['partition'] for n in G.nodes]
        unique_partitions = list(set(partitions))
        color_palette = sns.color_palette("tab10", len(unique_partitions))
        partition_colors = {p: color_palette[i % len(color_palette)] for i, p in enumerate(unique_partitions)}
        node_colors = [partition_colors[G.nodes[n]['partition']] for n in G.nodes]
        
        # Node sizing scaling
        node_sizes = [G.nodes[n]['size'] * 150 + 80 for n in G.nodes]
        
        # Edge weights scaling
        edge_widths = [G[u][v]['weight'] * 0.8 for u, v in G.edges]
        
        # Draw elements
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, alpha=0.9, edgecolors='black', linewidths=0.5)
        nx.draw_networkx_edges(G, pos, width=edge_widths, alpha=0.25, edge_color='gray')
        
        # Label top authors to avoid clutter
        labels = {}
        for n in G.nodes:
            if G.nodes[n]['size'] >= 2 or len(G.nodes) < 30:
                labels[n] = G.nodes[n]['name']
                
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=8, font_family="sans-serif", font_weight="bold", alpha=0.8)
        
        plt.title("Co-authorship Network & Louvain Communities", fontsize=18, pad=15)
        plt.axis('off')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300)
        return plt.gcf()

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

