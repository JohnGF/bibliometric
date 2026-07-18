import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class WebOfScienceCollector:
    BASE_URL = "https://api.clarivate.com/api/woslite"

    def __init__(self, api_key: Optional[str] = None):
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["X-ApiKey"] = api_key

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        """Fetches papers from Web of Science (WoS Lite API) matching query and year range with pagination."""
        if "X-ApiKey" not in self.headers or not self.headers["X-ApiKey"]:
            logger.warning("Web of Science API key not provided. Skipping Web of Science search.")
            return pd.DataFrame()

        all_results = []
        first_record = 1
        count = min(limit, 100)

        wos_query = f"TS=({query})"
        if start_year and end_year:
            wos_query += f" AND PY=({start_year}-{end_year})"
        elif start_year:
            wos_query += f" AND PY=({start_year}-2030)"
        elif end_year:
            wos_query += f" AND PY=(1800-{end_year})"

        while (first_record - 1) < limit:
            current_count = min(count, limit - (first_record - 1))
            payload = {
                "databaseId": "WOS",
                "usrQuery": wos_query,
                "count": current_count,
                "firstRecord": first_record
            }

            logger.info(f"Fetching Web of Science papers (firstRecord={first_record}, count={current_count})")
            try:
                response = httpx.post(self.BASE_URL, json=payload, headers=self.headers, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                results = data.get("Data", [])
                if not results:
                    break
                all_results.extend(results)
                first_record += len(results)
                if len(results) < current_count:
                    break
            except Exception as e:
                logger.error(f"Error fetching from Web of Science: {e}")
                break

        return self._to_dataframe(all_results)

    def _to_dataframe(self, results: List[Dict]) -> pd.DataFrame:
        rows = []
        for item in results:
            uid = item.get("UID", "")
            
            title = ""
            title_data = item.get("Title", {}).get("Title", [])
            if title_data:
                title = title_data[0]

            abstract = ""

            authors = []
            author_data = item.get("Author", {}).get("Authors", [])
            for auth in author_data:
                if auth:
                    authors.append(auth)
            authors_str = "; ".join(authors)

            year = None
            source_data = item.get("Source", {})
            pub_year_list = source_data.get("PublishedBiblioYear", [])
            if pub_year_list:
                try:
                    year = int(pub_year_list[0])
                except ValueError:
                    pass

            doi = ""
            other_data = item.get("Other", {})
            doi_list = other_data.get("IdentifierDoi", [])
            if doi_list:
                doi = doi_list[0]

            rows.append({
                "Title": title if title else None,
                "Abstract": abstract,
                "Authors": authors_str,
                "Year": year,
                "Affiliations": "",
                "DOI": doi if doi else None,
                "EID": uid if uid else None,
                "Author Keywords": "",
                "Cite Count": 0,
                "Source": "Web of Science"
            })
        return pd.DataFrame(rows)
