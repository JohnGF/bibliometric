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

    def calculate_country_cagr(self, evolution_df: pd.DataFrame, min_total_papers: int = 10) -> pd.DataFrame:
        """
        Computes total publication count and CAGR growth rate (%) for each country.
        """
        if evolution_df.empty or "Country" not in evolution_df.columns:
            return pd.DataFrame()

        records = []
        grouped = evolution_df.groupby("Country")
        
        for country, group in grouped:
            total_count = group["Count"].sum()
            if total_count < min_total_papers:
                continue
                
            sorted_g = group.sort_values("Year")
            first_row = sorted_g.iloc[0]
            last_row = sorted_g.iloc[-1]
            
            y_start = int(first_row["Year"])
            y_end = int(last_row["Year"])
            c_start = int(first_row["Count"])
            c_end = int(last_row["Count"])
            
            y_diff = y_end - y_start
            if y_diff > 0 and c_start > 0:
                cagr = ((c_end / c_start) ** (1.0 / y_diff) - 1.0) * 100.0
            else:
                cagr = 0.0
                
            trend = "Surging" if cagr > 15 else ("Emerging" if cagr > 5 else "Established")
            
            records.append({
                "Country": country,
                "Total_Count": total_count,
                "First_Year": y_start,
                "First_Year_Count": c_start,
                "Last_Year": y_end,
                "Last_Year_Count": c_end,
                "CAGR_percent": cagr,
                "Trend": trend
            })
            
        res_df = pd.DataFrame(records)
        if not res_df.empty:
            res_df = res_df.sort_values("Total_Count", ascending=False).reset_index(drop=True)
        return res_df
