import os
import httpx
import logging
import pandas as pd
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class PDFRetriever:
    """Retrieves Open-Access PDFs for screened papers using Unpaywall and Crossref heuristics."""

    def __init__(self, cache_dir: str = "data/fulltext_cache", email: Optional[str] = "example@example.com"):
        self.cache_dir = cache_dir
        self.email = email
        os.makedirs(self.cache_dir, exist_ok=True)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
    )
    def _download_pdf(self, url: str, filepath: str) -> bool:
        try:
            with httpx.stream("GET", url, headers={"User-Agent": f"BibliometricPipeline (mailto:{self.email})"}, timeout=30.0, follow_redirects=True) as response:
                response.raise_for_status()
                # Ensure it's actually a PDF
                content_type = response.headers.get('content-type', '').lower()
                if 'application/pdf' not in content_type and not url.endswith('.pdf'):
                    # Some sources return HTML pages instead of raw PDFs if not handled carefully
                    logger.warning(f"URL {url} did not return a PDF content type ({content_type})")
                    return False

                with open(filepath, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
            return True
        except Exception as e:
            logger.warning(f"Failed to download PDF from {url}: {e}")
            raise e

    def _resolve_unpaywall_pdf(self, doi: str) -> Optional[str]:
        """Queries Unpaywall for an open access PDF link given a DOI."""
        if not doi: return None
        url = f"https://api.unpaywall.org/v2/{doi}?email={self.email}"
        try:
            response = httpx.get(url, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            if data.get("is_oa") and data.get("best_oa_location"):
                pdf_url = data["best_oa_location"].get("url_for_pdf")
                if pdf_url:
                    return pdf_url
        except Exception:
            pass
        return None

    def retrieve_pdfs(self, df: pd.DataFrame) -> pd.DataFrame:
        """Takes a DataFrame of papers, tries to download their PDFs, and adds the local filepath."""
        if df.empty:
            return df

        logger.info(f"PDFRetriever: Starting PDF retrieval for {len(df)} papers...")

        pdf_paths = []
        for idx, row in df.iterrows():
            doi = str(row.get("DOI", "")).strip()
            eid = str(row.get("EID", "")).strip()
            title = str(row.get("Title", "")).strip()

            # Clean DOI
            if doi:
                for prefix in ["https://doi.org/", "http://doi.org/", "doi.org/"]:
                    if doi.startswith(prefix):
                        doi = doi[len(prefix):]

            # Generate a safe filename
            safe_name = f"{doi.replace('/', '_')}" if doi else f"EID_{eid.replace(':', '_')}"
            if not safe_name or safe_name == "EID_":
                import re
                safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)[:50]
                if not safe_name: safe_name = f"paper_{idx}"

            filepath = os.path.join(self.cache_dir, f"{safe_name}.pdf")

            if os.path.exists(filepath):
                pdf_paths.append(filepath)
                continue

            # Attempt to resolve and download
            downloaded = False
            if doi:
                pdf_url = self._resolve_unpaywall_pdf(doi)
                if pdf_url:
                    try:
                        downloaded = self._download_pdf(pdf_url, filepath)
                    except Exception:
                        pass

            if downloaded:
                pdf_paths.append(filepath)
            else:
                pdf_paths.append(None)

        df_out = df.copy()
        df_out["local_pdf_path"] = pdf_paths
        retrieved_count = sum(1 for p in pdf_paths if p is not None)
        logger.info(f"PDFRetriever: Finished. Retrieved {retrieved_count}/{len(df)} PDFs.")

        return df_out