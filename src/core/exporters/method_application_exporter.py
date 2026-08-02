import os
import sys
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def export_method_application_table(output_dir: str = "pipeline_results_37k", force: bool = False):
    """Generates annex_method_application_matrix.tex containing Methodology vs Application Field Cross-Tabulation."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    fpath = os.path.join(tables_dir, "annex_method_application_matrix.tex")
    top_fpath = os.path.join(output_dir, "annex_method_application_matrix.tex")

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
            tex.append("\\subsection{Methodology $\\times$ Application Field Bipartite Mapping}")
            tex.append("\\begin{table}[htbp]")
            tex.append("\\caption{Methodology vs Application Field Cross-Tabulation}")
            tex.append("\\label{tab:method_application}")
            tex.append("\\scriptsize")
            tex.append("\\begin{tabular}{p{0.35\\linewidth} p{0.35\\linewidth} r r}")
            tex.append("\\toprule")
            tex.append("\\textbf{Methodology / Technique} & \\textbf{Application Field} & \\textbf{Papers} & \\textbf{Share (\\%)} \\\\")
            tex.append("\\midrule")

            titles = df["Title"].fillna("").astype(str).str.lower() if "Title" in df.columns else pd.Series([""]*len(df))
            abstracts = df["Abstract"].fillna("").astype(str).str.lower() if "Abstract" in df.columns else pd.Series([""]*len(df))
            text = titles + " " + abstracts

            methods = []
            apps = []
            for t in text:
                if any(w in t for w in ["ica", "wavelet", "artifact removal", "filtering", "suppression", "denois"]):
                    m = "ICA / Wavelet Denoising"
                elif any(w in t for w in ["deep learning", "cnn", "convolutional", "transformer", "neural network"]):
                    m = "Deep Learning (CNN/DL)"
                elif any(w in t for w in ["csp", "fbcsp", "ssvep", "spatial pattern", "evoked"]):
                    m = "Spatial Patterns (CSP/SSVEP)"
                elif any(w in t for w in ["stochastic", "resonance", "entropy", "variability"]):
                    m = "Stochastic Noise Dynamics"
                else:
                    m = "General Signal Processing"

                if any(w in t for w in ["motor imagery", "bci", "rehabilitation", "prosthetic", "neuroprosthet"]):
                    a = "Motor Imagery BCI"
                elif any(w in t for w in ["epilepsy", "seizure", "hfo", "spike", "ictal"]):
                    a = "Epilepsy \\& Seizures"
                elif any(w in t for w in ["emotion", "affective", "deap", "valence", "arousal"]):
                    a = "Emotion Recognition"
                elif any(w in t for w in ["sleep", "somnology", "staging", "drowsiness"]):
                    a = "Sleep Staging"
                elif any(w in t for w in ["workload", "fatigue", "driving", "cognitive", "mental"]):
                    a = "Cognitive Workload"
                else:
                    a = "General Clinical \\& Bio"

                methods.append(m)
                apps.append(a)

            ct = pd.crosstab(pd.Series(methods, name="Methodology"), pd.Series(apps, name="Application Field"))
            unstacked = ct.unstack().reset_index(name="Count").sort_values("Count", ascending=False)
            total = unstacked["Count"].sum() if unstacked["Count"].sum() > 0 else 1

            for _, r in unstacked.head(15).iterrows():
                m_name = str(r["Methodology"]).replace("_", "\\_").replace("&", "\\&")
                a_name = str(r["Application Field"]).replace("_", "\\_").replace("&", "\\&")
                cnt = int(r["Count"])
                pct = (cnt / total) * 100.0
                tex.append(f"{m_name} & {a_name} & {cnt:,} & {pct:.1f}\\% \\\\")
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
            logger.warning(f"Could not generate annex_method_application_matrix.tex: {e}")

    with open(fpath, "w", encoding="utf-8") as f:
        f.write("% Method-Application Annex\n\\subsection{Methodology vs Application}\n\\label{tab:method_application}\n")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results_37k"
    export_method_application_table(out_dir, force=True)
