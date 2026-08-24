import logging
import pandas as pd
import numpy as np
import scipy.stats as stats
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

class EffectSizeSynthesizer:
    """Executes classical and modern meta-analytic syntheses on extracted effect sizes."""

    def __init__(self):
        pass

    def run_meta_analysis(
        self,
        df: pd.DataFrame,
        effect_col: Optional[str] = None,
        n_col: Optional[str] = None,
        var_col: Optional[str] = None
    ) -> Tuple[Dict[str, Any], pd.DataFrame]:
        """Runs fixed and random effects meta-analysis given effect sizes and sample sizes."""
        if df.empty:
            return {}, pd.DataFrame()

        # Resolve effect size column
        eff_candidates = [c for c in [effect_col, "meta_standardized_effect_d", "meta_effect_size_d", "d_i", "effect_size"] if c and c in df.columns]
        if not eff_candidates:
            logger.warning("No valid effect size column found in DataFrame.")
            return {"k": 0}, pd.DataFrame()
        actual_eff_col = eff_candidates[0]

        # Resolve sample size column
        n_candidates = [c for c in [n_col, "meta_sample_size", "n_i", "sample_size", "N"] if c and c in df.columns]
        actual_n_col = n_candidates[0] if n_candidates else None

        # Resolve variance column
        v_candidates = [c for c in [var_col, "meta_effect_variance", "v_i", "variance"] if c and c in df.columns]
        actual_v_col = v_candidates[0] if v_candidates else None

        # Filter valid rows
        analysis_df = df.dropna(subset=[actual_eff_col]).copy()
        analysis_df["d_i"] = analysis_df[actual_eff_col].astype(float)

        # Handle sample sizes and variances
        if actual_n_col:
            analysis_df["n_i"] = pd.to_numeric(analysis_df[actual_n_col], errors="coerce").fillna(30.0).astype(float)
        else:
            analysis_df["n_i"] = 30.0

        if actual_v_col and actual_v_col in analysis_df.columns:
            analysis_df["v_i"] = pd.to_numeric(analysis_df[actual_v_col], errors="coerce").fillna(
                (4.0 / analysis_df["n_i"]) + (analysis_df["d_i"]**2 / (2.0 * analysis_df["n_i"]))
            )
        else:
            analysis_df["v_i"] = (4.0 / analysis_df["n_i"]) + (analysis_df["d_i"]**2 / (2.0 * analysis_df["n_i"]))

        # Ensure variance is strictly positive
        analysis_df["v_i"] = analysis_df["v_i"].apply(lambda v: max(0.0001, v) if not np.isnan(v) else 0.1)
        analysis_df["w_i"] = 1.0 / analysis_df["v_i"]

        k = len(analysis_df)
        if k < 2:
            logger.warning(f"Not enough valid studies (k={k}) for meta-analysis.")
            return {"k": k}, analysis_df

        # --- Fixed-Effects Model (Inverse-Variance) ---
        sum_w = analysis_df["w_i"].sum()
        sum_wd = (analysis_df["w_i"] * analysis_df["d_i"]).sum()

        fe_estimate = sum_wd / sum_w if sum_w > 0 else 0
        fe_se = np.sqrt(1.0 / sum_w) if sum_w > 0 else 0
        fe_z = fe_estimate / fe_se if fe_se > 0 else 0
        fe_p = 2.0 * (1.0 - stats.norm.cdf(abs(fe_z)))
        fe_ci_lower = fe_estimate - 1.96 * fe_se
        fe_ci_upper = fe_estimate + 1.96 * fe_se

        # --- Heterogeneity ---
        q_stat = (analysis_df["w_i"] * (analysis_df["d_i"] - fe_estimate)**2).sum()
        df_q = k - 1
        q_p = 1.0 - stats.chi2.cdf(q_stat, df_q) if df_q > 0 else 1.0

        i_squared = max(0.0, 100.0 * (q_stat - df_q) / q_stat) if q_stat > 0 else 0.0
        c = sum_w - (analysis_df["w_i"]**2).sum() / sum_w if sum_w > 0 else 0
        tau_squared = max(0.0, (q_stat - df_q) / c) if c > 0 else 0.0

        # --- Random-Effects Model (DerSimonian-Laird) ---
        analysis_df["w_star_i"] = 1.0 / (analysis_df["v_i"] + tau_squared)
        sum_w_star = analysis_df["w_star_i"].sum()
        sum_w_star_d = (analysis_df["w_star_i"] * analysis_df["d_i"]).sum()

        re_estimate = sum_w_star_d / sum_w_star if sum_w_star > 0 else 0
        re_se = np.sqrt(1.0 / sum_w_star) if sum_w_star > 0 else 0
        re_z = re_estimate / re_se if re_se > 0 else 0
        re_p = 2.0 * (1.0 - stats.norm.cdf(abs(re_z)))
        re_ci_lower = re_estimate - 1.96 * re_se
        re_ci_upper = re_estimate + 1.96 * re_se

        # --- Publication Bias (Egger's Test) ---
        try:
            prec = np.sqrt(analysis_df["w_i"])
            std_eff = analysis_df["d_i"] * prec
            slope, intercept, r_value, p_value, std_err = stats.linregress(prec, std_eff)
            eggers_p = p_value
        except Exception:
            eggers_p = 1.0

        # --- Begg's Rank Correlation Test ---
        try:
            tau, beggs_p = stats.kendalltau(analysis_df["d_i"], analysis_df["v_i"])
            if np.isnan(beggs_p):
                beggs_p = 1.0
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

        return results, analysis_df
