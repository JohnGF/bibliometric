import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class OpenAlexCollector:
    BASE_URL = "https://api.openalex.org/works"

    def __init__(self, email: Optional[str] = None):
        self.headers = {}
        if email:
            self.headers["mailto"] = email

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        """Fetches papers from OpenAlex based on a search query and year range with pagination."""
        all_results = []
        per_page = min(limit, 200)
        page = 1
        fetched = 0
        
        filters = []
        if start_year:
            filters.append(f"from_publication_date:{start_year}-01-01")
        if end_year:
            filters.append(f"to_publication_date:{end_year}-12-31")
            
        while fetched < limit:
            current_limit = min(per_page, limit - fetched)
            params = {
                "search": query,
                "per_page": current_limit,
                "page": page,
                "select": "title,abstract_inverted_index,authorships,publication_year,doi,ids,keywords,concepts,cited_by_count",
            }
            if filters:
                params["filter"] = ",".join(filters)
                
            logger.info(f"Fetching page {page} from OpenAlex for query: {query} (Limit page: {current_limit})")
            try:
                response = httpx.get(self.BASE_URL, params=params, headers=self.headers, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                if not results:
                    break
                all_results.extend(results)
                fetched += len(results)
                if len(results) < current_limit:
                    break
                page += 1
            except Exception as e:
                logger.error(f"Error fetching page {page} from OpenAlex: {e}")
                break
                
        return self._to_dataframe(all_results)

    def _reconstruct_abstract(self, inverted_index: Optional[Dict]) -> str:
        if not inverted_index:
            return ""
        word_index = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                word_index[pos] = word
        return " ".join([word_index[i] for i in sorted(word_index.keys())])

    def _to_dataframe(self, results: List[Dict]) -> pd.DataFrame:
        rows = []
        for res in results:
            authors = [a.get("author", {}).get("display_name", "") for a in res.get("authorships", [])]
            institutions = []
            for a in res.get("authorships", []):
                for inst in a.get("institutions", []):
                    inst_name = inst.get("display_name", "")
                    if inst_name and inst_name not in institutions:
                        institutions.append(inst_name)
            
            keywords = [k.get("display_name", "") for k in res.get("keywords", [])]
            
            row = {
                "Title": res.get("title"),
                "Abstract": self._reconstruct_abstract(res.get("abstract_inverted_index")),
                "Authors": "; ".join(filter(None, authors)),
                "Year": res.get("publication_year"),
                "Affiliations": "; ".join(filter(None, institutions)),
                "DOI": res.get("doi"),
                "EID": res.get("ids", {}).get("openalex"),
                "Author Keywords": "; ".join(filter(None, keywords)),
                "Cite Count": res.get("cited_by_count", 0),
                "Source": "OpenAlex"
            }
            rows.append(row)
        
        return pd.DataFrame(rows)
