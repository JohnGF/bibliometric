import httpx
import pandas as pd
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import logging
import re

logger = logging.getLogger(__name__)

class ArXivCollector:
    """Collector for arXiv preprints."""
    API_URL = "https://export.arxiv.org/api/query"

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        """Fetches preprints from arXiv matching search query and year range."""
        clean_query = re.sub(r'[\(\)\*\"]', ' ', query)
        clean_query = re.sub(r'\b(AND|OR|NOT)\b', ' ', clean_query, flags=re.IGNORECASE)
        clean_query = re.sub(r'\s+', '+', clean_query).strip('+')

        all_results = []
        max_results = min(limit if (limit and limit > 0) else 500, 200)
        start = 0

        logger.info(f"Fetching preprints from arXiv for query: {clean_query}...")
        while True:
            params = {
                "search_query": f"all:{clean_query}",
                "start": start,
                "max_results": max_results
            }
            try:
                r = httpx.get(self.API_URL, params=params, timeout=30.0)
                r.raise_for_status()
                entries = self._parse_atom_xml(r.text, start_year, end_year)
                if not entries:
                    break
                all_results.extend(entries)
                start += len(entries)

                if limit > 0 and len(all_results) >= limit:
                    break
                if len(entries) < max_results:
                    break
            except Exception as e:
                logger.error(f"Error fetching from arXiv: {e}")
                break

        return self._to_dataframe(all_results)

    def _parse_atom_xml(self, xml_content: str, start_year: Optional[int], end_year: Optional[int]) -> List[Dict]:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml_content)
        entries = []

        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
            summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")
            published = entry.findtext("atom:published", "", ns)
            year = int(published[:4]) if published and len(published) >= 4 else None

            if start_year and year and year < start_year:
                continue
            if end_year and year and year > end_year:
                continue

            authors = [a.findtext("atom:name", "", ns) for a in entry.findall("atom:author", ns)]
            doi_elem = entry.find("atom:doi", ns)
            doi = doi_elem.text if doi_elem is not None else ""

            entries.append({
                "Title": title,
                "Abstract": summary,
                "Authors": "; ".join(authors),
                "Year": year,
                "Source title": "arXiv Preprint",
                "DOI": doi,
                "Cite Count": 0,
                "Source": "arXiv (Preprint)"
            })
        return entries

    def _to_dataframe(self, results: List[Dict]) -> pd.DataFrame:
        return pd.DataFrame(results) if results else pd.DataFrame()
