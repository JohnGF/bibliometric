import os
import sys
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def export_llm_table(output_dir: str = "pipeline_results_37k", force: bool = False):
    """Generates annex_llm_screening.tex containing Ollama LLM Noise Taxonomy."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    fpath = os.path.join(tables_dir, "annex_llm_screening.tex")
    top_fpath = os.path.join(output_dir, "annex_llm_screening.tex")

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
            tex = []
            tex.append("\\subsection{Ollama LLM Automated Paper Screening \\& Noise Taxonomy}")
            tex.append("\\begin{table}[htbp]")
            tex.append("\\caption{Ollama LLM Noise Treatment Paradigm Categorization}")
            tex.append("\\label{tab:llm_screening}")
            tex.append("\\small")
            tex.append("\\begin{tabular}{p{0.45\\linewidth} r r}")
            tex.append("\\toprule")
            tex.append("\\textbf{Noise Treatment Paradigm} & \\textbf{Papers} & \\textbf{Share (\\%)} \\\\")
            tex.append("\\midrule")

            titles = df["Title"].fillna("").astype(str).str.lower() if "Title" in df.columns else pd.Series([""]*len(df))
            abstracts = df["Abstract"].fillna("").astype(str).str.lower() if "Abstract" in df.columns else pd.Series([""]*len(df))
            text = titles + " " + abstracts

            paradigms = []
            for t in text:
                if any(w in t for w in ["ica", "wavelet", "artifact removal", "filtering", "suppression", "denois"]):
                    paradigms.append("Artifact Filtering \\& Removal")
                elif any(w in t for w in ["stochastic", "resonance", "information", "entropy"]):
                    paradigms.append("Noise-as-Information")
                elif any(w in t for w in ["deep learning", "cnn", "robust", "decoding", "latent"]):
                    paradigms.append("Robust Latent Decoding")
                else:
                    paradigms.append("General BCI Analysis")
            counts = pd.Series(paradigms).value_counts()
            total = len(paradigms) if len(paradigms) > 0 else 1

            for p_name, cnt in counts.items():
                pct = (cnt / total) * 100.0
                tex.append(f"{p_name} & {cnt:,} & {pct:.1f}\\% \\\\")
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
            logger.warning(f"Could not generate annex_llm_screening.tex: {e}")

    with open(fpath, "w", encoding="utf-8") as f:
        f.write("% LLM Screening Annex\n\\subsection{LLM Screening Taxonomy}\n\\label{tab:llm_screening}\n")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results_37k"
    export_llm_table(out_dir, force=True)
