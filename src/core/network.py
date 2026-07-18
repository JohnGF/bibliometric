import polars as pl
import pandas as pd
from collections import Counter
from typing import Tuple, List, Dict
import logging

# GPU/CPU Fallback Logic
try:
    import cudf
    import cugraph
    import rmm
    # Test if GPU is actually available
    import cupy
    cupy.cuda.Device(0).use()
    HAS_GPU = True
except Exception:
    HAS_GPU = False

if not HAS_GPU:
    import networkx as nx
    import community as community_louvain  # python-louvain

class NetworkAnalysis:
    def __init__(self, use_gpu: bool = True):
        self.use_gpu = use_gpu and HAS_GPU
        self.graph = None
        self.node_metadata = None

    def build_co_authorship_graph(self, df: pl.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        logging.info("Building co-authorship network...")
        
        # Extract author-paper pairs
        author_paper_data = []
        for row in df.to_dicts():
            authors_val = row.get('Authors')
            if not authors_val:
                continue
            
            # Split, clean, and filter authors
            authors = []
            for a in str(authors_val).split(';'):
                clean_a = a.strip().replace("\n", " ").replace("\r", " ")
                # Skip empty, nan, none, or unknown names (case-insensitive)
                if not clean_a or clean_a.lower() in ("nan", "none", "unknown"):
                    continue
                authors.append(clean_a)
                
            for author in authors:
                # Clean affiliation by stripping newlines to guarantee clean single-line CSV format
                affil = row.get('Affiliations') or ""
                if isinstance(affil, str):
                    affil = affil.replace("\n", " ").replace("\r", " ").strip()
                else:
                    affil = ""
                    
                author_paper_data.append({
                    'author_name': author,
                    'paper_id': row.get('DOI') or row.get('Title'),
                    'paper_cite_count': row.get('Cite Count') or 0,
                    'affiliation': affil
                })
        
        if not author_paper_data:
            return pd.DataFrame(), pd.DataFrame()

        ap_df = pl.DataFrame(author_paper_data)
        
        # Ensure affiliation is treated as a list of strings
        if ap_df.schema.get("affiliation") == pl.String:
            ap_df = ap_df.with_columns(pl.col("affiliation").str.split(";"))

        # Build edges (co-authorship)
        paper_groups = ap_df.group_by('paper_id').agg(pl.col('author_name'))
        edges = Counter()
        for authors_list in paper_groups['author_name']:
            authors = sorted(list(set(authors_list)))
            for i in range(len(authors)):
                for j in range(i + 1, len(authors)):
                    edges[(authors[i], authors[j])] += 1
        
        edges_list = [{'source': k[0], 'destination': k[1], 'weight': v} for k, v in edges.items()]
        if not edges_list:
            return pd.DataFrame(), pd.DataFrame()

        edges_pdf = pd.DataFrame(edges_list)
        unique_authors = sorted(list(set(edges_pdf['source']) | set(edges_pdf['destination'])))
        author_to_id = {name: i for i, name in enumerate(unique_authors)}
        
        edges_pdf['source_id'] = edges_pdf['source'].map(author_to_id)
        edges_pdf['dest_id'] = edges_pdf['destination'].map(author_to_id)

        if self.use_gpu:
            edges_gdf = cudf.from_pandas(edges_pdf[['source_id', 'dest_id', 'weight']])
            self.graph = cugraph.Graph()
            self.graph.from_cudf_edgelist(edges_gdf, source='source_id', destination='dest_id', edge_attr='weight')
            partition, _ = cugraph.louvain(self.graph)
            pagerank = cugraph.pagerank(self.graph)
            betweenness = cugraph.betweenness_centrality(self.graph)
            degree = cugraph.degree_centrality(self.graph)

            partition = partition.merge(pagerank, on='vertex')
            partition = partition.merge(betweenness, on='vertex')
            partition = partition.merge(degree, on='vertex')
        else:
            edges_pdf_cpu = edges_pdf[['source_id', 'dest_id', 'weight']]
            nx_graph = nx.from_pandas_edgelist(edges_pdf_cpu, source='source_id', target='dest_id', edge_attr='weight')
            self.graph = nx_graph
            partition_dict = community_louvain.best_partition(nx_graph)
            pagerank_dict = nx.pagerank(nx_graph, weight='weight')
            betweenness_dict = nx.betweenness_centrality(nx_graph, weight='weight')
            degree_dict = nx.degree_centrality(nx_graph)

            partition = pd.DataFrame([
                {
                    'vertex': k,
                    'partition': v,
                    'pagerank': pagerank_dict[k],
                    'betweenness_centrality': betweenness_dict[k],
                    'degree_centrality': degree_dict[k]
                }
                for k, v in partition_dict.items()
            ])

        # Node metadata (metrics and affiliations)
        metrics = ap_df.group_by('author_name').agg([
            pl.col('paper_cite_count').sum().alias('total_citations'),
            pl.col('paper_id').n_unique().alias('num_publications')
        ])
        
        # Correctly aggregate affiliations: explode lists, then group and collect unique sorted values
        affiliations = ap_df.explode('affiliation').group_by('author_name').agg([
            pl.col('affiliation').unique().sort().alias('affiliation_list')
        ]).with_columns([
            pl.col('affiliation_list').list.join("; ").alias('affiliations_str')
        ])

        # Perform joins on DataFrames
        node_meta_pl = metrics.join(affiliations, on='author_name', how='left')
        
        # Join with author IDs
        id_mapping = pl.DataFrame({
            'author_name': list(author_to_id.keys()), 
            'vertex': list(author_to_id.values())
        })
        node_meta_pl = node_meta_pl.join(id_mapping, on='author_name').drop('affiliation_list')
        
        node_meta_pd = node_meta_pl.to_pandas()
        if self.use_gpu:
            self.node_metadata = partition.to_pandas().merge(node_meta_pd, on='vertex', how='left')
        else:
            self.node_metadata = partition.merge(node_meta_pd, on='vertex', how='left')

        return edges_pdf, self.node_metadata

    def build_directed_citation_graph(self, df: pl.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Builds a directed citation network tracking citation flows.
        Nodes are papers (using EID or DOI) and edges represent citations.
        Returns the edges DataFrame and node metadata DataFrame.
        """
        logging.info("Building directed citation network...")

        edges_list = []
        node_records = []

        # We need mapping from paper ID (EID or DOI) to Title/Year for metadata
        paper_info = {}

        for row in df.to_dicts():
            paper_id = row.get("EID") or row.get("DOI")
            if not paper_id:
                continue

            paper_id = str(paper_id).strip()

            # Store paper metadata
            if paper_id not in paper_info:
                paper_info[paper_id] = {
                    "title": row.get("Title", "Unknown Title"),
                    "year": row.get("Year", None),
                    "cite_count": row.get("Cite Count", 0)
                }

            references = row.get("References")
            if not references or not isinstance(references, str):
                continue

            refs = [r.strip() for r in references.split(";") if r.strip()]
            for ref in refs:
                # Directed edge: from citing paper to cited paper (reference)
                edges_list.append({
                    "source": paper_id,
                    "destination": ref,
                    "weight": 1
                })
                # Add a dummy record for cited paper if it doesn't exist to ensure it gets an ID
                if ref not in paper_info:
                    paper_info[ref] = {
                        "title": "Out of dataset paper",
                        "year": None,
                        "cite_count": 0
                    }

        if not edges_list:
            logger.warning("No citation edges found in dataset.")
            return pd.DataFrame(), pd.DataFrame()

        edges_pdf = pd.DataFrame(edges_list)

        # Give integer IDs to string paper IDs
        unique_papers = sorted(list(set(edges_pdf['source']) | set(edges_pdf['destination'])))
        paper_to_id = {pid: i for i, pid in enumerate(unique_papers)}

        edges_pdf['source_id'] = edges_pdf['source'].map(paper_to_id)
        edges_pdf['dest_id'] = edges_pdf['destination'].map(paper_to_id)

        node_meta_list = []
        for pid, pid_int in paper_to_id.items():
            info = paper_info.get(pid, {})
            node_meta_list.append({
                "vertex": pid_int,
                "paper_id": pid,
                "title": info.get("title", ""),
                "year": info.get("year", None),
                "cite_count": info.get("cite_count", 0)
            })

        node_meta_df = pd.DataFrame(node_meta_list)

        if self.use_gpu:
            edges_gdf = cudf.from_pandas(edges_pdf[['source_id', 'dest_id', 'weight']])
            citation_graph = cugraph.Graph(directed=True)
            citation_graph.from_cudf_edgelist(edges_gdf, source='source_id', destination='dest_id', edge_attr='weight')
            pagerank = cugraph.pagerank(citation_graph)
            node_meta_df = node_meta_df.merge(pagerank.to_pandas(), on='vertex', how='left')
        else:
            edges_pdf_cpu = edges_pdf[['source_id', 'dest_id', 'weight']]
            nx_graph = nx.from_pandas_edgelist(edges_pdf_cpu, source='source_id', target='dest_id', edge_attr='weight', create_using=nx.DiGraph())
            pagerank_dict = nx.pagerank(nx_graph, weight='weight')

            pr_df = pd.DataFrame([{'vertex': k, 'pagerank': v} for k, v in pagerank_dict.items()])
            node_meta_df = node_meta_df.merge(pr_df, on='vertex', how='left')

        return edges_pdf, node_meta_df

    def build_country_collaboration_graph(self, df: pl.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Builds a country-to-country undirected network where edges represent co-authorship.
        """
        from src.core.ingestion import extract_countries

        logging.info("Building country collaboration network...")

        edges = Counter()
        node_counts = Counter()

        for row in df.to_dicts():
            affil = row.get("Affiliations")
            if not affil or not isinstance(affil, str):
                continue

            countries = extract_countries(affil)
            if not countries:
                continue

            # Node weights (number of papers per country)
            for country in countries:
                node_counts[country] += 1

            # Edges (co-authorship between countries on the same paper)
            countries = sorted(list(set(countries)))
            for i in range(len(countries)):
                for j in range(i + 1, len(countries)):
                    edges[(countries[i], countries[j])] += 1

        edges_list = [{'source': k[0], 'destination': k[1], 'weight': v} for k, v in edges.items()]
        if not edges_list:
            logger.warning("No country collaboration edges found.")
            return pd.DataFrame(), pd.DataFrame()

        edges_pdf = pd.DataFrame(edges_list)
        unique_countries = sorted(list(set(edges_pdf['source']) | set(edges_pdf['destination'])))
        country_to_id = {name: i for i, name in enumerate(unique_countries)}

        edges_pdf['source_id'] = edges_pdf['source'].map(country_to_id)
        edges_pdf['dest_id'] = edges_pdf['destination'].map(country_to_id)

        # Build node metadata
        node_meta_list = []
        for country, cid in country_to_id.items():
            node_meta_list.append({
                "vertex": cid,
                "country": country,
                "num_publications": node_counts.get(country, 0)
            })

        node_meta_df = pd.DataFrame(node_meta_list)

        if self.use_gpu:
            edges_gdf = cudf.from_pandas(edges_pdf[['source_id', 'dest_id', 'weight']])
            collab_graph = cugraph.Graph()
            collab_graph.from_cudf_edgelist(edges_gdf, source='source_id', destination='dest_id', edge_attr='weight')
            partition, _ = cugraph.louvain(collab_graph)
            pagerank = cugraph.pagerank(collab_graph)

            node_meta_df = node_meta_df.merge(partition.to_pandas(), on='vertex', how='left')
            node_meta_df = node_meta_df.merge(pagerank.to_pandas(), on='vertex', how='left')
        else:
            edges_pdf_cpu = edges_pdf[['source_id', 'dest_id', 'weight']]
            nx_graph = nx.from_pandas_edgelist(edges_pdf_cpu, source='source_id', target='dest_id', edge_attr='weight')
            partition_dict = community_louvain.best_partition(nx_graph)
            pagerank_dict = nx.pagerank(nx_graph, weight='weight')

            part_df = pd.DataFrame([{'vertex': k, 'partition': v, 'pagerank': pagerank_dict[k]} for k, v in partition_dict.items()])
            node_meta_df = node_meta_df.merge(part_df, on='vertex', how='left')

        return edges_pdf, node_meta_df

    def calculate_community_impact(self) -> pd.DataFrame:
        """
        Calculates impact metrics (e.g. average citations, aggregate publications)
        for each Louvain community partition in the network.
        """
        if self.node_metadata is None or self.node_metadata.empty:
            return pd.DataFrame()

        # Group by partition and aggregate
        community_impact = self.node_metadata.groupby('partition').agg(
            num_authors=('author_name', 'count'),
            total_community_citations=('total_citations', 'sum'),
            avg_citations_per_author=('total_citations', 'mean'),
            total_community_publications=('num_publications', 'sum')
        ).reset_index()

        # Sort by total citations to highlight most influential communities
        community_impact = community_impact.sort_values(by='total_community_citations', ascending=False)
        return community_impact

    def get_layout(self, max_iter: int = 500) -> pd.DataFrame:
        if self.graph:
            if self.use_gpu:
                pos = cugraph.force_atlas2(self.graph, max_iter=max_iter)
                return pos.to_pandas()
            else:
                pos = nx.spring_layout(self.graph, iterations=max_iter, weight='weight')
                return pd.DataFrame([{'vertex': k, 'x': v[0], 'y': v[1]} for k, v in pos.items()])
        return None
