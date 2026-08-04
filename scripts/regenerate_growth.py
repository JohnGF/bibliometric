import os
import sys

# Ensure repo root is in python path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import polars as pl
from src.core.viz import Visualization


def regenerate_growth(output_dir: str = "pipeline_results_37k") -> int:
    """Regenerates the yearly growth figure + CSV using the configured study period.

    The study window (start/end year) is read from data/query.txt via
    Visualization.plot_yearly_growth, so the figure always matches the query.
    """
    os.makedirs(output_dir, exist_ok=True)

    dataset_candidates = [
        os.path.join(output_dir, "data", "publication_dataset.csv"),
        os.path.join(output_dir, "publication_dataset.csv"),
        os.path.join("data", "collected_EEG_master_merged.csv"),
        os.path.join("..", "data", "collected_EEG_master_merged.csv"),
    ]
    dataset = next((c for c in dataset_candidates if os.path.exists(c)), None)
    if not dataset:
        print("[!] No dataset found for yearly growth regeneration.")
        return 1

    print(f"[+] Reading {dataset} ...")
    df = pl.read_csv(dataset)
    df = df.filter(pl.col("Year").is_not_null())
    df = df.with_columns(pl.col("Year").cast(pl.Int64))

    viz = Visualization()
    growth = viz.plot_yearly_growth(df, save_path=os.path.join(output_dir, "yearly_growth.pdf"))
    if growth is None or growth.empty:
        print("[!] Yearly growth regeneration produced no data.")
        return 1

    min_yr = int(growth["Year"].min())
    max_yr = int(growth["Year"].max())

    for rel_path in ("yearly_growth.csv", os.path.join("data", "yearly_growth.csv")):
        os.makedirs(os.path.join(output_dir, os.path.dirname(rel_path)), exist_ok=True)
        growth.to_csv(os.path.join(output_dir, rel_path), index=False)

    fig_dir = os.path.join(output_dir, "figures")
    os.makedirs(fig_dir, exist_ok=True)
    import shutil
    shutil.copyfile(os.path.join(output_dir, "yearly_growth.pdf"), os.path.join(fig_dir, "yearly_growth.pdf"))

    print(f"[✓] Regenerated yearly growth ({min_yr}-{max_yr}) -> {output_dir}/yearly_growth.pdf")
    return 0


if __name__ == "__main__":
    sys.exit(regenerate_growth(sys.argv[1] if len(sys.argv) > 1 else "pipeline_results_37k"))
