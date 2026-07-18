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

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        """Fetches papers from Semantic Scholar with pagination."""
        all_results = []
        per_page = min(limit, 100)
        offset = 0
        
        year_range = ""
        if start_year and end_year:
            year_range = f"{start_year}-{end_year}"
        elif start_year:
            year_range = f"{start_year}-"
        elif end_year:
            year_range = f"-{end_year}"
            
        while offset < limit:
            current_limit = min(per_page, limit - offset)
            params = {
                "query": query,
                "limit": current_limit,
                "offset": offset,
                "fields": "title,abstract,authors,year,externalIds,citationCount,venue,publicationVenue",
            }
            if year_range:
                params["year"] = year_range
                
            logger.info(f"Fetching papers from Semantic Scholar (offset={offset}, limit={current_limit})")
            try:
                data = self._make_request(params)
                results = data.get("data", [])
                if not results:
                    break
                all_results.extend(results)
                offset += len(results)
                if len(results) < current_limit:
                    break
            except Exception as e:
                logger.error(f"Error fetching from Semantic Scholar: {e}")
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
            venue = res.get("venue") or res.get("publicationVenue", {}).get("name", "")
            
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
