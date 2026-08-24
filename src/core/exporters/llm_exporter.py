import os
import sys
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def export_llm_table(output_dir: str = "pipeline_results", force: bool = False):
    """Generates annex_llm_screening.tex containing domain-aware AI/LLM Thematic Categorization."""
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
        logger.warning(f"Could not find publication dataset in {output_dir}; returning empty.")
        return

    try:
        df = pd.read_csv(pub_csv)
        tex = []
        tex.append("\\subsection{Automated Semantic & Thematic Taxonomy}")
        tex.append("\\begin{table}[htbp]")
        tex.append("\\caption{Automated Thematic & Methodological Categorization}")
        tex.append("\\label{tab:llm_screening}")
        tex.append("\\small")
        tex.append("\\begin{tabular}{p{0.50\\linewidth} r r}")
        tex.append("\\toprule")
        tex.append("\\textbf{Research Focus / Paradigm} & \\textbf{Papers} & \\textbf{Share (\\%)} \\\\")
        tex.append("\\midrule")

        # Check if LLM/classifier category column is present
        category_col = None
        for cand in ["llm_category", "meta_theme", "thematic_category", "dominant_topic"]:
            if cand in df.columns and df[cand].notna().sum() > 0:
                category_col = cand
                break

        if category_col:
            counts = df[category_col].value_counts().head(8)
            total = len(df)
            for p_name, cnt in counts.items():
                pct = (cnt / total) * 100.0
                safe_name = str(p_name).replace('&', '\\&').replace('_', ' ')
                tex.append(f"{safe_name} & {cnt:,} & {pct:.1f}\\% \\\\")
        else:
            # Dynamic text classification based on keyword frequencies in dataset
            titles = df["Title"].fillna("").astype(str).str.lower() if "Title" in df.columns else pd.Series([""] * len(df))
            abstracts = df["Abstract"].fillna("").astype(str).str.lower() if "Abstract" in df.columns else pd.Series([""] * len(df))
            text = titles + " " + abstracts

            # Detect domain
            all_text = " ".join(text)
            is_eeg = any(k in all_text for k in ["eeg", "electroencephalography", "bci", "brain-computer"])
            is_econ = any(k in all_text for k in ["rent", "housing", "landlord", "tenant", "price ceiling", "market"])

            paradigms = []
            if is_eeg:
                for t in text:
                    if any(w in t for w in ["ica", "wavelet", "artifact removal", "filtering", "suppression", "denois"]):
                        paradigms.append("Artifact Filtering \\& Removal")
                    elif any(w in t for w in ["stochastic", "resonance", "information", "entropy"]):
                        paradigms.append("Noise-as-Information")
                    elif any(w in t for w in ["deep learning", "cnn", "robust", "decoding", "latent"]):
                        paradigms.append("Robust Latent Decoding")
                    else:
                        paradigms.append("General Neural Signal Analysis")
            elif is_econ:
                for t in text:
                    if any(w in t for w in ["supply", "construction", "shortage", "elasticity"]):
                        paradigms.append("Housing Supply \\& Market Elasticity")
                    elif any(w in t for w in ["tenant", "displacement", "mobility", "welfare", "eviction"]):
                        paradigms.append("Tenant Welfare \\& Displacement")
                    elif any(w in t for w in ["landlord", "maintenance", "investment", "conversion", "condo"]):
                        paradigms.append("Landlord Response \\& Unit Conversions")
                    else:
                        paradigms.append("General Rental Policy \\& Law")
            else:
                for t in text:
                    if any(w in t for w in ["empirical", "dataset", "experiment", "evaluation", "trial"]):
                        paradigms.append("Empirical Evaluation")
                    elif any(w in t for w in ["model", "theoretical", "framework", "simulation"]):
                        paradigms.append("Theoretical Frameworks")
                    else:
                        paradigms.append("General Domain Studies")

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
    except Exception as e:
        logger.warning(f"Could not generate annex_llm_screening.tex: {e}")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results"
    export_llm_table(out_dir, force=True)
