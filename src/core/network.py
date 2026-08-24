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
    # Enable CUDA Managed Memory so GPU memory allocations spill over into System RAM safely
    rmm.reinitialize(managed_memory=True)
    import cupy
    cupy.cuda.Device(0).use()
    HAS_GPU = True
except Exception as e:
    logging.warning(f"GPU RAPIDS initialization skipped ({e}). Using CPU network engine.")
    HAS_GPU = False

# CPU Fallback Engines (python-igraph C-engine preferred, networkx fallback)
HAS_IGRAPH = False
try:
    import igraph as ig
    HAS_IGRAPH = True
except ImportError:
    pass

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

        gpu_success = False
        if self.use_gpu:
            try:
                import cupy
                free_mem, total_mem = cupy.cuda.Device(0).mem_info
                logging.info(f"[GPU DIAGNOSTIC] VRAM Available: {free_mem / 1e9:.2f} GB free / {total_mem / 1e9:.2f} GB total")
                logging.info(f"[GPU DIAGNOSTIC] Graph Size: {len(unique_authors):,} author nodes, {len(edges_pdf):,} co-authorship edges")
                est_bytes = (len(unique_authors) + len(edges_pdf)) * 64
                logging.info(f"[GPU DIAGNOSTIC] Estimated Memory required for cuGraph buffers: ~{est_bytes / 1e6:.2f} MB")
            except Exception as e:
                logging.warning(f"Could not query GPU memory info: {e}")

            try:
                logging.info("NetworkAnalysis: Running GPU-accelerated co-authorship analysis (cuGraph/cuDF)...")
                edges_gdf = cudf.from_pandas(edges_pdf[['source_id', 'dest_id', 'weight']])
                self.graph = cugraph.Graph()
                self.graph.from_cudf_edgelist(edges_gdf, source='source_id', destination='dest_id', edge_attr='weight')
                partition, _ = cugraph.louvain(self.graph)
                pagerank = cugraph.pagerank(self.graph)
                degree = cugraph.degree_centrality(self.graph)

                partition = partition.merge(pagerank, on='vertex')
                partition = partition.merge(degree, on='vertex')
                
                if len(unique_authors) <= 3000:
                    try:
                        betweenness = cugraph.betweenness_centrality(self.graph, k=min(100, len(unique_authors)))
                        partition = partition.merge(betweenness, on='vertex', how='left')
                    except Exception as e:
                        logging.warning(f"GPU betweenness centrality skipped ({e}). Louvain, PageRank, and Degree running on GPU.")
                        partition['betweenness_centrality'] = 0.0
                else:
                    logging.info("Running Component-Decomposition Sampling for GPU betweenness centrality (>3000 nodes)...")
                    try:
                        comps = cugraph.connected_components(self.graph)
                        comp_counts = comps['labels'].value_counts()
                        major_labels = comp_counts[comp_counts > 2].index.to_pandas().tolist()
                        
                        if major_labels:
                            major_vertices = comps[comps['labels'].isin(major_labels)]['vertex']
                            sub_gdf = edges_gdf[edges_gdf['source_id'].isin(major_vertices) & edges_gdf['dest_id'].isin(major_vertices)]
                            if not sub_gdf.empty:
                                sub_g = cugraph.Graph()
                                sub_g.from_cudf_edgelist(sub_gdf, source='source_id', destination='dest_id', edge_attr='weight')
                                betweenness = cugraph.betweenness_centrality(sub_g, k=min(100, len(major_vertices)))
                                partition = partition.merge(betweenness, on='vertex', how='left')
                                partition['betweenness_centrality'] = partition['betweenness_centrality'].fillna(0.0)
                            else:
                                partition['betweenness_centrality'] = 0.0
                        else:
                            partition['betweenness_centrality'] = 0.0
                    except Exception as e:
                        logging.warning(f"Component betweenness sampling fallback triggered ({e}).")
                        partition['betweenness_centrality'] = 0.0
                gpu_success = True
            except Exception as gpu_err:
                logging.warning(f"GPU cuGraph calculation encountered error: {gpu_err}. Falling back to CPU graph engine.")
                gpu_success = False

        if not gpu_success:
            logging.info("NetworkAnalysis: Running CPU-mode co-authorship analysis (NetworkX)...")
            edges_pdf_cpu = edges_pdf[['source_id', 'dest_id', 'weight']]
            nx_graph = nx.from_pandas_edgelist(edges_pdf_cpu, source='source_id', target='dest_id', edge_attr='weight')
            self.graph = nx_graph
            partition_dict = community_louvain.best_partition(nx_graph)
            pagerank_dict = nx.pagerank(nx_graph, weight='weight')
            
            # For CPU performance, sample k nodes if graph is large
            num_nodes = len(nx_graph)
            if num_nodes > 500:
                betweenness_dict = nx.betweenness_centrality(nx_graph, k=min(num_nodes, 500), weight='weight', seed=42)
            else:
                betweenness_dict = nx.betweenness_centrality(nx_graph, weight='weight')

            degree_dict = nx.degree_centrality(nx_graph)

            # Skip spring_layout for large graphs (>1000 nodes) to avoid O(N^2) CPU freeze (layout is computed in viz.py)
            if num_nodes <= 1000:
                pos_dict = nx.spring_layout(nx_graph, k=0.35, iterations=50, seed=42)
            else:
                pos_dict = {k: (0.0, 0.0) for k in nx_graph.nodes()}

            partition = pd.DataFrame([
                {
                    'vertex': k,
                    'partition': v,
                    'pagerank': pagerank_dict.get(k, 0.0),
                    'betweenness_centrality': betweenness_dict.get(k, 0.0),
                    'degree_centrality': degree_dict.get(k, 0.0),
                    'x': pos_dict.get(k, (0.0, 0.0))[0],
                    'y': pos_dict.get(k, (0.0, 0.0))[1]
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
