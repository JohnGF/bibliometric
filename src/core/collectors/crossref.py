import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class CrossrefCollector:
    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, email: Optional[str] = None):
        self.headers = {}
        if email:
            self.headers["User-Agent"] = f"BibliometricPipeline/1.0 (mailto:{email})"
        else:
            self.headers["User-Agent"] = "BibliometricPipeline/1.0"

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        """Fetches papers from Crossref with pagination."""
        all_results = []
        per_page = min(limit, 1000)
        offset = 0
        
        filters = []
        if start_year and end_year:
            filters.append(f"from-pub-date:{start_year},until-pub-date:{end_year}")
        elif start_year:
            filters.append(f"from-pub-date:{start_year}")
        elif end_year:
            filters.append(f"until-pub-date:{end_year}")
            
        while offset < limit:
            current_limit = min(per_page, limit - offset)
            params = {
                "query": query,
                "rows": current_limit,
                "offset": offset,
                "select": "DOI,title,abstract,author,published-print,published-online,subject,is-referenced-by-count",
            }
            if filters:
                params["filter"] = ",".join(filters)
                
            logger.info(f"Fetching papers from Crossref (offset={offset}, limit={current_limit})")
            try:
                data = self._make_request(params)
                results = data.get("message", {}).get("items", [])
                if not results:
                    break
                all_results.extend(results)
                offset += len(results)
                if len(results) < current_limit:
                    break
            except Exception as e:
                logger.error(f"Error fetching from Crossref: {e}")
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
            # Authors reconstruction
            authors = []
            institutions = []
            for a in res.get("author", []):
                name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                if name:
                    authors.append(name)
                for aff in a.get("affiliation", []):
                    aff_name = aff.get("name")
                    if aff_name and aff_name not in institutions:
                        institutions.append(aff_name)
            
            # Year extraction
            year = None
            for date_key in ["published-print", "published-online", "issued"]:
                date_parts = res.get(date_key, {}).get("date-parts", [[]])[0]
                if date_parts:
                    year = date_parts[0]
                    break
            
            # Abstract cleaning
            abstract = res.get("abstract", "")
            if abstract.startswith("<jats:p>"):
                abstract = abstract.replace("<jats:p>", "").replace("</jats:p>", " ")
            
            row = {
                "Title": res.get("title", [None])[0] if res.get("title") else None,
                "Abstract": abstract,
                "Authors": "; ".join(authors),
                "Year": year,
                "Affiliations": "; ".join(institutions),
                "DOI": res.get("DOI"),
                "Author Keywords": "; ".join(res.get("subject", [])),
                "Cite Count": res.get("is-referenced-by-count", 0),
                "Source": "Crossref"
            }
            rows.append(row)
        
        return pd.DataFrame(rows)
