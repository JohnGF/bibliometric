import os
import re
import httpx
import logging
import asyncio
import pandas as pd
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

class PDFRetriever:
    """High-throughput asynchronous multi-source PDF retriever with concurrency limits and fallback cascade."""

    def __init__(
        self,
        cache_dir: str = "data/fulltext_cache",
        email: Optional[str] = None,
        scopus_api_key: Optional[str] = None,
        scopus_inst_token: Optional[str] = None,
        ieee_api_key: Optional[str] = None,
        pubmed_api_key: Optional[str] = None,
        max_concurrency: int = 8,
        timeout_seconds: float = 10.0
    ):
        self.cache_dir = cache_dir
        self.email = email or os.getenv("OPENALEX_EMAIL") or os.getenv("CROSSREF_EMAIL") or "example@example.com"
        self.scopus_api_key = scopus_api_key or os.getenv("SCOPUS_API_KEY")
        self.scopus_inst_token = scopus_inst_token or os.getenv("SCOPUS_INST_TOKEN")
        self.ieee_api_key = ieee_api_key or os.getenv("IEEE_API_KEY")
        self.pubmed_api_key = pubmed_api_key or os.getenv("PUBMED_API_KEY")
        self.max_concurrency = max_concurrency
        self.timeout_seconds = timeout_seconds
        os.makedirs(self.cache_dir, exist_ok=True)

    async def _async_download_file(self, client: httpx.AsyncClient, url: str, filepath: str, headers: Optional[Dict[str, str]] = None) -> bool:
        """Asynchronously streams and validates a PDF file."""
        req_headers = {"User-Agent": f"BibliometricPipeline (mailto:{self.email})"}
        if headers:
            req_headers.update(headers)

        try:
            async with client.stream("GET", url, headers=req_headers, timeout=self.timeout_seconds, follow_redirects=True) as response:
                if response.status_code != 200:
                    return False
                
                content_type = response.headers.get("content-type", "").lower()
                chunk_iter = response.aiter_bytes()
                first_chunk = await anext(chunk_iter, b"")
                
                # Check for PDF magic number or content type
                if not first_chunk.startswith(b"%PDF") and "application/pdf" not in content_type and not url.lower().endswith(".pdf"):
                    return False

                with open(filepath, "wb") as f:
                    f.write(first_chunk)
                    async for chunk in chunk_iter:
                        f.write(chunk)
            return os.path.exists(filepath) and os.path.getsize(filepath) > 1024
        except Exception:
            return False

    def _resolve_arxiv_url(self, doi: str, eid: str, title: str) -> Optional[str]:
        """Detects arXiv identifier and returns direct PDF link."""
        match = re.search(r'(?:arxiv\.org/abs/|arXiv:|\.arXiv\.)([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)', f"{doi} {eid}", re.IGNORECASE)
        if match:
            arxiv_id = match.group(1)
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        return None

    async def _resolve_openalex_oa_url(self, client: httpx.AsyncClient, doi: str) -> Optional[str]:
        """Queries OpenAlex for best open-access PDF link."""
        if not doi:
            return None
        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        headers = {"User-Agent": f"BibliometricPipeline (mailto:{self.email})"}
        try:
            res = await client.get(url, headers=headers, timeout=6.0)
            if res.status_code == 200:
                data = res.json()
                oa_info = data.get("open_access", {})
                if oa_info.get("is_oa"):
                    best_oa = data.get("best_oa_location", {}) or {}
                    return best_oa.get("pdf_url") or oa_info.get("oa_url")
        except Exception:
            pass
        return None

    async def _resolve_unpaywall_url(self, client: httpx.AsyncClient, doi: str) -> Optional[str]:
        """Queries Unpaywall for an open access PDF link."""
        if not doi:
            return None
        url = f"https://api.unpaywall.org/v2/{doi}?email={self.email}"
        try:
            res = await client.get(url, timeout=6.0)
            if res.status_code == 200:
                data = res.json()
                if data.get("is_oa") and data.get("best_oa_location"):
                    return data["best_oa_location"].get("url_for_pdf")
        except Exception:
            pass
        return None

    async def _resolve_elsevier_pdf(self, client: httpx.AsyncClient, doi: str, filepath: str) -> bool:
        """Retrieves article from Elsevier ScienceDirect API."""
        if not self.scopus_api_key or not doi:
            return False
        url = f"https://api.elsevier.com/content/article/doi/{doi}"
        headers = {
            "X-ELS-APIKey": self.scopus_api_key,
            "Accept": "application/pdf"
        }
        if self.scopus_inst_token:
            headers["X-ELS-Insttoken"] = self.scopus_inst_token
        return await self._async_download_file(client, url, filepath, headers=headers)

    async def _resolve_ieee_pdf(self, client: httpx.AsyncClient, doi: str, title: str, filepath: str) -> bool:
        """Retrieves article from IEEE Xplore API."""
        if not self.ieee_api_key:
            return False
        url = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
        params = {"apikey": self.ieee_api_key, "max_records": 1}
        if doi:
            params["doi"] = doi
        else:
            params["article_title"] = title[:80]

        try:
            res = await client.get(url, params=params, timeout=6.0)
            if res.status_code == 200:
                data = res.json()
                articles = data.get("articles", [])
                if articles:
                    pdf_url = articles[0].get("pdf_url")
                    if pdf_url:
                        return await self._async_download_file(client, pdf_url, filepath)
        except Exception:
            pass
        return False

    async def _fetch_single_paper(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        idx: int,
        row: pd.Series
    ) -> Tuple[int, Optional[str], str, str]:
        """Processes a single paper through the fallback cascade with concurrency control."""
        async with semaphore:
            doi = str(row.get("DOI", "")).strip()
            eid = str(row.get("EID", "")).strip()
            title = str(row.get("Title", "")).strip()

            if doi:
                for prefix in ["https://doi.org/", "http://doi.org/", "doi.org/"]:
                    if doi.startswith(prefix):
                        doi = doi[len(prefix):]

            safe_name = f"{doi.replace('/', '_')}" if doi else f"EID_{eid.replace(':', '_')}"
            if not safe_name or safe_name == "EID_":
                safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', title)[:50]
                if not safe_name:
                    safe_name = f"paper_{idx}"

            filepath = os.path.join(self.cache_dir, f"{safe_name}.pdf")

            if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
                return idx, filepath, "cached", "local_cache"

            # 1. arXiv
            arxiv_url = self._resolve_arxiv_url(doi, eid, title)
            if arxiv_url:
                if await self._async_download_file(client, arxiv_url, filepath):
                    return idx, filepath, "downloaded", "arxiv"

            # 2. OpenAlex OA
            if doi:
                oa_url = await self._resolve_openalex_oa_url(client, doi)
                if oa_url:
                    if await self._async_download_file(client, oa_url, filepath):
                        return idx, filepath, "downloaded", "openalex_oa"

            # 3. Elsevier ScienceDirect
            if doi and ("10.1016" in doi or self.scopus_api_key):
                if await self._resolve_elsevier_pdf(client, doi, filepath):
                    return idx, filepath, "downloaded", "sciencedirect"

            # 4. IEEE Xplore
            if self.ieee_api_key or "10.1109" in doi:
                if await self._resolve_ieee_pdf(client, doi, title, filepath):
                    return idx, filepath, "downloaded", "ieee"

            # 5. Unpaywall
            if doi:
                unpaywall_url = await self._resolve_unpaywall_url(client, doi)
                if unpaywall_url:
                    if await self._async_download_file(client, unpaywall_url, filepath):
                        return idx, filepath, "downloaded", "unpaywall"

            return idx, None, "paywalled_or_unretrievable", "none"

    def filter_candidates(
        self,
        df: pd.DataFrame,
        min_citations: Optional[int] = None,
        required_keywords: Optional[List[str]] = None,
        min_relevance: Optional[float] = None,
        max_papers: Optional[int] = None
    ) -> pd.DataFrame:
        """Filters DataFrame to select high-priority candidate papers for full-text downloading."""
        if df.empty:
            return df

        mask = pd.Series([True] * len(df), index=df.index)

        if min_citations is not None and "Cite Count" in df.columns:
            cite_counts = pd.to_numeric(df["Cite Count"], errors="coerce").fillna(0)
            mask &= (cite_counts >= min_citations)

        if min_relevance is not None and "relevance_score" in df.columns:
            rel_scores = pd.to_numeric(df["relevance_score"], errors="coerce").fillna(0)
            mask &= (rel_scores >= min_relevance)

        if required_keywords:
            kw_cols = [c for c in ["Author Keywords", "Index Keywords", "Title", "Abstract"] if c in df.columns]
            def matches_keywords(row):
                text = " ".join([str(row[c]).lower() for c in kw_cols if pd.notna(row[c])])
                return any(k.lower() in text for k in required_keywords)
            mask &= df.apply(matches_keywords, axis=1)

        filtered_df = df[mask].copy()
        if max_papers and len(filtered_df) > max_papers:
            if "Cite Count" in filtered_df.columns:
                filtered_df = filtered_df.sort_values(by="Cite Count", ascending=False)
            filtered_df = filtered_df.head(max_papers)

        logger.info(f"PDFRetriever: Pre-filtered {len(filtered_df)} / {len(df)} papers for full-text retrieval.")
        return filtered_df

    async def _retrieve_pdfs_async(self, df: pd.DataFrame, candidate_indices: set) -> List[Tuple[int, Optional[str], str, str]]:
        """Executes concurrent async downloads for all candidates."""
        semaphore = asyncio.Semaphore(self.max_concurrency)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            tasks = [
                self._fetch_single_paper(client, semaphore, idx, row)
                for idx, row in df.iterrows()
                if idx in candidate_indices
            ]
            return await asyncio.gather(*tasks)

    def retrieve_pdfs(
        self,
        df: pd.DataFrame,
        min_citations: Optional[int] = None,
        required_keywords: Optional[List[str]] = None,
        min_relevance: Optional[float] = None,
        max_papers: Optional[int] = None
    ) -> pd.DataFrame:
        """Retrieves full-text PDFs concurrently using async workers and tracks audit status."""
        if df.empty:
            return df

        candidates = self.filter_candidates(
            df,
            min_citations=min_citations,
            required_keywords=required_keywords,
            min_relevance=min_relevance,
            max_papers=max_papers
        )
        candidate_indices = set(candidates.index)

        logger.info(f"PDFRetriever: Initiating parallel async download for {len(candidate_indices)} candidate papers...")

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In nested event loop environments
                import nest_asyncio
                nest_asyncio.apply()
                results = loop.run_until_complete(self._retrieve_pdfs_async(df, candidate_indices))
            else:
                results = loop.run_until_complete(self._retrieve_pdfs_async(df, candidate_indices))
        except Exception:
            results = asyncio.run(self._retrieve_pdfs_async(df, candidate_indices))

        res_map = {idx: (path, status, src) for idx, path, status, src in results}

        pdf_paths = []
        pdf_statuses = []
        pdf_sources = []

        for idx in df.index:
            if idx in res_map:
                p, s, src = res_map[idx]
                pdf_paths.append(p)
                pdf_statuses.append(s)
                pdf_sources.append(src)
            else:
                pdf_paths.append(None)
                pdf_statuses.append("skipped_filter")
                pdf_sources.append("none")

        df_out = df.copy()
        df_out["local_pdf_path"] = pdf_paths
        df_out["pdf_retrieval_status"] = pdf_statuses
        df_out["pdf_source"] = pdf_sources

        downloaded_count = sum(1 for s in pdf_statuses if s in ["downloaded", "cached"])
        logger.info(f"PDFRetriever: Finished. Ready PDFs: {downloaded_count}/{len(candidate_indices)} (Skipped: {len(df) - len(candidate_indices)})")

        return df_out
