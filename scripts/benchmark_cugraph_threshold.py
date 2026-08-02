import time
import logging
import pandas as pd
import numpy as np
import multiprocessing as mp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cugraph_bughunter")

def generate_sparse_coauthorship(num_nodes: int, max_vertex_id: int = 100000):
    """Generates synthetic co-authorship edgelists with sparse non-contiguous vertex IDs."""
    np.random.seed(42)
    # Generate non-contiguous sparse author IDs
    sparse_author_ids = np.random.choice(np.arange(1, max_vertex_id), size=num_nodes, replace=False)
    
    num_edges = num_nodes * 3
    src_idx = np.random.choice(sparse_author_ids, size=num_edges)
    dst_idx = np.random.choice(sparse_author_ids, size=num_edges)
    
    mask = src_idx != dst_idx
    src_idx, dst_idx = src_idx[mask], dst_idx[mask]
    weights = np.random.randint(1, 5, size=len(src_idx))
    
    return pd.DataFrame({'source_id': src_idx, 'dest_id': dst_idx, 'weight': weights})

def _gpu_worker_process(edges_pdf, renumber_flag, return_dict):
    try:
        import cudf
        import cugraph
        import rmm
        rmm.reinitialize(managed_memory=True)
        
        t0 = time.time()
        edges_gdf = cudf.from_pandas(edges_pdf)
        g = cugraph.Graph()
        
        # Test low-level C++ renumbering allocation
        g.from_cudf_edgelist(
            edges_gdf, 
            source='source_id', 
            destination='dest_id', 
            edge_attr='weight',
            renumber=renumber_flag
        )
        
        part, _ = cugraph.louvain(g)
        pr = cugraph.pagerank(g)
        deg = cugraph.degree_centrality(g)
        
        gpu_time = time.time() - t0
        return_dict['success'] = True
        return_dict['time'] = gpu_time
        return_dict['msg'] = f"SUCCESS ({len(part):,} vertices processed)"
    except Exception as e:
        return_dict['success'] = False
        return_dict['time'] = 0.0
        return_dict['msg'] = f"PYTHON EXCEPTION: {e}"

def test_gpu_low_level(edges_pdf, renumber_flag):
    manager = mp.Manager()
    return_dict = manager.dict()
    
    p = mp.Process(target=_gpu_worker_process, args=(edges_pdf, renumber_flag, return_dict))
    p.start()
    p.join(timeout=60)
    
    if p.is_alive():
        p.terminate()
        p.join()
        return False, 0.0, "TIMEOUT (>60s)"
    
    if p.exitcode == -11 or p.exitcode == 139:
        return False, 0.0, "CUDA C++ SEGFAULT (Signal 11: Out-of-bounds CUDA Device Memory Access)"
    elif p.exitcode != 0 and not return_dict.get('success', False):
        return False, 0.0, f"CUDA KERNEL CRASH (Exit Code {p.exitcode})"
        
    return return_dict.get('success', False), return_dict.get('time', 0.0), return_dict.get('msg', 'Unknown Error')

def main():
    logger.info("==========================================================================")
    logger.info("=== RAPIDS cuGraph CUDA C++ LOW-LEVEL BUG HUNTING DIAGNOSTIC TOOL ===")
    logger.info("==========================================================================")
    
    test_node_counts = [1000, 5000, 15000, 35000, 75000]
    max_id_range = 100000
    
    results = []
    for N in test_node_counts:
        print("\n" + "-"*75)
        logger.info(f"BUG HUNT TEST CASE: {N:,} nodes spanning sparse ID range [1 .. {max_id_range:,}]")
        edges_pdf = generate_sparse_coauthorship(num_nodes=N, max_vertex_id=max_id_range)
        logger.info(f"Generated sparse edgelist: {len(edges_pdf):,} edges")
        
        # Test 1: WITHOUT Renumbering (triggers C++ out-of-bounds pointer read)
        logger.info(">>> Running Test 1: renumber=False (Raw Sparse Vertex IDs)...")
        ok_no_renum, t_no_renum, msg_no_renum = test_gpu_low_level(edges_pdf, renumber_flag=False)
        logger.info(f"    Result [renumber=False]: {msg_no_renum}")
        
        # Test 2: WITH Renumbering (Fixes CUDA memory indexing)
        logger.info(">>> Running Test 2: renumber=True (Contiguous Vertex Mapping)...")
        ok_renum, t_renum, msg_renum = test_gpu_low_level(edges_pdf, renumber_flag=True)
        logger.info(f"    Result [renumber=True]:  {msg_renum} (Time: {t_renum:.3f}s)")
        
        results.append({
            'nodes': N,
            'edges': len(edges_pdf),
            'renumber_false': msg_no_renum,
            'renumber_true': msg_renum,
            'time_with_fix_sec': round(t_renum, 3) if ok_renum else None
        })
        
    res_df = pd.DataFrame(results)
    print("\n" + "="*75)
    print("=== BUG HUNTING EXPERIMENT RESULTS ===")
    print("="*75)
    print(res_df.to_string(index=False))
    res_df.to_csv("data/cugraph_bughunter_results.csv", index=False)

if __name__ == "__main__":
    main()
