import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging
import os

logger = logging.getLogger(__name__)

class SpringerCollector:
    """Collector for Springer Nature API.
    
    Supports Springer Nature API key (SPRINGER_API_KEY) or Crossref Springer member filter (member:297).
    Not triggered by default in UnifiedCollector.
    """
    API_URL = "https://api.springernature.com/meta/v2/json"
    CROSSREF_URL = "https://api.crossref.org/works"

    def __init__(self, api_key: Optional[str] = None, email: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SPRINGER_API_KEY")
        self.email = email or os.environ.get("OPENALEX_EMAIL")

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        if self.api_key:
            return self._fetch_official_api(query, limit, start_year, end_year)
        return self._fetch_via_crossref_springer(query, limit, start_year, end_year)

    def _fetch_official_api(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        logger.info(f"Fetching Springer papers via Official API (limit={limit})...")
        parsed = []
        page_size = 100
        start_index = 1
        is_unlimited = (limit is None or limit <= 0)

        while True:
            if not is_unlimited and len(parsed) >= limit:
                break

            q_str = f"keyword:{query}"
            if start_year and end_year:
                q_str += f" date:{start_year}-01-01/{end_year}-12-31"
            elif start_year:
                q_str += f" date:{start_year}-01-01/{start_year}-12-31"

            params = {
                "q": q_str,
                "api_key": self.api_key,
                "p": page_size if is_unlimited else min(page_size, limit - len(parsed)),
                "s": start_index
            }

            try:
                r = httpx.get(self.API_URL, params=params, timeout=30.0)
                r.raise_for_status()
                data = r.json()
                records = data.get("records", [])
                if not records:
                    break

                for rec in records:
                    authors = [a.get("creator", "") for a in rec.get("creators", []) if a.get("creator")]
                    date_str = rec.get("publicationDate", "")
                    year = int(date_str.split("-")[0]) if date_str and "-" in date_str else None

                    parsed.append({
                        "Title": rec.get("title", ""),
                        "Abstract": rec.get("abstract", ""),
                        "Authors": "; ".join(authors),
                        "Year": year,
                        "Affiliations": rec.get("publisher", "Springer"),
                        "DOI": rec.get("doi", ""),
                        "EID": rec.get("identifier", ""),
                        "Author Keywords": rec.get("publicationName", ""),
                        "Cite Count": 0,
                        "Source": "Springer Nature"
                    })

                start_index += len(records)
                total = int(data.get("result", [{}])[0].get("total", 0))
                if start_index > total:
                    break
            except Exception as e:
                logger.error(f"Error fetching from Springer Official API: {e}")
                break

        return pd.DataFrame(parsed)

    def _fetch_via_crossref_springer(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        logger.info(f"Fetching Springer papers via Crossref Member filter...")
        headers = {}
        if self.email:
            headers["User-Agent"] = f"BibliometricPipeline/1.0 (mailto:{self.email})"

        filters = ["member:297"]  # Springer Nature Crossref Member ID
        if start_year and end_year:
            filters.append(f"from-pub-date:{start_year},until-pub-date:{end_year}")
        elif start_year:
            filters.append(f"from-pub-date:{start_year}")

        parsed = []
        cursor = "*"
        rows = 100
        is_unlimited = (limit is None or limit <= 0)

        while True:
            if not is_unlimited and len(parsed) >= limit:
                break

            params = {
                "query": query,
                "filter": ",".join(filters),
                "rows": rows if is_unlimited else min(rows, limit - len(parsed)),
                "cursor": cursor
            }

            try:
                r = httpx.get(self.CROSSREF_URL, params=params, headers=headers, timeout=30.0)
                r.raise_for_status()
                data = r.json()
                items = data.get("message", {}).get("items", [])
                if not items:
                    break

                for item in items:
                    authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in item.get("author", [])]
                    year = None
                    date_parts = item.get("published-print", {}).get("date-parts") or item.get("issued", {}).get("date-parts")
                    if date_parts and date_parts[0]:
                        year = date_parts[0][0]

                    parsed.append({
                        "Title": item.get("title", [""])[0] if item.get("title") else "",
                        "Abstract": item.get("abstract", ""),
                        "Authors": "; ".join(authors),
                        "Year": year,
                        "Affiliations": item.get("publisher", "Springer"),
                        "DOI": item.get("DOI", ""),
                        "EID": item.get("URL", ""),
                        "Author Keywords": "",
                        "Cite Count": item.get("is-referenced-by-count", 0),
                        "Source": "Springer (Crossref)"
                    })

                cursor = data.get("message", {}).get("next-cursor")
                if not cursor:
                    break
            except Exception as e:
                logger.error(f"Error fetching Springer papers via Crossref: {e}")
                break

        return pd.DataFrame(parsed)
