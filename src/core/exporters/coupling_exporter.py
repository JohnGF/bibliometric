import os
import sys
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def export_coupling_tables(output_dir: str = "pipeline_results_37k", title_map: dict = None, force: bool = False):
    """Generates tab_Biblio.tex and annex_Label_Bibliographic_Coupling.tex."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)

    t1 = os.path.join(tables_dir, "tab_Biblio.tex")
    t1_top = os.path.join(output_dir, "tab_Biblio.tex")

    if not force and os.path.exists(t1) and os.path.getsize(t1) > 100:
        return

    coupling_csv = os.path.join(output_dir, "data", "network_coupling.csv")
    if not os.path.exists(coupling_csv):
        coupling_csv = os.path.join(output_dir, "network_coupling.csv")

    if not os.path.exists(coupling_csv):
        return

    try:
        df = pd.read_csv(coupling_csv)
        top_10 = df.nlargest(10, "coupling_weight")
        tex = []
        tex.append("\\begin{table}[htbp]")
        tex.append("\\caption{Top 10 Bibliographically Coupled Document Pairs}")
        tex.append("\\label{tab:Biblio}")
        tex.append("\\scriptsize")
        tex.append("\\begin{tabular}{r p{0.40\\linewidth} p{0.40\\linewidth} r}")
        tex.append("\\toprule")
        tex.append("\\# & \\textbf{Source Document 1} & \\textbf{Source Document 2} & \\textbf{Shared} \\\\")
        tex.append("\\midrule")
        for i, (_, r) in enumerate(top_10.iterrows(), 1):
            s1_raw = str(r['source_1']).strip()
            s2_raw = str(r['source_2']).strip()
            u1 = f"https://doi.org/{s1_raw}" if s1_raw.startswith("10.") else f"https://openalex.org/{s1_raw}"
            u2 = f"https://doi.org/{s2_raw}" if s2_raw.startswith("10.") else f"https://openalex.org/{s2_raw}"
            t1_str = s1_raw[:20]
            t2_str = s2_raw[:20]
            if title_map and s1_raw in title_map:
                t1_str = title_map[s1_raw].get("title", t1_str)
                u1 = title_map[s1_raw].get("url", u1)
            if title_map and s2_raw in title_map:
                t2_str = title_map[s2_raw].get("title", t2_str)
                u2 = title_map[s2_raw].get("url", u2)
            c1 = t1_str.replace("&", "\\&").replace("_", "\\_").replace("#", "\\#").replace("%", "\\%")
            c2 = t2_str.replace("&", "\\&").replace("_", "\\_").replace("#", "\\#").replace("%", "\\%")
            s1_link = f"\\href{{{u1}}}{{{c1}}}"
            s2_link = f"\\href{{{u2}}}{{{c2}}}"
            cnt = int(r['coupling_weight'])
            tex.append(f"{i} & {s1_link} & {s2_link} & {cnt:,} \\\\")
        tex.append("\\bottomrule")
        tex.append("\\end{tabular}")
        tex.append("\\end{table}")

        with open(t1, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
        with open(t1_top, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
        logger.info(f"Generated {t1} successfully!")
    except Exception as e:
        logger.warning(f"Could not generate coupling tables: {e}")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results_37k"
    export_coupling_tables(out_dir, force=True)
