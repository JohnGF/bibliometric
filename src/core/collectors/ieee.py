import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging
import re

logger = logging.getLogger(__name__)

class IEEECollector:
    """Collector for IEEE Xplore publications.
    
    Supports:
    1. Official IEEE API Key via https://ieeexploreapi.ieee.org/api/v1/search/articles
    2. Open-access IEEE publisher fallback via OpenAlex (when no API key is set).
    """
    API_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
    OPENALEX_URL = "https://api.openalex.org/works"

    def __init__(self, api_key: Optional[str] = None, email: Optional[str] = None):
        self.api_key = api_key
        self.email = email

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None, resume: bool = True) -> pd.DataFrame:
        """Fetches IEEE papers matching query and year range with checkpoint recovery."""
        if self.api_key:
            df = self._fetch_official_api(query, limit, start_year, end_year, resume=resume)
            if not df.empty:
                return df
            logger.warning("IEEE Official API returned empty or failed. Falling back to OpenAlex IEEE Publisher Index...")

        return self._fetch_via_openalex_ieee(query, limit, start_year, end_year, resume=resume)

    def _fetch_official_api(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None, resume: bool = True) -> pd.DataFrame:
        from src.core.collectors.checkpoint import ScrapeCheckpointManager
        checkpoint_mgr = ScrapeCheckpointManager()

        all_results = []
        received_pages = []
        start_record = 1
        page = 0
        max_records = min(limit if limit > 0 else 200, 200)

        if resume:
            checkpoint = checkpoint_mgr.load("ieee_official", query, start_year, end_year)
            if checkpoint:
                all_results = checkpoint.get("items", [])
                received_pages = checkpoint.get("received_pages", [])
                start_record = checkpoint.get("offset", 1)
                page = checkpoint.get("last_page", 0)
                if checkpoint.get("is_complete") or (limit > 0 and len(all_results) >= limit):
                    logger.info(f"IEEE Official API fetch restored from checkpoint ({len(all_results)} items).")
                    return self._official_to_dataframe(all_results[:limit] if limit > 0 else all_results)

        logger.info(f"Fetching IEEE papers via Official API Key (start_record={start_record}, limit={limit})...")
        clean_query = re.sub(r'[\(\)\*\"]', ' ', query)
        clean_query = re.sub(r'\s+', ' ', clean_query).strip()

        while True:
            params = {
                "apikey": self.api_key,
                "querytext": clean_query,
                "max_records": max_records,
                "start_record": start_record,
                "format": "json",
            }
            if start_year:
                params["start_year"] = start_year
            if end_year:
                params["end_year"] = end_year

            page += 1
            try:
                r = httpx.get(self.API_URL, params=params, timeout=30.0)
                r.raise_for_status()
                data = r.json()
                articles = data.get("articles", [])
                if not articles:
                    if resume:
                        checkpoint_mgr.save("ieee_official", query, all_results, start_year, end_year, page=page, offset=start_record, received_pages=received_pages, is_complete=True)
                    break
                all_results.extend(articles)
                start_record += len(articles)
                received_pages.append(page)

                is_end = (len(articles) < max_records) or (limit > 0 and len(all_results) >= limit)
                if resume:
                    checkpoint_mgr.save("ieee_official", query, all_results, start_year, end_year, page=page, offset=start_record, received_pages=received_pages, is_complete=is_end)

                if is_end:
                    break
            except Exception as e:
                logger.error(f"Error fetching from IEEE Official API (saved checkpoint page {page}, items {len(all_results)}): {e}")
                break

        return self._official_to_dataframe(all_results)

    def _fetch_via_openalex_ieee(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None, resume: bool = True) -> pd.DataFrame:
        from src.core.collectors.checkpoint import ScrapeCheckpointManager
        checkpoint_mgr = ScrapeCheckpointManager()

        all_results = []
        received_pages = []
        cursor = "*"
        page = 0
        per_page = 200
        is_unlimited = (limit is None or limit <= 0)
        fetched = 0

        if resume:
            checkpoint = checkpoint_mgr.load("ieee_openalex", query, start_year, end_year)
            if checkpoint:
                all_results = checkpoint.get("items", [])
                received_pages = checkpoint.get("received_pages", [])
                cursor = checkpoint.get("last_cursor", "*")
                page = checkpoint.get("last_page", 0)
                fetched = len(all_results)
                if checkpoint.get("is_complete") or (not is_unlimited and fetched >= limit):
                    logger.info(f"IEEE OpenAlex fetch restored from checkpoint ({fetched} items).")
                    return self._openalex_to_dataframe(all_results[:limit] if not is_unlimited else all_results)

        logger.info(f"Fetching IEEE papers via OpenAlex IEEE Publisher index...")
        headers = {}
        if self.email:
            headers["mailto"] = self.email
        has_boolean = any(w in query.upper() for w in [" AND ", " OR ", " NOT "]) or '"' in query
        
        filters = ["primary_location.source.publisher_lineage:p4310319808"]  # IEEE Publisher ID
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

        while True:
            if not is_unlimited and fetched >= limit:
                if resume:
                    checkpoint_mgr.save("ieee_openalex", query, all_results, start_year, end_year, page=page, cursor=cursor, received_pages=received_pages, is_complete=True)
                break
            current_per_page = per_page if is_unlimited else min(per_page, limit - fetched)
            params = {
                "filter": ",".join(filters),
                "per_page": current_per_page,
                "cursor": cursor,
                "select": "title,abstract_inverted_index,authorships,publication_year,doi,ids,keywords,concepts,cited_by_count,referenced_works",
            }
            if search_param:
                params["search"] = search_param

            page += 1
            try:
                r = httpx.get(self.OPENALEX_URL, params=params, headers=headers, timeout=30.0)
                r.raise_for_status()
                data = r.json()
                results = data.get("results", [])
                meta = data.get("meta", {})
                next_cursor = meta.get("next_cursor")

                if not results:
                    if resume:
                        checkpoint_mgr.save("ieee_openalex", query, all_results, start_year, end_year, page=page, cursor=cursor, received_pages=received_pages, is_complete=True)
                    break
                all_results.extend(results)
                fetched += len(results)
                received_pages.append(page)

                is_end = (not next_cursor or next_cursor == cursor or len(results) < current_per_page)
                if resume:
                    checkpoint_mgr.save("ieee_openalex", query, all_results, start_year, end_year, page=page, cursor=next_cursor or cursor, received_pages=received_pages, is_complete=is_end)

                if is_end:
                    break
                cursor = next_cursor
            except Exception as e:
                logger.error(f"Error fetching IEEE papers via OpenAlex (saved checkpoint page {page}): {e}")
                break

        return self._openalex_to_dataframe(all_results)

    def _official_to_dataframe(self, articles: List[Dict]) -> pd.DataFrame:
        if not articles:
            return pd.DataFrame()
        
        rows = []
        for art in articles:
            authors = [a.get("full_name") for a in art.get("authors", {}).get("author", []) if a.get("full_name")]
            rows.append({
                "Title": art.get("title"),
                "Abstract": art.get("abstract"),
                "Authors": "; ".join(authors),
                "Year": art.get("publication_year"),
                "Source title": art.get("publication_title"),
                "DOI": art.get("doi"),
                "Cite Count": art.get("citing_paper_count", 0),
                "Source": "IEEE Xplore"
            })
        return pd.DataFrame(rows)

    def _openalex_to_dataframe(self, results: List[Dict]) -> pd.DataFrame:
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
                "Source title": "IEEE Xplore",
                "DOI": doi,
                "Cite Count": item.get("cited_by_count", 0),
                "Source": "IEEE Xplore"
            })
        return pd.DataFrame(rows)
