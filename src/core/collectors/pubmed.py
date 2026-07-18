import xml.etree.ElementTree as ET
import httpx
import pandas as pd
from typing import List, Dict, Optional
import logging
import re

logger = logging.getLogger(__name__)

class PubMedCollector:
    SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def fetch_papers(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        """Fetches papers from PubMed matching the search query and year range."""
        term = query
        if start_year and end_year:
            term += f" AND ({start_year}[DP] : {end_year}[DP])"
        elif start_year:
            term += f" AND {start_year}:3000[DP]"
        elif end_year:
            term += f" AND 1800:{end_year}[DP]"

        search_params = {
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": limit,
        }
        if self.api_key:
            search_params["api_key"] = self.api_key

        logger.info(f"Searching PubMed for term: {term} (limit={limit})")
        try:
            response = httpx.get(self.SEARCH_URL, params=search_params, timeout=30.0)
            response.raise_for_status()
            search_data = response.json()
            pmids = search_data.get("esearchresult", {}).get("idlist", [])
            if not pmids:
                logger.info("No PMIDs returned from PubMed search.")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error searching PubMed: {e}")
            return pd.DataFrame()

        all_rows = []
        batch_size = 100
        for i in range(0, len(pmids), batch_size):
            batch_ids = pmids[i:i+batch_size]
            fetch_params = {
                "db": "pubmed",
                "id": ",".join(batch_ids),
                "retmode": "xml",
            }
            if self.api_key:
                fetch_params["api_key"] = self.api_key

            logger.info(f"Fetching PubMed details for batch {i//batch_size + 1} (PMIDs: {len(batch_ids)})")
            try:
                response = httpx.get(self.FETCH_URL, params=fetch_params, timeout=40.0)
                response.raise_for_status()
                rows = self._parse_xml(response.content)
                all_rows.extend(rows)
            except Exception as e:
                logger.error(f"Error fetching batch details from PubMed: {e}")
                continue

        return pd.DataFrame(all_rows)

    def _parse_xml(self, xml_content: bytes) -> List[Dict]:
        rows = []
        try:
            root = ET.fromstring(xml_content)
        except Exception as e:
            logger.error(f"Failed to parse XML string from PubMed: {e}")
            return rows

        for article in root.findall(".//PubmedArticle"):
            pmid = ""
            pmid_el = article.find(".//PMID")
            if pmid_el is not None:
                pmid = pmid_el.text or ""

            title = ""
            title_el = article.find(".//ArticleTitle")
            if title_el is not None:
                title = "".join(title_el.itertext()).strip()

            abstract = ""
            abstract_texts = article.findall(".//AbstractText")
            if abstract_texts:
                parts = []
                for label_el in abstract_texts:
                    label = label_el.get("Label")
                    text = "".join(label_el.itertext()).strip()
                    if label:
                        parts.append(f"{label}: {text}")
                    else:
                        parts.append(text)
                abstract = " ".join(parts).strip()

            authors = []
            author_els = article.findall(".//AuthorList/Author")
            for auth in author_els:
                last_name = auth.find("LastName")
                fore_name = auth.find("ForeName")
                last_str = last_name.text if last_name is not None and last_name.text else ""
                fore_str = fore_name.text if fore_name is not None and fore_name.text else ""
                full_name = f"{fore_str} {last_str}".strip()
                if full_name:
                    authors.append(full_name)
            authors_str = "; ".join(authors)

            affiliations = []
            affil_els = article.findall(".//AffiliationInfo/Affiliation")
            for aff in affil_els:
                aff_text = "".join(aff.itertext()).strip()
                if aff_text and aff_text not in affiliations:
                    affiliations.append(aff_text)
            affil_str = "; ".join(affiliations)

            year = None
            pub_date = article.find(".//JournalIssue/PubDate")
            if pub_date is not None:
                year_el = pub_date.find("Year")
                if year_el is not None and year_el.text:
                    try:
                        year = int(year_el.text.strip())
                    except ValueError:
                        pass
                else:
                    medline_el = pub_date.find("MedlineDate")
                    if medline_el is not None and medline_el.text:
                        match = re.search(r'\b(19|20)\d{2}\b', medline_el.text)
                        if match:
                            year = int(match.group(0))

            doi = ""
            article_ids = article.findall(".//ArticleIdList/ArticleId")
            for aid in article_ids:
                if aid.get("IdType") == "doi":
                    doi = aid.text or ""
                    break

            keywords = []
            keyword_els = article.findall(".//KeywordList/Keyword")
            for kw in keyword_els:
                kw_text = "".join(kw.itertext()).strip()
                if kw_text:
                    keywords.append(kw_text)
            keywords_str = "; ".join(keywords)

            rows.append({
                "Title": title if title else None,
                "Abstract": abstract,
                "Authors": authors_str,
                "Year": year,
                "Affiliations": affil_str,
                "DOI": doi if doi else None,
                "EID": f"PMID:{pmid}" if pmid else None,
                "Author Keywords": keywords_str,
                "Cite Count": 0,
                "Source": "PubMed"
            })
        return rows
