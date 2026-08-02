import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class SemanticScholarCollector:
    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self, api_key: Optional[str] = None):
        self.headers = {}
        if api_key:
            self.headers["x-api-key"] = api_key

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None, resume: bool = True) -> pd.DataFrame:
        """Fetches papers from Semantic Scholar with pagination and automatic checkpoint recovery."""
        from src.core.collectors.checkpoint import ScrapeCheckpointManager
        checkpoint_mgr = ScrapeCheckpointManager()

        all_results = []
        received_pages = []
        per_page = min(limit if limit > 0 else 100, 100)
        offset = 0
        page = 0

        if resume:
            checkpoint = checkpoint_mgr.load("semantic_scholar", query, start_year, end_year)
            if checkpoint:
                all_results = checkpoint.get("items", [])
                received_pages = checkpoint.get("received_pages", [])
                offset = checkpoint.get("offset", 0)
                page = checkpoint.get("last_page", 0)
                if checkpoint.get("is_complete") or (limit > 0 and len(all_results) >= limit):
                    logger.info(f"Semantic Scholar fetch restored from checkpoint ({len(all_results)} items).")
                    return self._to_dataframe(all_results[:limit] if limit > 0 else all_results)

        year_range = ""
        if start_year and end_year:
            year_range = f"{start_year}-{end_year}"
        elif start_year:
            year_range = f"{start_year}-"
        elif end_year:
            year_range = f"-{end_year}"
            
        while limit <= 0 or offset < limit:
            current_limit = min(per_page, limit - offset) if limit > 0 else per_page
            params = {
                "query": query,
                "limit": current_limit,
                "offset": offset,
                "fields": "title,abstract,authors,year,externalIds,citationCount,venue,publicationVenue",
            }
            if year_range:
                params["year"] = year_range
                
            page += 1
            logger.info(f"Fetching papers from Semantic Scholar (Page {page}, offset={offset}, limit={current_limit})")
            try:
                data = self._make_request(params)
                results = data.get("data", [])
                if not results:
                    if resume:
                        checkpoint_mgr.save("semantic_scholar", query, all_results, start_year, end_year, page=page, offset=offset, received_pages=received_pages, is_complete=True)
                    break
                all_results.extend(results)
                offset += len(results)
                received_pages.append(page)

                is_end = (len(results) < current_limit)
                if resume:
                    checkpoint_mgr.save("semantic_scholar", query, all_results, start_year, end_year, page=page, offset=offset, received_pages=received_pages, is_complete=is_end)

                if is_end:
                    break
            except Exception as e:
                logger.error(f"Error fetching from Semantic Scholar (checkpoint saved at page {page}, offset {offset}): {e}")
                break
                
        return self._to_dataframe(all_results)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        reraise=True
    )
    def _make_request(self, params: Dict) -> Dict:
        response = httpx.get(self.BASE_URL, params=params, headers=self.headers, timeout=30.0)
        response.raise_for_status()
        return response.json()

    def _to_dataframe(self, results: List[Dict]) -> pd.DataFrame:
        rows = []
        for res in results:
            authors = [a.get("name", "") for a in res.get("authors", [])]
            pub_venue = res.get("publicationVenue") or {}
            venue = res.get("venue") or pub_venue.get("name", "")
            
            row = {
                "Title": res.get("title"),
                "Abstract": res.get("abstract"),
                "Authors": "; ".join(filter(None, authors)),
                "Year": res.get("year"),
                "Affiliations": venue, # SS doesn't always provide detailed affiliations in search
                "DOI": res.get("externalIds", {}).get("DOI"),
                "EID": res.get("paperId"),
                "Author Keywords": "", # SS search doesn't always return keywords directly
                "Cite Count": res.get("citationCount", 0),
                "Source": "Semantic Scholar"
            }
            rows.append(row)
        
        return pd.DataFrame(rows)
