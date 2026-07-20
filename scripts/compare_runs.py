import os
import sys
import pandas as pd
from typing import List, Dict

def analyze_and_compare_dirs(dirs: List[str]):
    print("==================================================")
    print("   Bibliometric Query Runs Comparative Report    ")
    print("==================================================\n")

    summary_rows = []
    datasets = {}

    for d in dirs:
        if not os.path.exists(d):
            print(f"[WARNING] Directory '{d}' does not exist yet. Skipping.")
            continue

        topic_file = os.path.join(d, "topic_info.csv")
        nodes_file = os.path.join(d, "network_nodes.csv")
        cagr_file = os.path.join(d, "keywords_cagr.csv")
        country_file = os.path.join(d, "country_evolution.csv")

        topics_count = len(pd.read_csv(topic_file)) if os.path.exists(topic_file) else 0
        authors_count = len(pd.read_csv(nodes_file)) if os.path.exists(nodes_file) else 0
        keywords_count = len(pd.read_csv(cagr_file)) if os.path.exists(cagr_file) else 0
        countries_count = len(pd.read_csv(country_file)['country'].unique()) if os.path.exists(country_file) and 'country' in pd.read_csv(country_file).columns else 0

        summary_rows.append({
            "Output Directory": d,
            "Topics Extracted": topics_count,
            "Author Nodes": authors_count,
            "Keywords Tracked": keywords_count,
            "Countries Covered": countries_count,
        })

    summary_df = pd.DataFrame(summary_rows)
    print(summary_df.to_string(index=False))
    print("\n==================================================")

if __name__ == "__main__":
    target_dirs = sys.argv[1:] if len(sys.argv) > 1 else [
        "pipeline_results_narrow_query",
        "pipeline_results_broad_33k",
        "pipeline_results_original_33k"
    ]
    analyze_and_compare_dirs(target_dirs)
