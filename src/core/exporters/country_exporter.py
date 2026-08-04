import os
import sys
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def export_country_table(output_dir: str = "pipeline_results", force: bool = False):
    """Generates annex_country_growth.tex containing Country Volume & CAGR Growth Rates."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    fpath = os.path.join(tables_dir, "annex_country_growth.tex")
    top_fpath = os.path.join(output_dir, "annex_country_growth.tex")

    if not force and os.path.exists(fpath) and os.path.getsize(fpath) > 100:
        return

    c_csv = os.path.join(output_dir, "data", "country_evolution.csv")
    if not os.path.exists(c_csv):
        c_csv = os.path.join(output_dir, "country_evolution.csv")

    if os.path.exists(c_csv):
        try:
            df = pd.read_csv(c_csv)
            from src.core.countries import CountryAnalysis
            cagr_df = CountryAnalysis().calculate_country_cagr(df)
            if not cagr_df.empty:
                tex = []
                tex.append("\\subsection{Country Publication Volume \\& Compound Annual Growth Rate (CAGR)}")
                tex.append("\\begin{table}[htbp]")
                tex.append("\\caption{Global Institutional Research Output and Country CAGR Growth}")
                tex.append("\\label{tab:country_growth}")
                tex.append("\\small")
                tex.append("\\setlength{\\tabcolsep}{4pt}")
                tex.append("\\begin{tabular}{r p{0.24\\linewidth} r r p{0.17\\linewidth}}")
                tex.append("\\toprule")
                tex.append("\\textbf{\\#} & \\textbf{Country} & \\textbf{Total Papers} & \\textbf{CAGR (\\%)} & \\textbf{Status} \\\\")
                tex.append("\\midrule")
                for i, (_, r) in enumerate(cagr_df.head(20).iterrows(), 1):
                    cname = str(r["Country"]).replace("_", "\\_").replace("&", "\\&")
                    cnt = int(r["Total_Count"])
                    cagr = float(r["CAGR_percent"])
                    status = str(r["Trend"])
                    tex.append(f"{i} & {cname} & {cnt:,} & {cagr:.1f}\\% & {status} \\\\")
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
            logger.warning(f"Could not generate annex_country_growth.tex: {e}")

    with open(fpath, "w", encoding="utf-8") as f:
        f.write("% Country Growth Annex\n\\subsection{Country Growth Rates}\n\\label{tab:country_growth}\n")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results"
    export_country_table(out_dir, force=True)
