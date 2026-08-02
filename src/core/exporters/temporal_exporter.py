import os
import sys
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def export_temporal_table(output_dir: str = "pipeline_results_37k", force: bool = False):
    """Generates annex_temporal_deltas.tex containing Scientific Market Share Deltas (Delta %)."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    fpath = os.path.join(tables_dir, "annex_temporal_deltas.tex")
    top_fpath = os.path.join(output_dir, "annex_temporal_deltas.tex")

    if not force and os.path.exists(fpath) and os.path.getsize(fpath) > 100:
        return

    pub_csv = os.path.join(output_dir, "data", "publication_dataset.csv")
    if not os.path.exists(pub_csv):
        pub_csv = os.path.join(output_dir, "publication_dataset.csv")
    if not os.path.exists(pub_csv):
        pub_csv = os.path.join("data", "collected_EEG_master_merged.csv")

    if os.path.exists(pub_csv):
        try:
            df = pd.read_csv(pub_csv)
            from src.core.temporal_delta import TemporalDeltaAnalysis
            tda = TemporalDeltaAnalysis()
            if "Author Keywords" in df.columns and "Year" in df.columns:
                records = []
                for _, r in df.dropna(subset=["Author Keywords", "Year"]).iterrows():
                    yr = int(r["Year"])
                    kws = str(r["Author Keywords"]).split(";")
                    for k in kws:
                        k_clean = k.strip().lower()
                        if k_clean and "eeg" not in k_clean:
                            records.append({"Keyword": k_clean, "Year": yr})
                kdf = pd.DataFrame(records)
                delta_df = tda.compute_temporal_deltas(kdf, category_col="Keyword", year_col="Year")
                if not delta_df.empty:
                    tex = []
                    tex.append("\\subsection{Scientific Temporal Dynamics \\& Market Share Deltas ($\\Delta$)}")
                    tex.append("\\begin{table}[htbp]")
                    tex.append("\\caption{Temporal Paradigm Shifts: Baseline vs Modern Epoch Market Share Deltas}")
                    tex.append("\\label{tab:temporal_deltas}")
                    tex.append("\\small")
                    tex.append("\\begin{tabular}{p{0.35\\linewidth} r r r r l}")
                    tex.append("\\toprule")
                    tex.append("\\textbf{Research Focus} & \\textbf{$T_1$ (\\%)} & \\textbf{$T_2$ (\\%)} & \\textbf{$\\Delta$ (\\%)} & \\textbf{Fold} & \\textbf{Trajectory} \\\\")
                    tex.append("\\midrule")
                    for _, r in delta_df.head(15).iterrows():
                        cat = str(r["Category"]).replace("_", "\\_").replace("&", "\\&")
                        st1 = float(r["Baseline_Share_Pct"])
                        st2 = float(r["Modern_Share_Pct"])
                        delta = float(r["Delta_Share_Pct"])
                        fold = float(r["Fold_Change"])
                        traj = str(r["Trajectory"])
                        tex.append(f"{cat[:25]} & {st1:.1f}\\% & {st2:.1f}\\% & {delta:+.2f}\\% & {fold:.1f}x & {traj} \\\\")
                    tex.append("\\bottomrule")
                    tex.append("\\end{tabular}")
                    tex.append("\\end{table}")
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write("\n".join(tex))
                    with open(top_fpath, "w", encoding="utf-8") as f:
                        f.write("\n".join(tex))
                    logger.info(f"Generated {fpath} successfully!")
                    return
        except Exception as e:
            logger.warning(f"Could not generate annex_temporal_deltas.tex: {e}")

    with open(fpath, "w", encoding="utf-8") as f:
        f.write("% Temporal Deltas Annex\n\\subsection{Temporal Delta Shifts}\n\\label{tab:temporal_deltas}\n")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results_37k"
    export_temporal_table(out_dir, force=True)
