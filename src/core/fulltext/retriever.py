import os
import re
import httpx
import logging
import pandas as pd
from typing import Optional, List, Dict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class PDFRetriever:
    """Multi-source PDF retriever supporting OpenAlex OA, arXiv, PubMed Central, Elsevier ScienceDirect, and IEEE Xplore."""

    def __init__(
        self,
        cache_dir: str = "data/fulltext_cache",
        email: Optional[str] = None,
        scopus_api_key: Optional[str] = None,
        scopus_inst_token: Optional[str] = None,
        ieee_api_key: Optional[str] = None,
        pubmed_api_key: Optional[str] = None
    ):
        self.cache_dir = cache_dir
        self.email = email or os.getenv("OPENALEX_EMAIL") or os.getenv("CROSSREF_EMAIL") or "example@example.com"
        self.scopus_api_key = scopus_api_key or os.getenv("SCOPUS_API_KEY")
        self.scopus_inst_token = scopus_inst_token or os.getenv("SCOPUS_INST_TOKEN")
        self.ieee_api_key = ieee_api_key or os.getenv("IEEE_API_KEY")
        self.pubmed_api_key = pubmed_api_key or os.getenv("PUBMED_API_KEY")
        os.makedirs(self.cache_dir, exist_ok=True)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
    )
    def _download_pdf(self, url: str, filepath: str, headers: Optional[Dict[str, str]] = None) -> bool:
        """Streams a PDF file to disk with validation and retry."""
        req_headers = {"User-Agent": f"BibliometricPipeline (mailto:{self.email})"}
        if headers:
            req_headers.update(headers)

        try:
            with httpx.stream("GET", url, headers=req_headers, timeout=30.0, follow_redirects=True) as response:
                response.raise_for_status()
                content_type = response.headers.get('content-type', '').lower()
                
                # Check for PDF signature or binary content
                if 'application/pdf' not in content_type and not url.lower().endswith('.pdf'):
                    # Read initial bytes to verify PDF magic number %PDF
                    chunk_iter = response.iter_bytes()
                    first_chunk = next(chunk_iter, b"")
                    if not first_chunk.startswith(b"%PDF"):
                        logger.debug(f"URL {url} did not return valid PDF content ({content_type})")
                        return False
                    
                    with open(filepath, "wb") as f:
                        f.write(first_chunk)
                        for chunk in chunk_iter:
                            f.write(chunk)
                    return True

                with open(filepath, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
            return True
        except Exception as e:
            logger.debug(f"Failed to download PDF from {url}: {e}")
            raise e

    def _resolve_arxiv_pdf(self, doi: str, eid: str, title: str) -> Optional[str]:
        """Detects arXiv IDs from DOI, EID, or Title and constructs direct PDF URL."""
        # 10.48550/arXiv.2301.12345 or arXiv:2301.12345
        match = re.search(r'(?:arxiv\.org/abs/|arXiv:|\.arXiv\.)([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)', f"{doi} {eid}", re.IGNORECASE)
        if match:
            arxiv_id = match.group(1)
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        return None

    def _resolve_openalex_oa_pdf(self, doi: str) -> Optional[str]:
        """Queries OpenAlex for best open-access PDF location."""
        if not doi:
            return None
        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        headers = {"User-Agent": f"BibliometricPipeline (mailto:{self.email})"}
        try:
            res = httpx.get(url, headers=headers, timeout=12.0)
            if res.status_code == 200:
                data = res.json()
                oa_info = data.get("open_access", {})
                if oa_info.get("is_oa"):
                    best_oa = data.get("best_oa_location", {}) or {}
                    pdf_url = best_oa.get("pdf_url") or oa_info.get("oa_url")
                    if pdf_url:
                        return pdf_url
        except Exception:
            pass
        return None

    def _resolve_unpaywall_pdf(self, doi: str) -> Optional[str]:
        """Queries Unpaywall for an open access PDF link given a DOI."""
        if not doi:
            return None
        url = f"https://api.unpaywall.org/v2/{doi}?email={self.email}"
        try:
            response = httpx.get(url, timeout=12.0)
            if response.status_code == 200:
                data = response.json()
                if data.get("is_oa") and data.get("best_oa_location"):
                    return data["best_oa_location"].get("url_for_pdf")
        except Exception:
            pass
        return None

    def _resolve_elsevier_pdf(self, doi: str, filepath: str) -> bool:
        """Attempts retrieval via Elsevier ScienceDirect Article Retrieval API."""
        if not self.scopus_api_key or not doi:
            return False
        url = f"https://api.elsevier.com/content/article/doi/{doi}"
        headers = {
            "X-ELS-APIKey": self.scopus_api_key,
            "Accept": "application/pdf"
        }
        if self.scopus_inst_token:
            headers["X-ELS-Insttoken"] = self.scopus_inst_token
        try:
            return self._download_pdf(url, filepath, headers=headers)
        except Exception:
            return False

    def _resolve_ieee_pdf(self, doi: str, title: str, filepath: str) -> bool:
        """Attempts retrieval via IEEE Xplore API."""
        if not self.ieee_api_key:
            return False
        url = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
        params = {
            "apikey": self.ieee_api_key,
            "max_records": 1
        }
        if doi:
            params["doi"] = doi
        else:
            params["article_title"] = title[:80]

        try:
            res = httpx.get(url, params=params, timeout=15.0)
            if res.status_code == 200:
                data = res.json()
                articles = data.get("articles", [])
                if articles:
                    pdf_url = articles[0].get("pdf_url")
                    if pdf_url:
                        return self._download_pdf(pdf_url, filepath)
        except Exception:
            pass
        return False

    def filter_candidates(
        self,
        df: pd.DataFrame,
        min_citations: Optional[int] = None,
        required_keywords: Optional[List[str]] = None,
        min_relevance: Optional[float] = None,
        max_papers: Optional[int] = None
    ) -> pd.DataFrame:
        """Filters DataFrame to select high-priority papers for full-text downloading."""
        if df.empty:
            return df

        mask = pd.Series([True] * len(df), index=df.index)

        # 1. Min citations filter
        if min_citations is not None and "Cite Count" in df.columns:
            cite_counts = pd.to_numeric(df["Cite Count"], errors="coerce").fillna(0)
            mask &= (cite_counts >= min_citations)

        # 2. Relevance score filter
        if min_relevance is not None and "relevance_score" in df.columns:
            rel_scores = pd.to_numeric(df["relevance_score"], errors="coerce").fillna(0)
            mask &= (rel_scores >= min_relevance)

        # 3. Keywords filter
        if required_keywords:
            kw_cols = [c for c in ["Author Keywords", "Index Keywords", "Title", "Abstract"] if c in df.columns]
            def matches_keywords(row):
                text = " ".join([str(row[c]).lower() for c in kw_cols if pd.notna(row[c])])
                return any(k.lower() in text for k in required_keywords)
            mask &= df.apply(matches_keywords, axis=1)

        filtered_df = df[mask].copy()
        if max_papers and len(filtered_df) > max_papers:
            # Sort by citations if available, else take top N
            if "Cite Count" in filtered_df.columns:
                filtered_df = filtered_df.sort_values(by="Cite Count", ascending=False)
            filtered_df = filtered_df.head(max_papers)

        logger.info(f"PDFRetriever: Pre-filtered {len(filtered_df)} / {len(df)} papers for full-text retrieval.")
        return filtered_df

    def retrieve_pdfs(
        self,
        df: pd.DataFrame,
        min_citations: Optional[int] = None,
        required_keywords: Optional[List[str]] = None,
        min_relevance: Optional[float] = None,
        max_papers: Optional[int] = None
    ) -> pd.DataFrame:
        """Retrieves full-text PDFs using a multi-tier fallback cascade and flags outcomes."""
        if df.empty:
            return df

        # Mark which papers are candidates
        candidates = self.filter_candidates(
            df,
            min_citations=min_citations,
            required_keywords=required_keywords,
            min_relevance=min_relevance,
            max_papers=max_papers
        )
        candidate_indices = set(candidates.index)

        logger.info(f"PDFRetriever: Initiating download cascade for {len(candidate_indices)} candidate papers...")

        pdf_paths = []
        pdf_statuses = []
        pdf_sources = []

        for idx, row in df.iterrows():
            if idx not in candidate_indices:
                pdf_paths.append(None)
                pdf_statuses.append("skipped_filter")
                pdf_sources.append("none")
                continue

            doi = str(row.get("DOI", "")).strip()
            eid = str(row.get("EID", "")).strip()
            title = str(row.get("Title", "")).strip()

            # Clean DOI
            if doi:
                for prefix in ["https://doi.org/", "http://doi.org/", "doi.org/"]:
                    if doi.startswith(prefix):
                        doi = doi[len(prefix):]

            # Generate safe cache filename
            safe_name = f"{doi.replace('/', '_')}" if doi else f"EID_{eid.replace(':', '_')}"
            if not safe_name or safe_name == "EID_":
                safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)[:50]
                if not safe_name:
                    safe_name = f"paper_{idx}"

            filepath = os.path.join(self.cache_dir, f"{safe_name}.pdf")

            # Check cache
            if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
                pdf_paths.append(filepath)
                pdf_statuses.append("cached")
                pdf_sources.append("local_cache")
                continue

            downloaded = False
            source_used = "none"

            # 1. arXiv direct check
            arxiv_url = self._resolve_arxiv_pdf(doi, eid, title)
            if arxiv_url:
                try:
                    if self._download_pdf(arxiv_url, filepath):
                        downloaded = True
                        source_used = "arxiv"
                except Exception:
                    pass

            # 2. OpenAlex OA URL
            if not downloaded and doi:
                oa_url = self._resolve_openalex_oa_pdf(doi)
                if oa_url:
                    try:
                        if self._download_pdf(oa_url, filepath):
                            downloaded = True
                            source_used = "openalex_oa"
                    except Exception:
                        pass

            # 3. Elsevier ScienceDirect API
            if not downloaded and doi and ("10.1016" in doi or self.scopus_api_key):
                if self._resolve_elsevier_pdf(doi, filepath):
                    downloaded = True
                    source_used = "sciencedirect"

            # 4. IEEE Xplore API
            if not downloaded and (self.ieee_api_key or "10.1109" in doi):
                if self._resolve_ieee_pdf(doi, title, filepath):
                    downloaded = True
                    source_used = "ieee"

            # 5. Unpaywall fallback
            if not downloaded and doi:
                unpaywall_url = self._resolve_unpaywall_pdf(doi)
                if unpaywall_url:
                    try:
                        if self._download_pdf(unpaywall_url, filepath):
                            downloaded = True
                            source_used = "unpaywall"
                    except Exception:
                        pass

            if downloaded and os.path.exists(filepath):
                pdf_paths.append(filepath)
                pdf_statuses.append("downloaded")
                pdf_sources.append(source_used)
            else:
                pdf_paths.append(None)
                pdf_statuses.append("paywalled_or_unretrievable")
                pdf_sources.append("none")

        df_out = df.copy()
        df_out["local_pdf_path"] = pdf_paths
        df_out["pdf_retrieval_status"] = pdf_statuses
        df_out["pdf_source"] = pdf_sources

        downloaded_count = sum(1 for s in pdf_statuses if s in ["downloaded", "cached"])
        logger.info(f"PDFRetriever: Completed. Ready PDFs: {downloaded_count}/{len(candidate_indices)} (Skipped: {len(df) - len(candidate_indices)})")

        return df_out
