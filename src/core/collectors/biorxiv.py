import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging
import re

logger = logging.getLogger(__name__)

class BioRxivCollector:
    """Collector for bioRxiv & medRxiv preprints via OpenAlex preprint index."""
    OPENALEX_URL = "https://api.openalex.org/works"

    def __init__(self, email: Optional[str] = None):
        self.email = email

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        """Fetches preprints from bioRxiv/medRxiv matching query and year range."""
        logger.info("Fetching preprints from bioRxiv/medRxiv...")
        headers = {}
        if self.email:
            headers["mailto"] = self.email
            
        clean_query = re.sub(r'[\(\)\*\"]', ' ', query)
        clean_query = re.sub(r'\b(AND|OR|NOT)\b', ' ', clean_query, flags=re.IGNORECASE)
        clean_query = re.sub(r'\s+', ' ', clean_query).strip()
        
        # OpenAlex filter for bioRxiv/medRxiv preprints
        filters = ["type:preprint"]
        if start_year:
            filters.append(f"from_publication_date:{start_year}-01-01")
        if end_year:
            filters.append(f"to_publication_date:{end_year}-12-31")

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
                "search": clean_query,
                "filter": ",".join(filters),
                "per_page": current_per_page,
                "cursor": cursor,
                "select": "title,abstract_inverted_index,authorships,publication_year,doi,ids,keywords,concepts,cited_by_count,referenced_works",
            }
            try:
                r = httpx.get(self.OPENALEX_URL, params=params, headers=headers, timeout=30.0)
                r.raise_for_status()
                data = r.json()
                results = data.get("results", [])
                meta = data.get("meta", {})
                next_cursor = meta.get("next_cursor")

                if not results:
                    break
                all_results.extend(results)
                fetched += len(results)

                if not next_cursor or next_cursor == cursor or len(results) < current_per_page:
                    break
                cursor = next_cursor
            except Exception as e:
                logger.error(f"Error fetching bioRxiv preprints: {e}")
                break

        return self._to_dataframe(all_results)

    def _to_dataframe(self, results: List[Dict]) -> pd.DataFrame:
        if not results:
            return pd.DataFrame()

        rows = []
        for item in results:
            title = item.get("title", "")
            abstract_dict = item.get("abstract_inverted_index")
            abstract = ""
            if abstract_dict:
                word_index = {}
                for word, pos_list in abstract_dict.items():
                    for pos in pos_list:
                        word_index[pos] = word
                abstract = " ".join([word_index[i] for i in sorted(word_index.keys())])

            authorships = item.get("authorships", [])
            authors = [a.get("author", {}).get("display_name") for a in authorships if a.get("author")]
            authors_str = "; ".join([a for a in authors if a])

            doi = item.get("doi", "")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi[len("https://doi.org/"):].strip()

            rows.append({
                "Title": title,
                "Abstract": abstract,
                "Authors": authors_str,
                "Year": item.get("publication_year"),
                "Source title": "bioRxiv / medRxiv Preprint",
                "DOI": doi,
                "Cite Count": item.get("cited_by_count", 0),
                "Source": "bioRxiv (Preprint)"
            })
        return pd.DataFrame(rows)
