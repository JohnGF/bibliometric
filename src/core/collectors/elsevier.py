import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ElsevierCollector:
    BASE_URL = "https://api.elsevier.com/content/search/scopus"

    def __init__(self, api_key: Optional[str] = None, inst_token: Optional[str] = None):
        self.headers = {
            "Accept": "application/json"
        }
        if api_key:
            self.headers["X-ELS-APIKey"] = api_key
        if inst_token:
            self.headers["X-ELS-Insttoken"] = inst_token

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        """Fetches papers from Elsevier Scopus matching query and year range with pagination."""
        if "X-ELS-APIKey" not in self.headers or not self.headers["X-ELS-APIKey"]:
            logger.warning("Elsevier Scopus API key not provided. Skipping Scopus search.")
            return pd.DataFrame()

        all_results = []
        start = 0
        count = min(limit, 25)

        scopus_query = f"TITLE-ABS-KEY({query})"
        if start_year and end_year:
            scopus_query += f" AND PUBYEAR AFT {start_year - 1} AND PUBYEAR BEF {end_year + 1}"
        elif start_year:
            scopus_query += f" AND PUBYEAR AFT {start_year - 1}"
        elif end_year:
            scopus_query += f" AND PUBYEAR BEF {end_year + 1}"

        while start < limit:
            current_count = min(count, limit - start)
            params = {
                "query": scopus_query,
                "count": current_count,
                "start": start,
                "view": "STANDARD"
            }

            logger.info(f"Fetching Scopus papers (start={start}, count={current_count})")
            try:
                response = httpx.get(self.BASE_URL, params=params, headers=self.headers, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                results = data.get("search-results", {}).get("entry", [])
                
                if results and "error" in results[0]:
                    logger.error(f"Scopus API returned error: {results[0].get('error')}")
                    break
                    
                if not results:
                    break
                    
                all_results.extend(results)
                start += len(results)
                if len(results) < current_count:
                    break
            except Exception as e:
                logger.error(f"Error fetching from Scopus: {e}")
                break

        return self._to_dataframe(all_results)

    def _to_dataframe(self, results: List[Dict]) -> pd.DataFrame:
        rows = []
        for res in results:
            authors = []
            author_list = res.get("author", [])
            if isinstance(author_list, list):
                for a in author_list:
                    name = a.get("authname") or f"{a.get('given-name', '')} {a.get('surname', '')}".strip()
                    if name:
                        authors.append(name)
            elif isinstance(author_list, dict):
                name = author_list.get("authname") or f"{author_list.get('given-name', '')} {author_list.get('surname', '')}".strip()
                if name:
                    authors.append(name)
            authors_str = "; ".join(authors)

            affiliations = []
            affil_list = res.get("affiliation", [])
            if isinstance(affil_list, list):
                for aff in affil_list:
                    name = aff.get("affilname") or ""
                    city = aff.get("affiliation-city") or ""
                    country = aff.get("affiliation-country") or ""
                    label = f"{name}, {city}, {country}".strip(", ")
                    if label and label not in affiliations:
                        affiliations.append(label)
            elif isinstance(affil_list, dict):
                name = affil_list.get("affilname") or ""
                city = affil_list.get("affiliation-city") or ""
                country = affil_list.get("affiliation-country") or ""
                label = f"{name}, {city}, {country}".strip(", ")
                if label:
                    affiliations.append(label)
            affil_str = "; ".join(affiliations)

            year = None
            cover_date = res.get("prism:coverDate")
            if cover_date and isinstance(cover_date, str):
                try:
                    year = int(cover_date.split("-")[0])
                except (ValueError, IndexError):
                    pass

            rows.append({
                "Title": res.get("dc:title"),
                "Abstract": res.get("dc:description") or "",
                "Authors": authors_str,
                "Year": year,
                "Affiliations": affil_str,
                "DOI": res.get("prism:doi"),
                "EID": res.get("eid"),
                "Author Keywords": "",
                "Cite Count": int(res.get("citedby-count") or 0),
                "Source": "Scopus"
            })
        return pd.DataFrame(rows)
