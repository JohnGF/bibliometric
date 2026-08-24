import os
import json
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def export_meta_tables(output_dir: str = "pipeline_results", force: bool = False):
    """Exports PRISMA and Meta-Analysis summary LaTeX tables."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)
    
    # 1. Study Characteristics Table
    char_fpath = os.path.join(tables_dir, "tab_study_characteristics.tex")
    ext_csv = os.path.join(output_dir, "extracted_study_data.csv")
    if os.path.exists(ext_csv):
        try:
            df = pd.read_csv(ext_csv)
            # Filter to papers with either sample size or effect size or accuracy
            valid_mask = df["meta_sample_size"].notna() | df["meta_effect_size_d"].notna() | df["meta_accuracy"].notna()
            sub_df = df[valid_mask].head(15) if valid_mask.sum() > 0 else df.head(10)
            
            tex = [
                "\\subsection{Characteristics of Included Primary Studies}",
                "\\begin{table}[htbp]",
                "\\caption{Included Empirical Study Outcomes and Methodological Characteristics}",
                "\\label{tab:study_characteristics}",
                "\\scriptsize",
                "\\setlength{\\tabcolsep}{3pt}",
                "\\begin{tabular}{p{0.32\\linewidth} r r p{0.18\\linewidth} c c}",
                "\\toprule",
                "\\textbf{Study (Author, Year)} & \\textbf{N} & \\textbf{Effect ($d$)} & \\textbf{Key Outcome} & \\textbf{Random.} & \\textbf{Blinded} \\\\",
                "\\midrule"
            ]
            
            for _, row in sub_df.iterrows():
                auth = str(row.get("Authors", "")).split(";")[0].strip()
                yr = str(row.get("Year", "")).replace(".0", "")
                label = f"{auth} ({yr})" if auth else f"Study {yr}"
                label = label.replace("&", "\\&")[:30]
                
                n_val = f"{int(row['meta_sample_size'])}" if pd.notna(row.get("meta_sample_size")) else "---"
                d_val = f"{float(row['meta_effect_size_d']):.2f}" if pd.notna(row.get("meta_effect_size_d")) else "---"
                
                outcome = "---"
                if pd.notna(row.get("meta_accuracy")):
                    outcome = f"Acc: {float(row['meta_accuracy'])*100:.1f}\\%"
                elif pd.notna(row.get("meta_mean")):
                    outcome = f"M={float(row['meta_mean']):.1f}"
                
                rand_val = "Yes" if row.get("meta_is_randomized") else "No"
                blind_val = "Yes" if row.get("meta_is_blinded") else "No"
                
                tex.append(f"{label} & {n_val} & {d_val} & {outcome} & {rand_val} & {blind_val} \\\\")
                
            tex.append("\\bottomrule")
            tex.append("\\end{tabular}")
            tex.append("\\end{table}")
            
            with open(char_fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(tex))
            logger.info(f"Generated {char_fpath} successfully.")
        except Exception as e:
            logger.warning(f"Could not export tab_study_characteristics.tex: {e}")

    # 2. Meta-Analysis Model Synthesis Table
    summary_fpath = os.path.join(tables_dir, "tab_meta_analysis_summary.tex")
    res_json = os.path.join(output_dir, "meta_analysis_results.json")
    if os.path.exists(res_json):
        try:
            with open(res_json, "r") as f:
                res = json.load(f)
                
            k = res.get("k_studies", res.get("k", 0))
            fe = res.get("fixed_effects", {})
            re = res.get("random_effects", {})
            het = res.get("heterogeneity", {})
            bias = res.get("publication_bias", {})
            
            tex = [
                "\\subsection{Quantitative Synthesis \& Heterogeneity Diagnostics}",
                "\\begin{table}[htbp]",
                "\\caption{Statistical Meta-Analytic Pooled Estimates and Model Fit}",
                "\\label{tab:meta_summary}",
                "\\small",
                "\\begin{tabular}{p{0.45\\linewidth} r r}",
                "\\toprule",
                "\\textbf{Statistical Metric} & \\textbf{Value} & \\textbf{95\\% CI / Interpretation} \\\\",
                "\\midrule",
                f"Number of Synthesized Studies ($k$) & {k} & Valid Empirical Trials \\\\",
                f"Fixed-Effects Pooled Estimate ($d$) & {fe.get('estimate', 0):.2f} & [{fe.get('ci_lower', 0):.2f}, {fe.get('ci_upper', 0):.2f}] \\\\",
                f"Random-Effects Pooled Estimate ($d$) & {re.get('estimate', 0):.2f} & [{re.get('ci_lower', 0):.2f}, {re.get('ci_upper', 0):.2f}] \\\\",
                f"Heterogeneity $I^2$ Statistic & {het.get('i_squared_pct', 0):.1f}\\% & Higgins \\& Thompson \\\\",
                f"Between-Study Variance ($\\tau^2$) & {het.get('tau_squared', 0):.2f} & DerSimonian--Laird \\\\",
                f"Cochran's $Q$ Test ($p$-value) & {het.get('q_stat', 0):.2f} & $p = {het.get('q_p_value', 1.0):.4f}$ \\\\",
                f"Egger's Test for Small-Study Bias & $p = {bias.get('eggers_p_value', 1.0):.3f}$ & {'No Bias' if bias.get('eggers_p_value', 1.0) > 0.05 else 'Asymmetry Present'} \\\\",
                "\\bottomrule",
                "\\end{tabular}",
                "\\end{table}"
            ]
            
            with open(summary_fpath, "w", encoding="utf-8") as f:
                f.write("\n".join(tex))
            logger.info(f"Generated {summary_fpath} successfully.")
        except Exception as e:
            logger.warning(f"Could not export tab_meta_analysis_summary.tex: {e}")
