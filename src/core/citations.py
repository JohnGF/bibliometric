import pandas as pd
import numpy as np
import scipy.sparse as sp
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class CitationsAnalysis:
    def __init__(self):
        pass

    def calculate_co_citation(self, references_df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[sp.csr_matrix]]:
        """
        Calculates co-citation counts for cited papers.
        Two papers are co-cited if they are referenced together by the same source paper.
        
        Args:
            references_df: A DataFrame with 'source', 'destination', 'authors', and 'year' columns.
            
        Returns:
            Tuple[pd.DataFrame, sp.csr_matrix]:
                - co_citation_results: DataFrame with columns: 
                  'cited_1', 'cited_2', 'co_citation_count', 'authors_1', 'authors_2', 'year_1', 'year_2'
                - X: Sparse citation matrix (sources x destinations)
        """
        logger.info("Starting co-citation matrix calculation...")
        required_columns = {'source', 'destination', 'authors', 'year'}
        
        if not required_columns.issubset(references_df.columns):
            logger.error(f"Missing required columns in references. Needed: {required_columns}")
            return pd.DataFrame(columns=['cited_1', 'cited_2', 'co_citation_count', 'authors_1', 'authors_2', 'year_1', 'year_2']), None
            
        # Drop duplicates and na rows to avoid dirty joins
        df = references_df[['source', 'destination', 'authors', 'year']].dropna(subset=['source', 'destination']).drop_duplicates(subset=['source', 'destination'])
        
        if df.empty:
            logger.warning("Empty references DataFrame provided.")
            return pd.DataFrame(columns=['cited_1', 'cited_2', 'co_citation_count', 'authors_1', 'authors_2', 'year_1', 'year_2']), None
            
        # Create metadata lookup map for authors and years
        destination_metadata = df.drop_duplicates(subset=['destination']).set_index('destination')
        author_map = destination_metadata['authors']
        year_map = destination_metadata['year']
        
        # Factorize papers to integer codes
        source_codes, source_uniques = pd.factorize(df['source'])
        dest_codes, dest_uniques = pd.factorize(df['destination'])
        
        # Build sparse citation matrix (Sources x Destinations)
        X = sp.coo_matrix(
            (np.ones(len(source_codes), dtype=np.int64), (source_codes, dest_codes)),
            shape=(len(source_uniques), len(dest_uniques))
        ).tocsr()
        
        # Calculate co-citation counts: X.T @ X (Destinations x Destinations)
        logger.info("Computing sparse matrix multiplication (X.T @ X)...")
        co_citation_matrix = X.T @ X
        co_citation_matrix = sp.triu(co_citation_matrix, k=1) # Upper triangle to drop self-loops and duplicates
        
        # Extract co-citation entries
        coo = co_citation_matrix.tocoo()
        if coo.nnz == 0:
            logger.warning("No co-citations found in dataset.")
            return pd.DataFrame(columns=['cited_1', 'cited_2', 'co_citation_count', 'authors_1', 'authors_2', 'year_1', 'year_2']), X
            
        cited_1 = dest_uniques[coo.row]
        cited_2 = dest_uniques[coo.col]
        
        results = pd.DataFrame({
            'cited_1': cited_1,
            'cited_2': cited_2,
            'co_citation_count': coo.data,
            'authors_1': author_map.reindex(cited_1).values,
            'authors_2': author_map.reindex(cited_2).values,
            'year_1': year_map.reindex(cited_1).values,
            'year_2': year_map.reindex(cited_2).values,
        })
        
        logger.info(f"Co-citation mapping completed. Found {len(results)} co-citation pairs.")
        return results, X

    def calculate_bibliographic_coupling(self, X: sp.csr_matrix, source_uniques: np.ndarray) -> pd.DataFrame:
        """
        Calculates bibliographic coupling between source papers.
        Two papers are coupled if they share one or more common references.
        
        Args:
            X: Sparse citation matrix (sources x destinations)
            source_uniques: The list of source paper labels (names/DOIs/EIDs) matching the rows of X.
            
        Returns:
            pd.DataFrame: DataFrame containing coupling pairs:
                'source_1', 'source_2', 'coupling_weight'
        """
        if X is None or X.shape[0] == 0:
            return pd.DataFrame(columns=['source_1', 'source_2', 'coupling_weight'])
            
        logger.info("Computing bibliographic coupling matrix (X @ X.T)...")
        # X @ X.T gives overlapping reference counts (Sources x Sources)
        coupling_matrix = X @ X.T
        coupling_matrix = sp.triu(coupling_matrix, k=1) # Drop self-coupling
        
        coo = coupling_matrix.tocoo()
        if coo.nnz == 0:
            logger.warning("No bibliographic coupling links found.")
            return pd.DataFrame(columns=['source_1', 'source_2', 'coupling_weight'])
            
        results = pd.DataFrame({
            'source_1': source_uniques[coo.row],
            'source_2': source_uniques[coo.col],
            'coupling_weight': coo.data
        })
        
        logger.info(f"Bibliographic coupling completed. Found {len(results)} coupling pairs.")
        return results

    def perform_percolation_analysis(self, edge_df: pd.DataFrame, source_col: str, target_col: str, weight_col: str) -> pd.DataFrame:
        """
        Performs a filtering-based percolation (network robustness) analysis
        by incrementally sweeping threshold cutoffs on edge weights.
        
        Args:
            edge_df: DataFrame containing the edge list.
            source_col: Name of column representing source nodes.
            target_col: Name of column representing target nodes.
            weight_col: Name of column representing edge weights (e.g. 'co_citation_count').
            
        Returns:
            pd.DataFrame: DataFrame containing percolation metrics for each cutoff.
        """
        import networkx as nx
        logger.info(f"Starting percolation sweep over edge weights ({weight_col})...")
        
        required_cols = {source_col, target_col, weight_col}
        if not required_cols.issubset(edge_df.columns):
            logger.error(f"Missing required columns in edge DataFrame: {required_cols - set(edge_df.columns)}")
            return pd.DataFrame()
            
        df_for_analysis = edge_df[[source_col, target_col, weight_col]].dropna()
        if df_for_analysis.empty:
            logger.warning("Empty edge DataFrame for percolation analysis.")
            return pd.DataFrame()
            
        # Define Cutoffs
        min_weight = df_for_analysis[weight_col].min()
        max_weight = df_for_analysis[weight_col].max()
        
        # Build granular sweep thresholds (phase transitions)
        cutoffs = []
        if min_weight <= 10:
            cutoffs.extend(range(int(min_weight), min(int(max_weight), 11), 1))
        if max_weight > 10:
            cutoffs.extend(range(12, min(int(max_weight), 21), 2))
        if max_weight > 20:
            cutoffs.extend(range(25, min(int(max_weight), 101), 5))
        if max_weight > 100:
            cutoffs.extend(range(150, min(int(max_weight), 201), 50))
        if max_weight > 200:
            cutoffs.extend(np.linspace(250, max_weight, 5, endpoint=True).astype(int).tolist())
            
        if min_weight not in cutoffs and min_weight > 0:
            cutoffs.insert(0, int(min_weight))
        if max_weight not in cutoffs:
            cutoffs.append(int(max_weight))
            
        cutoffs = sorted(list(set(cutoffs)))
        # Keep cutoffs below the maximum observed weight
        cutoffs = [c for c in cutoffs if c < max_weight]
        if not cutoffs:
            cutoffs = [int(min_weight)]
            
        all_initial_nodes = pd.concat([df_for_analysis[source_col], df_for_analysis[target_col]]).unique()
        total_initial_nodes = len(all_initial_nodes)
        
        results = {
            'cutoff': [],
            'num_edges': [],
            'num_nodes_in_filtered_graph': [],
            'num_components': [],
            'lcc_size': [],
            'lcc_nodes_percentage_of_filtered': [],
            'lcc_nodes_percentage_of_total_initial': []
        }
        
        for cutoff in cutoffs:
            current_df = df_for_analysis[df_for_analysis[weight_col] > cutoff]
            results['cutoff'].append(cutoff)
            
            if current_df.empty:
                results['num_edges'].append(0)
                results['num_nodes_in_filtered_graph'].append(0)
                results['num_components'].append(total_initial_nodes)
                results['lcc_size'].append(0)
                results['lcc_nodes_percentage_of_filtered'].append(0)
                results['lcc_nodes_percentage_of_total_initial'].append(0)
                continue
                
            G = nx.from_pandas_edgelist(current_df, source=source_col, target=target_col, create_using=nx.Graph())
            num_edges = G.number_of_edges()
            num_nodes = G.number_of_nodes()
            
            results['num_edges'].append(num_edges)
            results['num_nodes_in_filtered_graph'].append(num_nodes)
            
            connected_components = list(nx.connected_components(G))
            num_components = len(connected_components)
            lcc_size = max(len(c) for c in connected_components) if num_components > 0 else 0
            
            # Isolated node component adjustment
            isolated_nodes = total_initial_nodes - num_nodes
            results['num_components'].append(num_components + isolated_nodes)
            results['lcc_size'].append(lcc_size)
            results['lcc_nodes_percentage_of_filtered'].append((lcc_size / num_nodes) * 100 if num_nodes > 0 else 0)
            results['lcc_nodes_percentage_of_total_initial'].append((lcc_size / total_initial_nodes) * 100 if total_initial_nodes > 0 else 0)
            
        logger.info(f"Percolation sweep completed over {len(cutoffs)} cutoffs.")
        return pd.DataFrame(results)
