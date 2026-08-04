import os
import sys
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def export_bertopic_table(output_dir: str = "pipeline_results", force: bool = False):
    """Generates annex_bertopic_details.tex containing BERTopic Meta-Theme Taxonomy."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    fpath = os.path.join(tables_dir, "annex_bertopic_details.tex")
    top_fpath = os.path.join(output_dir, "annex_bertopic_details.tex")

    if not force and os.path.exists(fpath) and os.path.getsize(fpath) > 100:
        return

    topic_csv = os.path.join(output_dir, "data", "topic_info.csv")
    if not os.path.exists(topic_csv):
        topic_csv = os.path.join(output_dir, "topic_info.csv")

    if os.path.exists(topic_csv):
        try:
            df = pd.read_csv(topic_csv)
            valid = df[df["Topic"] != -1].head(15) if "Topic" in df.columns else df.head(15)
            tex = []
            tex.append("\\subsection{AI-Driven Content Analysis \\& BERTopic Taxonomy}")
            tex.append("\\begin{table}[htbp]")
            tex.append("\\caption{BERTopic Clusters Consolidated into Meta-Theme Taxonomy}")
            tex.append("\\label{tab:bertopic_clusters}")
            tex.append("\\scriptsize")
            tex.append("\\setlength{\\tabcolsep}{4pt}")
            tex.append("\\begin{tabular}{r p{0.32\\linewidth} p{0.30\\linewidth} r}")
            tex.append("\\toprule")
            tex.append("\\textbf{\\#} & \\textbf{Consolidated Meta-Theme} & \\textbf{BERTopic Keywords} & \\textbf{Papers} \\\\")
            tex.append("\\midrule")
            for _, r in valid.iterrows():
                tid = int(r.get("Topic", 0))
                raw_name = str(r.get("Name", r.get("Representation", ""))).lower()

                # Infer Meta-Theme from keywords
                if any(w in raw_name for w in ["artifact", "ica", "wavelet", "noise", "tms", "emg", "filter", "electrode"]):
                    theme = "Advanced Artifact Suppression"
                elif any(w in raw_name for w in ["bci", "motor", "mi", "ssvep", "cca", "intent", "imagery"]):
                    theme = "Brain-Computer Interface Systems"
                else:
                    theme = "Clinical \\& Biological Applications"

                clean_kw = raw_name.replace(f"{tid}_", "").replace("_", ", ").replace("&", "\\&")[:45]
                cnt = int(r.get("Count", 0))
                tex.append(f"T{tid} & {theme} & {clean_kw} & {cnt:,} \\\\")
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
            logger.warning(f"Could not generate annex_bertopic_details.tex: {e}")

    with open(fpath, "w", encoding="utf-8") as f:
        f.write("% BERTopic Details Annex\n\\subsection{BERTopic Details}\n\\label{tab:bertopic_clusters}\n")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results"
    export_bertopic_table(out_dir, force=True)
