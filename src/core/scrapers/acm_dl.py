import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging
import re

logger = logging.getLogger(__name__)

class ACMDirectScraper:
    """Direct scraper for ACM Digital Library search results.
    
    Extracts publication metadata from dl.acm.org.
    Not triggered by default in UnifiedCollector.
    """
    BASE_URL = "https://dl.acm.org/action/doSearch"

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        logger.info(f"Scraping ACM Digital Library for '{query}' (limit={limit})...")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        params = {
            "AllField": query,
            "pageSize": min(limit if limit > 0 else 50, 50),
            "startPage": 0
        }
        if start_year and end_year:
            params["AfterYear"] = start_year
            params["BeforeYear"] = end_year

        try:
            r = httpx.get(self.BASE_URL, params=params, headers=headers, timeout=20.0, follow_redirects=True)
            if r.status_code != 200:
                logger.warning(f"ACM DL scraper returned HTTP {r.status_code}. Access may be restricted or IP rate-limited.")
                return pd.DataFrame()
            
            return self._parse_html(r.text)
        except Exception as e:
            logger.error(f"Error executing ACM Direct Scraper: {e}")
            return pd.DataFrame()

    def _parse_html(self, html_content: str) -> pd.DataFrame:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("BeautifulSoup4 not installed. Run `pip install beautifulsoup4` to use ACMDirectScraper.")
            return pd.DataFrame()

        soup = BeautifulSoup(html_content, "html.parser")
        items = soup.find_all("li", class_="search__item")
        parsed = []

        for item in items:
            title_el = item.find("h5", class_="issue-item__title")
            title = title_el.get_text(strip=True) if title_el else ""

            authors_el = item.find_all("span", class_="hlFld-Author")
            authors = [a.get_text(strip=True) for a in authors_el]

            doi_el = item.find("a", class_="issue-item__doi")
            doi = doi_el.get_text(strip=True) if doi_el else ""

            date_el = item.find("span", class_="issue-item__detail")
            year = None
            if date_el:
                m = re.search(r'\b(19|20)\d{2}\b', date_el.get_text())
                if m:
                    year = int(m.group(0))

            if title:
                parsed.append({
                    "Title": title,
                    "Abstract": "",
                    "Authors": "; ".join(authors),
                    "Year": year,
                    "Affiliations": "ACM",
                    "DOI": doi,
                    "EID": doi,
                    "Author Keywords": "",
                    "Cite Count": 0,
                    "Source": "ACM Digital Library Direct"
                })

        return pd.DataFrame(parsed)
