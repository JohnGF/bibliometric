import pandas as pd
from typing import List, Optional, Dict
import logging
import os
from src.core.collectors.openalex import OpenAlexCollector
from src.core.collectors.semantic_scholar import SemanticScholarCollector
from src.core.collectors.crossref import CrossrefCollector

logger = logging.getLogger(__name__)

class UnifiedCollector:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Priority: passed config > environment variables
        oa_email = self.config.get("openalex_email") or os.environ.get("OPENALEX_EMAIL")
        ss_key = self.config.get("ss_api_key") or os.environ.get("SS_API_KEY")
        cr_email = self.config.get("crossref_email") or os.environ.get("CROSSREF_EMAIL") or oa_email
        
        self.collectors = {
            "openalex": OpenAlexCollector(email=oa_email),
            "semantic_scholar": SemanticScholarCollector(api_key=ss_key),
            "crossref": CrossrefCollector(email=cr_email)
        }

    def fetch_all(self, query: str, limit_per_source: int = 100, sources: Optional[List[str]] = None, 
                  start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        """Fetches and merges data from multiple sources."""
        all_dfs = []
        target_sources = sources or list(self.collectors.keys())

        for source in target_sources:
            if source in self.collectors:
                df = self.collectors[source].fetch_papers(
                    query, limit=limit_per_source, start_year=start_year, end_year=end_year
                )
                if not df.empty:
                    all_dfs.append(df)
            else:
                logger.warning(f"Source {source} not recognized.")

        if not all_dfs:
            return pd.DataFrame()

        merged_df = pd.concat(all_dfs, ignore_index=True)
        
        # Normalize DOIs and Titles for grouping
        def normalize_doi(doi):
            if pd.isna(doi) or not isinstance(doi, str):
                return ""
            # Strip URL prefixes if present
            doi = doi.lower().strip()
            for prefix in ["https://doi.org/", "http://doi.org/", "doi.org/"]:
                if doi.startswith(prefix):
                    doi = doi[len(prefix):]
            return doi

        def normalize_title(title):
            if pd.isna(title) or not isinstance(title, str):
                return ""
            # Keep only alphanumeric characters and convert to lowercase
            import re
            return re.sub(r'[^a-z0-9]', '', title.lower())

        merged_df["normalized_doi"] = merged_df["DOI"].apply(normalize_doi)
        merged_df["normalized_title"] = merged_df["Title"].apply(normalize_title)

        # Merge matching rows
        def merge_group(group: pd.DataFrame) -> pd.Series:
            # Initialize merged row with the first row
            merged = group.iloc[0].copy()
            for idx in range(1, len(group)):
                row = group.iloc[idx]
                for col in group.columns:
                    val = row[col]
                    curr = merged[col]
                    
                    is_curr_empty = pd.isna(curr) or curr == "" or curr is None or (isinstance(curr, list) and not curr)
                    is_val_present = not pd.isna(val) and val != "" and val is not None and not (isinstance(val, list) and not val)
                    
                    if is_curr_empty and is_val_present:
                        merged[col] = val
                    elif col == "Cite Count" and is_val_present:
                        # Keep max citation count
                        merged[col] = max(int(curr or 0), int(val or 0))
                    elif col == "Source" and is_val_present:
                        # Collect all sources
                        if val not in str(curr):
                            merged[col] = f"{curr}, {val}"
                    elif col == "Author Keywords" and is_val_present and curr != val:
                        # Combine keywords
                        kws = set(filter(None, [k.strip() for k in str(curr).split(";") if k.strip()]))
                        new_kws = [k.strip() for k in str(val).split(";") if k.strip()]
                        for kw in new_kws:
                            kws.add(kw)
                        merged[col] = "; ".join(sorted(kws))
            return merged

        # Assign group IDs based on normalized DOI or Title
        group_ids = {}
        current_group_id = 0
        doi_to_gid = {}
        title_to_gid = {}
        
        row_gids = []
        for _, row in merged_df.iterrows():
            doi = row["normalized_doi"]
            title = row["normalized_title"]
            
            gid = None
            if doi and doi in doi_to_gid:
                gid = doi_to_gid[doi]
            elif title and title in title_to_gid:
                gid = title_to_gid[title]
                
            if gid is None:
                gid = current_group_id
                current_group_id += 1
                
            if doi:
                doi_to_gid[doi] = gid
            if title:
                title_to_gid[title] = gid
                
            row_gids.append(gid)
            
        merged_df["group_id"] = row_gids
        
        # Group by group_id and merge each group
        deduplicated_rows = []
        for _, group in merged_df.groupby("group_id"):
            if len(group) == 1:
                deduplicated_rows.append(group.iloc[0])
            else:
                deduplicated_rows.append(merge_group(group))
                
        deduplicated_df = pd.DataFrame(deduplicated_rows)
        deduplicated_df = deduplicated_df.drop(columns=["normalized_doi", "normalized_title", "group_id"])
        
        # Cross-Source DOI Enrichment
        self._enrich_missing_metadata(deduplicated_df)

        logger.info(f"Unified collection complete. Total unique papers: {len(deduplicated_df)}")
        return deduplicated_df.reset_index(drop=True)

    def _enrich_missing_metadata(self, df: pd.DataFrame):
        """Fetches missing Abstract or Author Keywords by querying OpenAlex via DOI."""
        if df.empty or "openalex" not in self.collectors:
            return

        oa_collector = self.collectors["openalex"]
        enriched_count = 0

        for idx, row in df.iterrows():
            doi = row.get("DOI")
            has_abstract = not pd.isna(row.get("Abstract")) and str(row.get("Abstract")).strip()
            has_keywords = not pd.isna(row.get("Author Keywords")) and str(row.get("Author Keywords")).strip()

            if doi and (not has_abstract or not has_keywords):
                # Clean DOI
                clean_doi = str(doi).strip().lower()
                for prefix in ["https://doi.org/", "http://doi.org/", "doi.org/"]:
                    if clean_doi.startswith(prefix):
                        clean_doi = clean_doi[len(prefix):]

                try:
                    oa_data = oa_collector.fetch_by_doi(clean_doi)
                    if oa_data:
                        changed = False

                        if not has_abstract and oa_data.get("abstract_inverted_index"):
                            abstract = oa_collector._reconstruct_abstract(oa_data["abstract_inverted_index"])
                            if abstract:
                                df.at[idx, "Abstract"] = abstract
                                changed = True

                        if not has_keywords and oa_data.get("keywords"):
                            keywords = [k.get("display_name", "") for k in oa_data.get("keywords", [])]
                            keywords_str = "; ".join(filter(None, keywords))
                            if keywords_str:
                                df.at[idx, "Author Keywords"] = keywords_str
                                changed = True

                        if changed:
                            enriched_count += 1
                except Exception as e:
                    logger.debug(f"Failed to enrich DOI {clean_doi}: {e}")

        if enriched_count > 0:
            logger.info(f"Enriched {enriched_count} papers with missing metadata via OpenAlex DOI lookup.")
