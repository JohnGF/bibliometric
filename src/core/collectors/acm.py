import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging
import re

logger = logging.getLogger(__name__)

class ACMCollector:
    """Collector for ACM (Association for Computing Machinery) publications.
    
    Uses OpenAlex ACM Publisher Lineage Index (p4310319965) and Crossref to fetch
    ACM journal and conference papers without requiring fragile web scrapers or paid API keys.
    """
    OPENALEX_URL = "https://api.openalex.org/works"
    ACM_PUBLISHER_ID = "p4310319965"  # ACM Publisher Lineage ID in OpenAlex

    def __init__(self, email: Optional[str] = None):
        self.email = email

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        """Fetches ACM papers matching query and year range."""
        logger.info(f"Fetching ACM papers via OpenAlex ACM Publisher index...")
        headers = {}
        if self.email:
            headers["mailto"] = self.email

        has_boolean = any(w in query.upper() for w in [" AND ", " OR ", " NOT "]) or '"' in query

        filters = [f"primary_location.source.publisher_lineage:{self.ACM_PUBLISHER_ID}"]
        if start_year:
            filters.append(f"from_publication_date:{start_year}-01-01")
        if end_year:
            filters.append(f"to_publication_date:{end_year}-12-31")

        if has_boolean:
            filters.append(f"title_and_abstract.search:{query}")
            search_param = None
        else:
            clean_query = re.sub(r'[\(\)\*\"]', ' ', query)
            clean_query = re.sub(r'\b(AND|OR|NOT)\b', ' ', clean_query, flags=re.IGNORECASE)
            clean_query = re.sub(r'\s+', ' ', clean_query).strip()
            search_param = clean_query

        all_results = []
        cursor = "*"
        per_page = 200
        is_unlimited = (limit is None or limit <= 0)
        fetched = 0

        while True:
            if not is_unlimited and fetched >= limit:
                break
            current_per_page = per_page if is_unlimited else min(per_page, limit - fetched)

            params = {
                "filter": ",".join(filters),
                "per-page": current_per_page,
                "cursor": cursor
            }
            if search_param:
                params["search"] = search_param

            try:
                r = httpx.get(self.OPENALEX_URL, params=params, headers=headers, timeout=30.0)
                r.raise_for_status()
                data = r.json()
                results = data.get("results", [])
                if not results:
                    break
                all_results.extend(results)
                fetched += len(results)

                cursor = data.get("meta", {}).get("next_cursor")
                if not cursor:
                    break
            except Exception as e:
                logger.error(f"Error fetching ACM papers via OpenAlex: {e}")
                break

        return self._to_dataframe(all_results)

    def _to_dataframe(self, results: List[Dict]) -> pd.DataFrame:
        parsed = []
        for item in results:
            authors_list = []
            affils_list = []
            for auth in item.get("authorships", []):
                name = auth.get("author", {}).get("display_name")
                if name:
                    authors_list.append(name)
                for inst in auth.get("institutions", []):
                    inst_name = inst.get("display_name")
                    if inst_name and inst_name not in affils_list:
                        affils_list.append(inst_name)

            title = item.get("title") or ""
            abstract = ""
            inv_abstract = item.get("abstract_inverted_index")
            if inv_abstract:
                word_positions = []
                for word, pos_list in inv_abstract.items():
                    for pos in pos_list:
                        word_positions.append((pos, word))
                word_positions.sort()
                abstract = " ".join([wp[1] for wp in word_positions])

            parsed.append({
                "Title": title,
                "Abstract": abstract,
                "Authors": "; ".join(authors_list),
                "Year": item.get("publication_year"),
                "Affiliations": "; ".join(affils_list),
                "DOI": item.get("doi"),
                "EID": item.get("id"),
                "Author Keywords": "; ".join([k.get("display_name", "") for k in item.get("keywords", []) if k.get("display_name")]),
                "Cite Count": item.get("cited_by_count", 0),
                "Source": "ACM",
            })
        return pd.DataFrame(parsed)
