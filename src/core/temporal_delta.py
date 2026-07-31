import pandas as pd
import numpy as np
import logging
from typing import Tuple, Dict, Optional

logger = logging.getLogger(__name__)

class TemporalDeltaAnalysis:
    """
    Computes scientific temporal dynamics and delta shifts (\Delta) between
    baseline (historical) vs modern epochs for bibliometric features.
    """
    def __init__(self):
        pass

    def compute_temporal_deltas(
        self, 
        df: pd.DataFrame, 
        category_col: str, 
        year_col: str = "Year",
        split_year: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Computes volume and market share deltas (\Delta Share %) between two temporal epochs.
        """
        if df.empty or category_col not in df.columns or year_col not in df.columns:
            logger.warning(f"Required columns missing for temporal delta analysis on '{category_col}'.")
            return pd.DataFrame()

        clean_df = df.dropna(subset=[category_col, year_col]).copy()
        clean_df[year_col] = clean_df[year_col].astype(int)

        years = sorted(clean_df[year_col].unique())
        if len(years) < 2:
            logger.warning("Insufficient year span for temporal delta calculation.")
            return pd.DataFrame()

        if split_year is None:
            split_year = int(np.median(years))

        t1_df = clean_df[clean_df[year_col] < split_year]
        t2_df = clean_df[clean_df[year_col] >= split_year]

        total_t1 = len(t1_df) if len(t1_df) > 0 else 1
        total_t2 = len(t2_df) if len(t2_df) > 0 else 1

        t1_counts = t1_df[category_col].value_counts()
        t2_counts = t2_df[category_col].value_counts()

        all_categories = set(t1_counts.index).union(set(t2_counts.index))

        records = []
        for cat in all_categories:
            n_t1 = int(t1_counts.get(cat, 0))
            n_t2 = int(t2_counts.get(cat, 0))
            
            s_t1 = (n_t1 / total_t1) * 100.0
            s_t2 = (n_t2 / total_t2) * 100.0
            
            delta_share = s_t2 - s_t1
            fold_change = (s_t2 / s_t1) if s_t1 > 0 else (s_t2 if s_t2 > 0 else 1.0)
            
            if delta_share > 1.5:
                trajectory = "Emerging Frontier"
            elif delta_share < -1.5:
                trajectory = "Maturing/Declining"
            else:
                trajectory = "Sustained Core"

            records.append({
                "Category": cat,
                "Baseline_Count_T1": n_t1,
                "Modern_Count_T2": n_t2,
                "Baseline_Share_Pct": round(s_t1, 2),
                "Modern_Share_Pct": round(s_t2, 2),
                "Delta_Share_Pct": round(delta_share, 2),
                "Fold_Change": round(fold_change, 2),
                "Trajectory": trajectory
            })

        result_df = pd.DataFrame(records)
        if not result_df.empty:
            result_df = result_df.sort_values("Delta_Share_Pct", ascending=False).reset_index(drop=True)

        logger.info(f"Computed temporal delta analysis across {len(result_df)} items (Split Year: {split_year}).")
        return result_df
