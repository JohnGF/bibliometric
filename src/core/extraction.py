import re
import math
import logging
import pandas as pd
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class StudyData(BaseModel):
    """Schema for extracting quantitative variables and Risk of Bias across scientific domains."""
    # Universal identifiers
    domain: str = Field("general", description="Detected scientific domain: economics, biomedical, engineering, or general")
    sample_size: Optional[int] = Field(None, description="Total sample size (N)")
    
    # Standardized synthesis targets
    standardized_effect_d: Optional[float] = Field(None, description="Standardized effect size (Cohen's d equivalent)")
    effect_variance: Optional[float] = Field(None, description="Sampling variance v_i of the effect size")
    effect_direction: str = Field("neutral", description="Direction of finding: positive, negative, or neutral")
    
    # Biomedical & Clinical fields
    effect_size_d: Optional[float] = Field(None, description="Reported Cohen's d or Hedges' g")
    effect_size_r: Optional[float] = Field(None, description="Correlation r")
    odds_ratio: Optional[float] = Field(None, description="Odds Ratio (OR)")
    risk_ratio: Optional[float] = Field(None, description="Risk Ratio (RR)")
    mean: Optional[float] = Field(None, description="Group Mean")
    std_dev: Optional[float] = Field(None, description="Standard Deviation")
    
    # Economics & Social Policy fields
    percent_change: Optional[float] = Field(None, description="Percentage change in target outcome (% Delta)")
    elasticity: Optional[float] = Field(None, description="Price or supply elasticity (epsilon)")
    regression_beta: Optional[float] = Field(None, description="Econometric regression coefficient (beta)")
    standard_error: Optional[float] = Field(None, description="Standard error of regression estimate SE(beta)")
    t_statistic: Optional[float] = Field(None, description="Empirical t-statistic")
    
    # Engineering & Machine Learning fields
    accuracy: Optional[float] = Field(None, description="ML Accuracy metric (0.0 - 1.0)")
    f1_score: Optional[float] = Field(None, description="ML F1 metric")
    auc: Optional[float] = Field(None, description="ML AUC metric")
    snr_db: Optional[float] = Field(None, description="Signal-to-Noise Ratio improvement in dB")

    # Risk of Bias (RoB) / Methodological Rigor
    is_randomized: bool = Field(False, description="Randomization mentioned")
    is_blinded: bool = Field(False, description="Blinding mentioned")
    attrition_reported: bool = Field(False, description="Attrition/drop-outs reported")
    has_control_group: bool = Field(False, description="Control or comparison group mentioned")


class VariableExtractor:
    """Extracts structured variables across Economics, Biomedical, and Engineering literatures."""

    def detect_domain(self, text: str) -> str:
        """Heuristically detects the scientific discipline of the document."""
        lower = text.lower()
        if any(k in lower for k in ["rent", "housing", "landlord", "tenant", "wage", "tax", "elasticity", "econometric", "gdp", "market price"]):
            return "economics"
        elif any(k in lower for k in ["patient", "clinical", "trial", "placebo", "disease", "therapy", "mortality", "odds ratio"]):
            return "biomedical"
        elif any(k in lower for k in ["eeg", "bci", "signal", "decoding", "accuracy", "neural network", "deep learning", "classifier", "snr", "f1"]):
            return "engineering"
        return "general"

    def extract_from_text(self, text: str) -> StudyData:
        """Extracts structured variables and converts them to standardized effect sizes."""
        data = StudyData()
        if not text:
            return data

        data.domain = self.detect_domain(text)

        # 1. Sample size (N)
        n_match = re.search(r'(?i)\b(?:N|n)\s*=\s*(\d{1,7})\b', text)
        if not n_match:
            n_match = re.search(r'(?i)\b(\d{1,7})\s+(?:subjects|participants|patients|households|units|cities|samples)\b', text)
        if n_match:
            try:
                data.sample_size = int(n_match.group(1))
            except ValueError:
                pass

        # 2. Economics & Policy metrics
        # Percent change: -15%, +5.1%, decrease of 12%
        pct_match = re.search(r'(?i)(?:increase|decrease|decline|drop|growth|reduction|change)\s*(?:of|by|is)?\s*([+-]?\d*\.?\d+)\s*%', text)
        if not pct_match:
            pct_match = re.search(r'([+-]?\d*\.?\d+)\s*%\s*(?:increase|decrease|decline|reduction|change|drop)', text)
        if pct_match:
            try:
                val = float(pct_match.group(1))
                if any(neg in text.lower() for neg in ["decrease", "decline", "drop", "reduction", "loss"]) and val > 0:
                    val = -val
                data.percent_change = val
            except ValueError:
                pass

        # Elasticity: epsilon = -0.42, elasticity of 0.5
        elast_match = re.search(r'(?i)\b(?:elasticity|epsilon|\u03b5)\s*(?:of|=|is)?\s*([+-]?\d*\.?\d+)\b', text)
        if elast_match:
            try: data.elasticity = float(elast_match.group(1))
            except ValueError: pass

        # Beta & Standard Error: beta = -0.14, SE = 0.05
        beta_match = re.search(r'(?i)\b(?:beta|\u03b2)\s*=\s*([+-]?\d*\.?\d+)\b', text)
        if beta_match:
            try: data.regression_beta = float(beta_match.group(1))
            except ValueError: pass

        se_match = re.search(r'(?i)\b(?:SE|std\s*err(?:or)?)\s*=\s*([+-]?\d*\.?\d+)\b', text)
        if se_match:
            try: data.standard_error = float(se_match.group(1))
            except ValueError: pass

        # t-statistic: t = 2.45, t(59) = 3.2
        t_match = re.search(r'(?i)\bt(?:\(\d+\))?\s*=\s*([+-]?\d*\.?\d+)\b', text)
        if t_match:
            try: data.t_statistic = float(t_match.group(1))
            except ValueError: pass

        # 3. Biomedical metrics
        d_match = re.search(r'(?i)\b(?:Cohen\'s\s+d|Hedges\'\s+g|d)\s*=\s*([+-]?\d*\.?\d+)\b', text)
        if d_match:
            try: data.effect_size_d = float(d_match.group(1))
            except ValueError: pass

        r_match = re.search(r'(?i)\br\s*=\s*([+-]?\d*\.?\d+)\b', text)
        if r_match:
            try: data.effect_size_r = float(r_match.group(1))
            except ValueError: pass

        or_match = re.search(r'(?i)\b(?:OR|Odds\s+Ratio)\s*=\s*([+-]?\d*\.?\d+)\b', text)
        if or_match:
            try: data.odds_ratio = float(or_match.group(1))
            except ValueError: pass

        rr_match = re.search(r'(?i)\b(?:RR|Risk\s+Ratio)\s*=\s*([+-]?\d*\.?\d+)\b', text)
        if rr_match:
            try: data.risk_ratio = float(rr_match.group(1))
            except ValueError: pass

        mean_match = re.search(r'(?i)\b(?:M|mean)\s*=\s*([+-]?\d*\.?\d+)\b', text)
        if mean_match:
            try: data.mean = float(mean_match.group(1))
            except ValueError: pass

        sd_match = re.search(r'(?i)\b(?:SD|standard\s+deviation)\s*=\s*([+-]?\d*\.?\d+)\b', text)
        if sd_match:
            try: data.std_dev = float(sd_match.group(1))
            except ValueError: pass

        # 4. Engineering & ML metrics
        acc_match = re.search(r'(?i)\b(?:accuracy|acc)\s*(?:is|of|=)?\s*(\d*\.?\d+|\d+%)\b', text)
        if acc_match:
            val = acc_match.group(1).replace('%', '')
            try:
                f_val = float(val)
                data.accuracy = f_val / 100.0 if f_val > 1.0 else f_val
            except ValueError: pass

        f1_match = re.search(r'(?i)\b(?:f1(?:-score)?)\s*(?:is|of|=)?\s*(\d*\.?\d+)\b', text)
        if f1_match:
            try: data.f1_score = float(f1_match.group(1))
            except ValueError: pass

        auc_match = re.search(r'(?i)\b(?:auc|roc-auc)\s*(?:is|of|=)?\s*(\d*\.?\d+)\b', text)
        if auc_match:
            try: data.auc = float(auc_match.group(1))
            except ValueError: pass

        snr_match = re.search(r'(?i)\b(?:SNR|signal-to-noise)\s*(?:is|of|=|\+)?\s*([+-]?\d*\.?\d+)\s*dB\b', text)
        if snr_match:
            try: data.snr_db = float(snr_match.group(1))
            except ValueError: pass

        # 5. Methodological & Risk of Bias flags
        if re.search(r'(?i)\brandomi[zs]ed\b', text):
            data.is_randomized = True
        if re.search(r'(?i)\bblind(?:ed|ing)?\b', text) or re.search(r'(?i)\bdouble-blind\b', text):
            data.is_blinded = True
        if re.search(r'(?i)\b(?:attrition|drop-?out)\b', text):
            data.attrition_reported = True
        if re.search(r'(?i)\b(?:control\s+group|baseline|counterfactual|comparator|synthetic\s+control|difference-in-differences)\b', text):
            data.has_control_group = True

        # 6. Universal Standardization: Map domain findings to standardized d and variance
        n_eff = data.sample_size if (data.sample_size and data.sample_size >= 4) else 30

        if data.effect_size_d is not None:
            data.standardized_effect_d = data.effect_size_d
        elif data.t_statistic is not None:
            # d ≈ 2t / sqrt(N)
            data.standardized_effect_d = (2.0 * data.t_statistic) / math.sqrt(n_eff)
        elif data.odds_ratio is not None and data.odds_ratio > 0:
            # Chinn (2000) conversion: d = ln(OR) * sqrt(3) / pi
            data.standardized_effect_d = (math.log(data.odds_ratio) * math.sqrt(3)) / math.pi
        elif data.regression_beta is not None and data.standard_error and data.standard_error > 0:
            # t = beta / SE -> d ≈ 2t / sqrt(N)
            t_val = data.regression_beta / data.standard_error
            data.standardized_effect_d = (2.0 * t_val) / math.sqrt(n_eff)
        elif data.percent_change is not None:
            # Proxy mapping: standardizes percent changes into d-units (10% change ≈ 0.2 d)
            data.standardized_effect_d = data.percent_change / 50.0
        elif data.accuracy is not None:
            # Convert accuracy above 50% baseline to standardized effect
            gain = max(0.0, data.accuracy - 0.50)
            data.standardized_effect_d = gain * 2.5

        # Compute sampling variance v_i if standardized d exists
        if data.standardized_effect_d is not None:
            data.effect_variance = (4.0 / n_eff) + (data.standardized_effect_d**2 / (2.0 * n_eff))
            if data.standardized_effect_d > 0.001:
                data.effect_direction = "positive"
            elif data.standardized_effect_d < -0.001:
                data.effect_direction = "negative"
            else:
                data.effect_direction = "neutral"

        return data

    def extract_dataframe(self, df: pd.DataFrame, text_cols: Optional[List[str]] = None) -> pd.DataFrame:
        """Extracts variables across documents and appends prefixed metadata."""
        if df.empty:
            return df

        if text_cols is None:
            text_cols = ["extracted_abstract", "extracted_methods", "extracted_results", "Abstract"]

        logger.info(f"VariableExtractor: Extracting multi-domain variables from {len(df)} papers...")

        extracted_rows = []
        for idx, row in df.iterrows():
            combined_text = ""
            for col in text_cols:
                if col in row and not pd.isna(row[col]):
                    combined_text += " " + str(row[col])

            study_data = self.extract_from_text(combined_text)
            extracted_rows.append(study_data.model_dump())

        ext_df = pd.DataFrame(extracted_rows).add_prefix("meta_")
        df_out = pd.concat([df.reset_index(drop=True), ext_df.reset_index(drop=True)], axis=1)

        valid_effects = ext_df["meta_standardized_effect_d"].notna().sum()
        logger.info(f"VariableExtractor: Extracted standardized effects for {valid_effects}/{len(df)} studies.")
        return df_out
