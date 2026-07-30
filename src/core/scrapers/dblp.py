import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class DBLPCollector:
    """Collector for DBLP Computer Science Bibliography (IEEE, ACM, Springer CS).
    
    API docs: https://dblp.org/faq/How+to+use+the+dblp+search+API.html
    Not triggered by default in UnifiedCollector.
    """
    SEARCH_URL = "https://dblp.org/search/publ/api"

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        logger.info(f"Fetching DBLP papers for query '{query}' (limit={limit})...")
        parsed_results = []
        hits_per_page = 100
        first_record = 0
        is_unlimited = (limit is None or limit <= 0)

        while True:
            if not is_unlimited and len(parsed_results) >= limit:
                break

            params = {
                "q": query,
                "format": "json",
                "h": hits_per_page if is_unlimited else min(hits_per_page, limit - len(parsed_results)),
                "f": first_record
            }

            try:
                r = httpx.get(self.SEARCH_URL, params=params, timeout=30.0)
                r.raise_for_status()
                data = r.json()
                result = data.get("result", {})
                hits_data = result.get("hits", {})
                hit_list = hits_data.get("hit", [])

                if not hit_list:
                    break

                for hit in hit_list:
                    info = hit.get("info", {})
                    year_val = info.get("year")
                    try:
                        year_int = int(year_val) if year_val else None
                    except (ValueError, TypeError):
                        year_int = None

                    if start_year and year_int and year_int < start_year:
                        continue
                    if end_year and year_int and year_int > end_year:
                        continue

                    # Extract authors
                    authors_data = info.get("authors", {}).get("author", [])
                    if isinstance(authors_data, dict):
                        authors_data = [authors_data]
                    authors = [a.get("text", "") for a in authors_data if isinstance(a, dict) and a.get("text")]

                    title = info.get("title", "").rstrip(".")
                    venue = info.get("venue", "")
                    doi = info.get("doi", "")
                    ee = info.get("ee", "")

                    parsed_results.append({
                        "Title": title,
                        "Abstract": "",  # DBLP index does not store full abstracts
                        "Authors": "; ".join(authors),
                        "Year": year_int,
                        "Affiliations": "",
                        "DOI": doi,
                        "EID": info.get("key", ""),
                        "Author Keywords": venue,
                        "Cite Count": 0,
                        "Source": f"DBLP ({venue})" if venue else "DBLP"
                    })

                first_record += len(hit_list)
                total_hits = int(hits_data.get("@total", 0))
                if first_record >= total_hits:
                    break

            except Exception as e:
                logger.error(f"Error fetching from DBLP API: {e}")
                break

        return pd.DataFrame(parsed_results)
