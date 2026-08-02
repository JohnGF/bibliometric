import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class OpenAlexCollector:
    BASE_URL = "https://api.openalex.org/works"

    def __init__(self, email: Optional[str] = None):
        self.headers = {}
        if email:
            self.headers["mailto"] = email

    def fetch_papers(self, query: str, limit: Optional[int] = 100, start_year: Optional[int] = None, end_year: Optional[int] = None, resume: bool = True) -> pd.DataFrame:
        """Fetches papers from OpenAlex using cursor-based deep pagination with automatic checkpoint recovery.
        
        Set limit=None or limit=0 for unlimited fetching of all matching papers.
        Set resume=True to automatically recover from previous interrupted session/pages.
        """
        from src.core.collectors.checkpoint import ScrapeCheckpointManager
        checkpoint_mgr = ScrapeCheckpointManager()
        
        all_results = []
        received_pages = []
        per_page = 200  # OpenAlex max items per request
        cursor = "*"
        page = 0
        fetched = 0
        is_unlimited = (limit is None or limit <= 0)

        if resume:
            checkpoint = checkpoint_mgr.load("openalex", query, start_year, end_year)
            if checkpoint:
                all_results = checkpoint.get("items", [])
                received_pages = checkpoint.get("received_pages", [])
                cursor = checkpoint.get("last_cursor", "*")
                page = checkpoint.get("last_page", 0)
                fetched = len(all_results)
                if checkpoint.get("is_complete") or (not is_unlimited and fetched >= limit):
                    logger.info(f"OpenAlex fetch fully restored from checkpoint ({fetched} items).")
                    return self._to_dataframe(all_results[:limit] if not is_unlimited else all_results)

        filters = []
        if start_year:
            filters.append(f"from_publication_date:{start_year}-01-01")
        if end_year:
            filters.append(f"to_publication_date:{end_year}-12-31")
            
        has_boolean = any(w in query.upper() for w in [" AND ", " OR ", " NOT "]) or '"' in query
            
        if has_boolean:
            filters.append(f"title_and_abstract.search:{query}")
            search_param = None
        else:
            import re
            clean_query = re.sub(r'[\(\)\*\"]', ' ', query)
            clean_query = re.sub(r'\b(AND|OR|NOT)\b', ' ', clean_query, flags=re.IGNORECASE)
            clean_query = re.sub(r'\s+', ' ', clean_query).strip()
            search_param = clean_query

        while True:
            if not is_unlimited and fetched >= limit:
                if resume:
                    checkpoint_mgr.save("openalex", query, all_results, start_year, end_year, page=page, cursor=cursor, received_pages=received_pages, is_complete=True)
                break
                
            current_per_page = per_page if is_unlimited else min(per_page, limit - fetched)
            params = {
                "per_page": current_per_page,
                "cursor": cursor,
                "select": "title,abstract_inverted_index,authorships,publication_year,doi,ids,keywords,concepts,cited_by_count,referenced_works",
            }
            if search_param:
                params["search"] = search_param
            if filters:
                params["filter"] = ",".join(filters)
                
            page += 1
            logger.info(f"Fetching batch from OpenAlex (Page {page}, Fetched: {fetched}{'/' + str(limit) if not is_unlimited else ''}, Cursor: {str(cursor)[:10]}...)")
            try:
                data = self._make_request(params)
                results = data.get("results", [])
                meta = data.get("meta", {})
                next_cursor = meta.get("next_cursor")

                if not results:
                    if resume:
                        checkpoint_mgr.save("openalex", query, all_results, start_year, end_year, page=page, cursor=cursor, received_pages=received_pages, is_complete=True)
                    break
                    
                all_results.extend(results)
                fetched += len(results)
                received_pages.append(page)

                is_end = (not next_cursor or next_cursor == cursor or len(results) < current_per_page)
                
                if resume:
                    checkpoint_mgr.save("openalex", query, all_results, start_year, end_year, page=page, cursor=next_cursor or cursor, received_pages=received_pages, is_complete=is_end)

                if is_end:
                    break
                    
                cursor = next_cursor
            except Exception as e:
                logger.error(f"Error fetching from OpenAlex (saved checkpoint at page {page}, items {len(all_results)}): {e}")
                break
                
        logger.info(f"OpenAlex fetch complete. Total papers retrieved: {len(all_results)}")
        return self._to_dataframe(all_results)

    def fetch_by_doi(self, doi: str) -> Optional[Dict]:
        """Fetches a single paper by DOI."""
        url = f"{self.BASE_URL}/doi:{doi}"
        try:
            # We don't need all params, just make a direct get
            @retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
                reraise=True
            )
            def _fetch():
                response = httpx.get(url, headers=self.headers, timeout=15.0)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
            return _fetch()
        except Exception as e:
            logger.error(f"Error fetching DOI {doi} from OpenAlex: {e}")
            return None

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
            

            referenced_works = res.get("referenced_works", [])

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
                "References": "; ".join(referenced_works),
                "Source": "OpenAlex"
            }
            rows.append(row)
        
        return pd.DataFrame(rows)
