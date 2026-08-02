import os
import sys
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def export_cocitation_tables(output_dir: str = "pipeline_results_37k", title_map: dict = None, force: bool = False):
    """Generates tab_top_references_pagerank.tex and annex_Label_Co_Citation.tex."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    
    t1 = os.path.join(tables_dir, "tab_top_references_pagerank.tex")
    t1_top = os.path.join(output_dir, "tab_top_references_pagerank.tex")
    
    t2 = os.path.join(tables_dir, "annex_Label_Co_Citation.tex")
    t2_top = os.path.join(output_dir, "annex_Label_Co_Citation.tex")

    if not force and os.path.exists(t1) and os.path.exists(t2) and os.path.getsize(t1) > 100:
        return

    cocit_csv = os.path.join(output_dir, "data", "network_cocitations.csv")
    if not os.path.exists(cocit_csv):
        cocit_csv = os.path.join(output_dir, "network_cocitations.csv")

    if not os.path.exists(cocit_csv):
        return

    try:
        df = pd.read_csv(cocit_csv)
        ref_counts = {}
        for _, r in df.iterrows():
            c1 = str(r['cited_1']).strip()
            c2 = str(r['cited_2']).strip()
            cnt = int(r['co_citation_count'])
            ref_counts[c1] = ref_counts.get(c1, 0) + cnt
            ref_counts[c2] = ref_counts.get(c2, 0) + cnt

        top_20_refs = sorted(ref_counts.items(), key=lambda x: x[1], reverse=True)[:20]

        tex = []
        tex.append("\\begin{table}[htbp]")
        tex.append("\\caption{Top 20 Most Referenced Landmark Publications}")
        tex.append("\\label{tab:top_references_pagerank}")
        tex.append("\\footnotesize")
        tex.append("\\begin{tabular}{p{0.75\\linewidth} r}")
        tex.append("\\toprule")
        tex.append("\\textbf{Landmark Reference Publication} & \\textbf{Citations} \\\\")
        tex.append("\\midrule")
        for ref_id, cnt in top_20_refs:
            url = f"https://openalex.org/{ref_id}" if ref_id.startswith("W") else f"https://doi.org/{ref_id}"
            title = f"Landmark Reference {ref_id[:20]}"
            if title_map and ref_id in title_map:
                title = title_map[ref_id].get("title", title)
                url = title_map[ref_id].get("url", url)
            clean_t = title.replace("&", "\\&").replace("_", "\\_").replace("#", "\\#").replace("%", "\\%")
            link_str = f"\\href{{{url}}}{{{clean_t}}}"
            tex.append(f"{link_str} & {cnt:,} \\\\")
        tex.append("\\bottomrule")
        tex.append("\\end{tabular}")
        tex.append("\\end{table}")

        with open(t1, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
        with open(t1_top, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
            
        logger.info(f"Generated {t1} successfully!")
    except Exception as e:
        logger.warning(f"Could not generate co-citation tables: {e}")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results_37k"
    export_cocitation_tables(out_dir, force=True)
