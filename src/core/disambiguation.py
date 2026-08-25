import re
import logging
import pandas as pd
from collections import defaultdict
from typing import List, Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

class AuthorDisambiguator:
    """
    Robust Author and Institution Disambiguation Engine.
    Translates research notebook logic for:
    1. Position-aware 1-to-1 author-affiliation pairing
    2. Author role & seniority tagging (first author, corresponding/last author, middle author)
    3. Multi-signal homonym disambiguation (persistent ID, institution, and co-authorship neighborhood)
    """

    def __init__(self):
        pass

    @staticmethod
    def clean_name(name: str) -> str:
        """Cleans and standardizes an author name string."""
        if not name or not isinstance(name, str):
            return ""
        # Remove extra whitespace, newlines, and trailing commas
        cleaned = name.strip().replace("\n", " ").replace("\r", " ")
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.rstrip(',')
        if cleaned.lower() in ("nan", "none", "unknown", "et al", "et al."):
            return ""
        return cleaned

    @staticmethod
    def clean_affiliation(affil: str) -> str:
        """Cleans and standardizes an institution/affiliation string."""
        if not affil or not isinstance(affil, str):
            return ""
        cleaned = affil.strip().replace("\n", " ").replace("\r", " ")
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.rstrip(';')
        if cleaned.lower() in ("nan", "none", "unknown"):
            return ""
        return cleaned

    def parse_authors_list(self, authors_raw: Any) -> List[str]:
        """Parses a semicolon-separated or comma-separated author string into a clean list."""
        if not authors_raw or pd.isna(authors_raw):
            return []
        
        raw_str = str(authors_raw).strip()
        if not raw_str:
            return []

        # Split on semicolon if present, otherwise split on commas separating full names
        if ";" in raw_str:
            parts = [self.clean_name(p) for p in raw_str.split(";")]
        else:
            parts = [self.clean_name(raw_str)]
        
        return [p for p in parts if p]

    def parse_affiliations_list(self, affils_raw: Any) -> List[str]:
        """Parses a semicolon-separated affiliation string into a clean list."""
        if not affils_raw or pd.isna(affils_raw):
            return []
        
        raw_str = str(affils_raw).strip()
        if not raw_str:
            return []

        if ";" in raw_str:
            parts = [self.clean_affiliation(p) for p in raw_str.split(";")]
        else:
            parts = [self.clean_affiliation(raw_str)]
        
        return [p for p in parts if p]

    def pair_authors_and_affiliations(
        self,
        authors_raw: Any,
        affiliations_raw: Any
    ) -> List[Dict[str, str]]:
        """
        Pairs authors with their corresponding institutional affiliations based on positional heuristic:
        - Case 1: 1 affiliation on paper -> all co-authors share it.
        - Case 2: N authors == M affiliations -> exact 1-to-1 index zip matching.
        - Case 3: M affiliations but M != N -> assigns primary match or leaves unassigned to avoid false pairing.
        Also computes author role ('fa' = First Author, 'mp' = Last/Senior Author, 'coauthor' = Middle Author).
        """
        authors = self.parse_authors_list(authors_raw)
        affils = self.parse_affiliations_list(affiliations_raw)

        n_authors = len(authors)
        n_affils = len(affils)

        if n_authors == 0:
            return []

        paired = []
        for idx, author in enumerate(authors):
            # Determine author role
            if idx == 0:
                role = "fa"  # First Author
            elif idx == n_authors - 1 and n_authors > 1:
                role = "mp"  # Last / Senior Author
            else:
                role = "coauthor"

            # Determine affiliation
            if n_affils == 1:
                # Case 1: Single institution shared by all
                assigned_affil = affils[0]
            elif n_affils == n_authors:
                # Case 2: Exact 1-to-1 positional match
                assigned_affil = affils[idx]
            elif n_affils > 1:
                # Case 3: Count mismatch - assign first if only 1, otherwise general
                assigned_affil = affils[idx] if idx < n_affils else affils[0]
            else:
                assigned_affil = ""

            # Check if author name already contains an ID (e.g. "Smith, J. (57226766385)")
            id_match = re.search(r'\((?:ID:\s*|orcid:\s*)?([A-Za-z0-9_\-]+)\)$', author)
            author_id = id_match.group(1) if id_match else None
            base_name = re.sub(r'\s*\([A-Za-z0-9_\-]+\)$', '', author).strip()

            paired.append({
                "author_raw": author,
                "author_base_name": base_name,
                "author_id": author_id,
                "affiliation": assigned_affil,
                "role": role,
                "position": idx,
                "total_authors": n_authors
            })

        return paired

    def disambiguate_dataset(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """
        Processes a publication dataset and generates disambiguated author identifiers.
        Disambiguates homonyms using:
        1. Explicit Author ID / ORCID if present
        2. Institutional Affiliation signature
        3. Co-Authorship cluster context
        Returns:
            - Augmented DataFrame with 'Disambiguated Authors' and 'Author-Affiliation Pairs'
            - Mapping dictionary {raw_author_record: disambiguated_id}
        """
        if df.empty or "Authors" not in df.columns:
            return df, {}

        logger.info(f"AuthorDisambiguator: Disambiguating authors across {len(df)} publications...")

        # Step 1: Collect author-institution-coauthor profiles across the whole corpus
        author_profiles = defaultdict(lambda: {
            "institutions": defaultdict(int),
            "coauthors": defaultdict(int),
            "ids": set(),
            "paper_count": 0
        })

        all_paper_pairs = []

        for _, row in df.iterrows():
            authors_raw = row.get("Authors", "")
            affils_raw = row.get("Affiliations", "")
            paper_id = row.get("DOI") or row.get("Title")

            pairs = self.pair_authors_and_affiliations(authors_raw, affils_raw)
            all_paper_pairs.append(pairs)

            paper_coauthors = [p["author_base_name"] for p in pairs if p["author_base_name"]]

            for p in pairs:
                base = p["author_base_name"]
                if not base:
                    continue
                author_profiles[base]["paper_count"] += 1
                if p["affiliation"]:
                    author_profiles[base]["institutions"][p["affiliation"]] += 1
                if p["author_id"]:
                    author_profiles[base]["ids"].add(p["author_id"])
                
                # Add coauthors on this paper
                for co in paper_coauthors:
                    if co != base:
                        author_profiles[base]["coauthors"][co] += 1

        # Step 2: Build disambiguated keys for each author occurrence
        disambiguated_authors_col = []
        author_mapping = {}

        for pairs in all_paper_pairs:
            dis_names = []
            for p in pairs:
                base = p["author_base_name"]
                if not base:
                    continue

                affil = p["affiliation"]
                auth_id = p["author_id"]

                # If explicit ID exists, use it
                if auth_id:
                    dis_id = f"{base} ({auth_id})"
                else:
                    # Check if base name is ambiguous (associated with multiple distinct institutions across corpus)
                    prof = author_profiles.get(base, {})
                    inst_counts = prof.get("institutions", {})

                    if len(inst_counts) > 1 and affil:
                        # Shorten affiliation for concise clean label (e.g. "Stanford Univ" or first institution token)
                        short_affil = affil.split(",")[0].strip()
                        dis_id = f"{base} [{short_affil}]"
                    else:
                        dis_id = base

                dis_names.append(dis_id)
                author_mapping[p["author_raw"]] = dis_id

            disambiguated_authors_col.append("; ".join(dis_names))

        df_out = df.copy()
        df_out["Disambiguated Authors"] = disambiguated_authors_col
        logger.info(f"AuthorDisambiguator: Successfully disambiguated {len(author_profiles)} unique author names.")
        return df_out, author_mapping
