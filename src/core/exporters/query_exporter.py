import os
import sys
import logging

logger = logging.getLogger(__name__)


def export_query_table(output_dir: str = "pipeline_results", force: bool = False):
    """Generates annex_query.tex from the query configuration file.

    Reads data/query.txt (via src.core.study_config) and writes the search
    query and study period (start-end year) into the IEEEtran scaffold annex.
    """
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    fpath = os.path.join(tables_dir, "annex_query.tex")
    top_fpath = os.path.join(output_dir, "annex_query.tex")

    if not force and os.path.exists(fpath) and os.path.getsize(fpath) > 100:
        return

    from src.core.study_config import load_study_config
    cfg = load_study_config()
    query = cfg.get("query")
    start_year = cfg.get("start_year")
    end_year = cfg.get("end_year")

    if not query:
        logger.warning("No query configuration found; writing placeholder query annex.")
        query = "query not configured (see data/query.txt)"

    period_str = ""
    if start_year and end_year:
        period_str = f" (study period {start_year} -- {end_year})"

    query_tex = query.replace("\\", "\\textbackslash{}").replace("#", r"\#").replace("&", r"\&").replace("%", r"\%")

    tex = [
        "% Search Query Annex",
        "\\subsection{Complete Search Query Strategy}",
        "\\label{sec:complete_query}",
        f"Detailed multi-database search query used for publication retrieval{period_str}:",
        "",
        "\\begin{quote}",
        "\\small\\ttfamily\\raggedright",
        query_tex,
        "\\end{quote}",
    ]

    with open(fpath, "w", encoding="utf-8") as f:
        f.write("\n".join(tex))
    with open(top_fpath, "w", encoding="utf-8") as f:
        f.write("\n".join(tex))
    logger.info(f"Generated {fpath} from query configuration.")


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results"
    export_query_table(out_dir, force=True)
