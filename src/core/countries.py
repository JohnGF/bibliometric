import polars as pl
import pandas as pd
from typing import Tuple
import logging
from src.core.ingestion import extract_countries

logger = logging.getLogger(__name__)

class CountryAnalysis:
    def __init__(self):
        pass

    def process_countries(self, df: pl.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Processes a publication DataFrame, extracts countries from affiliations,
        and computes country evolution statistics over the years.
        
        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: 
                - exploded_publications: DataFrame with Title, Year, Country
                - country_evolution: DataFrame with Year, Country, Count
        """
        logger.info("Extracting country affiliation data...")
        df_dicts = df.to_dicts()
        records = []
        
        for row in df_dicts:
            year = row.get("Year")
            affil = row.get("Affiliations")
            title = row.get("Title")
            
            if not affil or year is None:
                continue
                
            try:
                year_val = int(year)
            except (ValueError, TypeError):
                continue
            
            countries = extract_countries(str(affil))
            if not countries:
                continue
                
            for country in countries:
                records.append({
                    "Title": title,
                    "Year": year_val,
                    "Country": country
                })
                
        if not records:
            logger.warning("No country affiliations extracted.")
            return pd.DataFrame(), pd.DataFrame()
            
        exploded_pl = pl.DataFrame(records)
        
        # Calculate yearly country frequency
        evolution_pl = exploded_pl.group_by(["Year", "Country"]).len().sort(["Year", "Country"])
        evolution_pl = evolution_pl.rename({"len": "Count"})
        
        logger.info(f"Extracted {len(records)} country affiliation records across {evolution_pl['Country'].n_unique()} unique countries.")
        return exploded_pl.to_pandas(), evolution_pl.to_pandas()
