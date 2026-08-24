import re
import logging
import pandas as pd
from pydantic import BaseModel, Field
from typing import Optional, List

logger = logging.getLogger(__name__)

class StudyData(BaseModel):
    """Schema for extracting quantitative variables and Risk of Bias metrics."""
    sample_size: Optional[int] = Field(None, description="Total sample size (N)")
    effect_size_d: Optional[float] = Field(None, description="Cohen's d or Hedges' g")
    effect_size_r: Optional[float] = Field(None, description="Correlation r")
    odds_ratio: Optional[float] = Field(None, description="Odds Ratio (OR)")
    risk_ratio: Optional[float] = Field(None, description="Risk Ratio (RR)")
    mean: Optional[float] = Field(None, description="Group Mean")
    std_dev: Optional[float] = Field(None, description="Standard Deviation")
    accuracy: Optional[float] = Field(None, description="ML Accuracy metric")
    f1_score: Optional[float] = Field(None, description="ML F1 metric")
    auc: Optional[float] = Field(None, description="ML AUC metric")

    # Risk of Bias (RoB)
    is_randomized: bool = Field(False, description="Randomization mentioned")
    is_blinded: bool = Field(False, description="Blinding mentioned")
    attrition_reported: bool = Field(False, description="Attrition/drop-outs reported")


class VariableExtractor:
    """Extracts structured variables from parsed canonical sections using heuristic regexes."""

    def extract_from_text(self, text: str) -> StudyData:
        data = StudyData()
        if not text:
            return data

        # Sample size: N = 42, n=42, 42 subjects, 42 participants
        n_match = re.search(r'(?i)\b(?:N|n)\s*=\s*(\d+)\b', text)
        if not n_match:
            n_match = re.search(r'(?i)\b(\d+)\s+(?:subjects|participants|patients)\b', text)
        if n_match:
            try:
                data.sample_size = int(n_match.group(1))
            except ValueError:
                pass

        # Effect sizes
        d_match = re.search(r'(?i)\b(?:Cohen\'s\s+d|Hedges\'\s+g|d)\s*=\s*([+-]?\d*\.\d+)\b', text)
        if d_match:
            try: data.effect_size_d = float(d_match.group(1))
            except ValueError: pass

        r_match = re.search(r'(?i)\br\s*=\s*([+-]?\d*\.\d+)\b', text)
        if r_match:
            try: data.effect_size_r = float(r_match.group(1))
            except ValueError: pass

        or_match = re.search(r'(?i)\b(?:OR|Odds\s+Ratio)\s*=\s*([+-]?\d*\.\d+)\b', text)
        if or_match:
            try: data.odds_ratio = float(or_match.group(1))
            except ValueError: pass

        rr_match = re.search(r'(?i)\b(?:RR|Risk\s+Ratio)\s*=\s*([+-]?\d*\.\d+)\b', text)
        if rr_match:
            try: data.risk_ratio = float(rr_match.group(1))
            except ValueError: pass

        mean_match = re.search(r'(?i)\b(?:M|mean)\s*=\s*([+-]?\d*\.\d+)\b', text)
        if mean_match:
            try: data.mean = float(mean_match.group(1))
            except ValueError: pass

        sd_match = re.search(r'(?i)\b(?:SD|standard\s+deviation)\s*=\s*([+-]?\d*\.\d+)\b', text)
        if sd_match:
            try: data.std_dev = float(sd_match.group(1))
            except ValueError: pass

        # ML Metrics
        acc_match = re.search(r'(?i)\b(?:accuracy|acc)\s*(?:is|of|=)?\s*(\d*\.\d+|\d+%)\b', text)
        if acc_match:
            val = acc_match.group(1).replace('%', '')
            try:
                f_val = float(val)
                data.accuracy = f_val / 100.0 if f_val > 1.0 else f_val
            except ValueError: pass

        f1_match = re.search(r'(?i)\b(?:f1(?:-score)?)\s*(?:is|of|=)?\s*(\d*\.\d+)\b', text)
        if f1_match:
            try: data.f1_score = float(f1_match.group(1))
            except ValueError: pass

        auc_match = re.search(r'(?i)\b(?:auc|roc-auc)\s*(?:is|of|=)?\s*(\d*\.\d+)\b', text)
        if auc_match:
            try: data.auc = float(auc_match.group(1))
            except ValueError: pass

        # Risk of Bias
        if re.search(r'(?i)\brandomi[zs]ed\b', text):
            data.is_randomized = True
        if re.search(r'(?i)\bblind(?:ed|ing)?\b', text) or re.search(r'(?i)\bdouble-blind\b', text):
            data.is_blinded = True
        if re.search(r'(?i)\b(?:attrition|drop-?out)\b', text):
            data.attrition_reported = True

        return data

    def extract_dataframe(self, df: pd.DataFrame, text_cols: List[str] = None) -> pd.DataFrame:
        """Extracts variables from the provided dataframe text columns and appends them."""
        if df.empty:
            return df

        if text_cols is None:
            text_cols = ["extracted_abstract", "extracted_methods", "extracted_results", "Abstract"]

        logger.info(f"VariableExtractor: Extracting quantitative variables from {len(df)} papers...")

        extracted_rows = []
        for idx, row in df.iterrows():
            combined_text = ""
            for col in text_cols:
                if col in row and not pd.isna(row[col]):
                    combined_text += " " + str(row[col])

            study_data = self.extract_from_text(combined_text)
            extracted_rows.append(study_data.model_dump())

        ext_df = pd.DataFrame(extracted_rows)
        # Prefix the extracted columns
        ext_df = ext_df.add_prefix('meta_')

        df_out = pd.concat([df.reset_index(drop=True), ext_df.reset_index(drop=True)], axis=1)

        # Log summary
        valid_n = ext_df['meta_sample_size'].notna().sum()
        logger.info(f"VariableExtractor: Found sample size (N) for {valid_n} papers.")

        return df_out