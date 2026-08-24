import os
import re
import logging
import pandas as pd
from typing import Dict

logger = logging.getLogger(__name__)

try:
    import pymupdf  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

class PDFParser:
    """Parses local PDFs and segments them into canonical sections."""

    def __init__(self):
        if not HAS_PYMUPDF:
            logger.warning("PyMuPDF (pymupdf) is not installed. PDFParser will return empty text.")

    def parse_pdf(self, filepath: str) -> Dict[str, str]:
        """Extracts text and segments it into basic canonical sections."""
        if not HAS_PYMUPDF or not filepath or not os.path.exists(filepath):
            return {"abstract": "", "methodology": "", "results": "", "full_text": ""}

        full_text = ""
        try:
            doc = pymupdf.open(filepath)
            for page in doc:
                full_text += page.get_text("text") + "\n"
            doc.close()
        except Exception as e:
            logger.warning(f"Error reading PDF {filepath}: {e}")
            return {"abstract": "", "methodology": "", "results": "", "full_text": ""}

        # Basic regex heuristics to find sections.
        # In reality, this is complex and depends heavily on publisher formatting.
        sections = {
            "abstract": "",
            "methodology": "",
            "results": "",
            "full_text": full_text
        }

        # Abstract extraction
        abs_match = re.search(r'(?i)(?:^|\n)\s*(?:Abstract|Summary)\s*\n(.*?)(?:(?:\n\s*(?:Introduction|Background)\s*\n)|$)', full_text, re.DOTALL)
        if abs_match:
            sections["abstract"] = abs_match.group(1).strip()

        # Methodology extraction
        meth_match = re.search(r'(?i)(?:^|\n)\s*(?:(?:Materials\s+and\s+)?Methods|Methodology|Experimental\s+Design)\s*\n(.*?)(?:(?:\n\s*(?:Results|Discussion|Conclusion)\s*\n)|$)', full_text, re.DOTALL)
        if meth_match:
            sections["methodology"] = meth_match.group(1).strip()

        # Results extraction
        res_match = re.search(r'(?i)(?:^|\n)\s*(?:Results(?:(?:\s+and\s+)?Discussion)?)\s*\n(.*?)(?:(?:\n\s*(?:Discussion|Conclusion|References)\s*\n)|$)', full_text, re.DOTALL)
        if res_match:
            sections["results"] = res_match.group(1).strip()

        return sections

    def parse_dataframe(self, df: pd.DataFrame, path_col: str = "local_pdf_path") -> pd.DataFrame:
        """Parses all PDFs in a DataFrame and appends the extracted sections as new columns."""
        if df.empty or path_col not in df.columns:
            return df

        logger.info(f"PDFParser: Extracting text from {len(df)} papers...")

        abstracts = []
        methods = []
        results = []

        for idx, row in df.iterrows():
            path = row.get(path_col)
            if pd.isna(path) or not path:
                abstracts.append("")
                methods.append("")
                results.append("")
                continue

            parsed = self.parse_pdf(str(path))
            abstracts.append(parsed.get("abstract", ""))
            methods.append(parsed.get("methodology", ""))
            results.append(parsed.get("results", ""))

        df_out = df.copy()
        df_out["extracted_abstract"] = abstracts
        df_out["extracted_methods"] = methods
        df_out["extracted_results"] = results

        parsed_count = sum(1 for m in methods if m)
        logger.info(f"PDFParser: Finished. Successfully parsed methodology sections for {parsed_count} papers.")

        return df_out