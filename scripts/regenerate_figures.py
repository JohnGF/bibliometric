import os
import sys
import shutil
from typing import Optional

# Ensure repo root is in python path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import polars as pl
import pandas as pd
from src.core.viz import Visualization
from src.core.temporal_delta import TemporalDeltaAnalysis


def _dataset_for(output_dir: str) -> Optional[str]:
    """Locate the dataset used for an output directory."""
    candidates = [
        os.path.join(output_dir, "data", "publication_dataset.csv"),
        os.path.join(output_dir, "publication_dataset.csv"),
        os.path.join("data", "collected_EEG_master_merged.csv"),
        os.path.join("..", "data", "collected_EEG_master_merged.csv"),
    ]
    return next((c for c in candidates if os.path.exists(c)), None)


def regenerate_figures(output_dir: str = "pipeline_results_37k") -> int:
    """Regenerates analysis figures from the dataset into the output directory.

    Covers the yearly growth chart, temporal delta shifts, LLM noise paradigm
    donut, and methodology x application field matrix. Figure titles are
    deliberately query-neutral so the scaffold is reusable for any dataset.
    """
    os.makedirs(output_dir, exist_ok=True)
    fig_dir = os.path.join(output_dir, "figures")
    os.makedirs(fig_dir, exist_ok=True)
    data_dir = os.path.join(output_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    dataset = _dataset_for(output_dir)
    if not dataset:
        print("[!] No dataset found for figure regeneration.")
        return 1

    print(f"[+] Reading {dataset} ...")
    df_pd = pd.read_csv(dataset)
    viz = Visualization()

    def save(name: str, pdf_name: str):
        pdf_src = os.path.join(output_dir, pdf_name)
        if os.path.exists(pdf_src):
            shutil.copyfile(pdf_src, os.path.join(fig_dir, pdf_name))

    # 1. Yearly growth (also writes the growth CSV).
    df = pl.from_pandas(df_pd)
    df = df.filter(pl.col("Year").is_not_null())
    df = df.with_columns(pl.col("Year").cast(pl.Int64))
    growth = viz.plot_yearly_growth(df, save_path=os.path.join(output_dir, "yearly_growth.pdf"))
    if growth is not None and not growth.empty:
        min_yr = int(growth["Year"].min())
        max_yr = int(growth["Year"].max())
        growth.to_csv(os.path.join(output_dir, "yearly_growth.csv"), index=False)
        growth.to_csv(os.path.join(data_dir, "yearly_growth.csv"), index=False)
        print(f"[✓] Regenerated yearly growth ({min_yr}-{max_yr}) -> {output_dir}/yearly_growth.pdf")
    save("yearly_growth.pdf", "yearly_growth.pdf")

    # 2. Temporal delta shifts (requires Author Keywords).
    if "Author Keywords" in df_pd.columns and "Year" in df_pd.columns:
        try:
            records = []
            for _, r in df_pd.dropna(subset=["Author Keywords", "Year"]).iterrows():
                yr = int(r["Year"])
                for k in str(r["Author Keywords"]).split(";"):
                    k_clean = k.strip().lower()
                    if k_clean:
                        records.append({"Keyword": k_clean, "Year": yr})
            kdf = pd.DataFrame(records)
            delta_df = TemporalDeltaAnalysis().compute_temporal_deltas(
                kdf, category_col="Keyword", year_col="Year"
            )
            if delta_df is not None and not delta_df.empty:
                viz.plot_temporal_delta_shifts(
                    delta_df,
                    title_suffix="Research Focus Areas",
                    save_path=os.path.join(output_dir, "temporal_delta_shifts.pdf"),
                )
                print(f"[✓] Regenerated temporal delta shifts -> {output_dir}/temporal_delta_shifts.pdf")
                save("temporal_delta_shifts.pdf", "temporal_delta_shifts.pdf")
        except Exception as e:
            print(f"[!] Could not regenerate temporal delta shifts: {e}")

    # 3. LLM noise treatment paradigm taxonomy.
    try:
        viz.plot_llm_noise_paradigm(df_pd, save_path=os.path.join(output_dir, "llm_noise_paradigm.pdf"))
        print(f"[✓] Regenerated LLM noise paradigm chart -> {output_dir}/llm_noise_paradigm.pdf")
        save("llm_noise_paradigm.pdf", "llm_noise_paradigm.pdf")
    except Exception as e:
        print(f"[!] Could not regenerate LLM noise paradigm chart: {e}")

    # 4. Methodology x application field matrix.
    try:
        viz.plot_method_application_matrix(df_pd, save_path=os.path.join(output_dir, "method_application_matrix.pdf"))
        print(f"[✓] Regenerated methodology x application matrix -> {output_dir}/method_application_matrix.pdf")
        save("method_application_matrix.pdf", "method_application_matrix.pdf")
    except Exception as e:
        print(f"[!] Could not regenerate methodology x application matrix: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(regenerate_figures(sys.argv[1] if len(sys.argv) > 1 else "pipeline_results_37k"))
