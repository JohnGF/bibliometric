import logging
import pandas as pd
import numpy as np
import scipy.stats as stats
from typing import Dict, Any

logger = logging.getLogger(__name__)

class EffectSizeSynthesizer:
    """Executes classical and modern meta-analytic syntheses on extracted effect sizes."""

    def __init__(self):
        pass

    def run_meta_analysis(self, df: pd.DataFrame, effect_col: str = "meta_effect_size_d", n_col: str = "meta_sample_size") -> tuple[Dict[str, Any], pd.DataFrame]:
        """Runs fixed/random effects meta-analysis given effect sizes and sample sizes."""
        if df.empty or effect_col not in df.columns or n_col not in df.columns:
            logger.warning("Missing required columns for meta-analysis.")
            return {}, pd.DataFrame()

        # Drop rows with missing values
        analysis_df = df.dropna(subset=[effect_col, n_col]).copy()
        k = len(analysis_df)

        if k < 2:
            logger.warning(f"Not enough valid studies (k={k}) for meta-analysis.")
            return {"k": k}, analysis_df

        # Calculate standard errors and variances
        # Using approximation for Cohen's d var(d) ≈ (N_t + N_c)/(N_t * N_c) + d^2 / (2*(N_t + N_c))
        # Assuming equal group sizes N/2 for simplicity if only total N is provided
        analysis_df["n_i"] = analysis_df[n_col].astype(float)
        analysis_df["d_i"] = analysis_df[effect_col].astype(float)

        # Variance of Cohen's d (approx)
        analysis_df["v_i"] = (4 / analysis_df["n_i"]) + (analysis_df["d_i"]**2 / (2 * analysis_df["n_i"]))
        analysis_df["w_i"] = 1 / analysis_df["v_i"]  # Inverse variance weights

        # --- Fixed-Effects Model (Inverse-Variance) ---
        sum_w = analysis_df["w_i"].sum()
        sum_wd = (analysis_df["w_i"] * analysis_df["d_i"]).sum()

        fe_estimate = sum_wd / sum_w if sum_w > 0 else 0
        fe_se = np.sqrt(1 / sum_w) if sum_w > 0 else 0
        fe_z = fe_estimate / fe_se if fe_se > 0 else 0
        fe_p = 2 * (1 - stats.norm.cdf(abs(fe_z)))
        fe_ci_lower = fe_estimate - 1.96 * fe_se
        fe_ci_upper = fe_estimate + 1.96 * fe_se

        # --- Heterogeneity ---
        # Cochran's Q
        q_stat = (analysis_df["w_i"] * (analysis_df["d_i"] - fe_estimate)**2).sum()
        df_q = k - 1
        q_p = 1 - stats.chi2.cdf(q_stat, df_q) if df_q > 0 else 1.0

        # I^2 (Higgins & Thompson)
        i_squared = max(0.0, 100 * (q_stat - df_q) / q_stat) if q_stat > 0 else 0.0

        # Tau^2 (DerSimonian-Laird estimator)
        c = sum_w - (analysis_df["w_i"]**2).sum() / sum_w if sum_w > 0 else 0
        tau_squared = max(0.0, (q_stat - df_q) / c) if c > 0 else 0.0

        # --- Random-Effects Model (DerSimonian-Laird) ---
        analysis_df["w_star_i"] = 1 / (analysis_df["v_i"] + tau_squared)
        sum_w_star = analysis_df["w_star_i"].sum()
        sum_w_star_d = (analysis_df["w_star_i"] * analysis_df["d_i"]).sum()

        re_estimate = sum_w_star_d / sum_w_star if sum_w_star > 0 else 0
        re_se = np.sqrt(1 / sum_w_star) if sum_w_star > 0 else 0
        re_z = re_estimate / re_se if re_se > 0 else 0
        re_p = 2 * (1 - stats.norm.cdf(abs(re_z)))
        re_ci_lower = re_estimate - 1.96 * re_se
        re_ci_upper = re_estimate + 1.96 * re_se

        # --- Publication Bias (Egger's Test) ---
        # Regress standardized effect size (d/se) on precision (1/se)
        try:
            prec = np.sqrt(analysis_df["w_i"]) # 1 / SE
            std_eff = analysis_df["d_i"] * prec
            slope, intercept, r_value, p_value, std_err = stats.linregress(prec, std_eff)
            eggers_p = p_value
        except Exception:
            eggers_p = 1.0

        # --- Begg's Rank Correlation Test ---
        try:
            # Correlate effect size with variance (or std error)
            tau, beggs_p = stats.kendalltau(analysis_df["d_i"], analysis_df["v_i"])
            if np.isnan(beggs_p): beggs_p = 1.0
        except Exception:
            beggs_p = 1.0

        results = {
            "k_studies": k,
            "fixed_effects": {
                "estimate": fe_estimate,
                "se": fe_se,
                "z": fe_z,
                "p_value": fe_p,
                "ci_lower": fe_ci_lower,
                "ci_upper": fe_ci_upper
            },
            "random_effects": {
                "estimate": re_estimate,
                "se": re_se,
                "z": re_z,
                "p_value": re_p,
                "ci_lower": re_ci_lower,
                "ci_upper": re_ci_upper
            },
            "heterogeneity": {
                "q_stat": q_stat,
                "q_p_value": q_p,
                "i_squared_pct": i_squared,
                "tau_squared": tau_squared
            },
            "publication_bias": {
                "eggers_p_value": eggers_p,
                "beggs_p_value": beggs_p
            }
        }

        # Also return the augmented dataframe with variances for plotting
        return results, analysis_df
