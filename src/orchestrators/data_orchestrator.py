import logging
import os
import pandas as pd
from typing import Optional

from src.core.collection import UnifiedCollector
from src.core.ingestion import load_data, validate_publications
from src.core.screening import PaperScreener

logger = logging.getLogger(__name__)

class DataOrchestrator:
    """Handles data collection, screening, ingestion, and validation."""

    def __init__(self, config: dict):
        self.config = config
        self.collector = UnifiedCollector(config=self.config)

        use_screen_emb = self.config.get("screen_embeddings", False)
        use_screen_llm = self.config.get("screen_llm", False)
        emb_threshold = self.config.get("embedding_threshold", 0.35)
        llm_model = self.config.get("llm_model", "llama3.2:3b")

        if use_screen_emb or use_screen_llm:
            self.screener = PaperScreener(
                use_embedding_filter=use_screen_emb,
                embedding_threshold=emb_threshold,
                use_llm_categorization=use_screen_llm,
                llm_model=llm_model
            )
        else:
            self.screener = None

    def collect_data(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None) -> Optional[str]:
        """Fetches data, screens it, and saves it to a file. Returns the file path."""
        logger.info(f"Starting autonomous collection for query: {query} (Years: {start_year}-{end_year})")
        df_pd = self.collector.fetch_all(query, limit_per_source=limit, start_year=start_year, end_year=end_year)

        if df_pd.empty:
            logger.error("No data found for the given query.")
            return None

        if self.screener:
            logger.info("Applying automated paper screening...")
            df_pd = self.screener.screen(df_pd)
            if df_pd.empty:
                logger.error("No papers retained after screening.")
                return None

        data_dir = "data"
        os.makedirs(data_dir, exist_ok=True)
        import re
        safe_query = re.sub(r'[^a-zA-Z0-9_\-]', '_', query)
        safe_query = re.sub(r'_+', '_', safe_query)[:50].strip('_')
        papers_path = os.path.join(data_dir, f"collected_{safe_query}.csv")
        df_pd.to_csv(papers_path, index=False)
        logger.info(f"Data saved to {papers_path}")

        return papers_path

    def load_and_validate_data(self, papers_path: str) -> Optional[pd.DataFrame]:
        """Loads data from file, applies screening if needed, and validates."""
        logger.info(f"Loading data from {papers_path}")
        df_pd = load_data(papers_path)

        if self.screener:
            logger.info("Applying automated paper screening on input file...")
            df_pd = self.screener.screen(df_pd)
            if df_pd.empty:
                logger.error("No papers retained after screening.")
                return None

        # Basic check to see if it's a refs dataset
        is_references_dataset = "source" in df_pd.columns and "destination" in df_pd.columns
        if not is_references_dataset:
            validate_publications(df_pd)

        return df_pd
