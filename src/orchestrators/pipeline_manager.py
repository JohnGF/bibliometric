import logging
import os
from typing import Optional
from src.orchestrators.data_orchestrator import DataOrchestrator
from src.orchestrators.analysis_orchestrator import AnalysisOrchestrator
from src.core.latex_exporter import LaTeXExporter

# Auto-load .env if present
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                if key.strip() not in os.environ:
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class PipelineManager:
    """High-level manager coordinating the Data, Analysis, and Export orchestrators."""

    def __init__(self, output_dir: str = "pipeline_results", config: Optional[dict] = None):
        self.output_dir = output_dir
        self.config = config or {}

        self.data_orch = DataOrchestrator(self.config)
        self.analysis_orch = AnalysisOrchestrator(self.output_dir, self.config)

    def run_with_query(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None):
        """Fetches data and runs the pipeline."""
        papers_path = self.data_orch.collect_data(query, limit, start_year, end_year)
        if papers_path:
            return self.run(papers_path)

    def run(self, papers_path: str, refs_path: Optional[str] = None):
        """Runs the pipeline on an existing file."""
        logger.info(f"PipelineManager: Starting pipeline for {papers_path}")

        # 1. Data Ingestion
        df_pd = self.data_orch.load_and_validate_data(papers_path)
        if df_pd is None or df_pd.empty:
            logger.error("Data validation/screening failed or dataset is empty. Aborting.")
            return

        # 2. Routing based on dataset type
        is_references_dataset = "source" in df_pd.columns and "destination" in df_pd.columns
        if is_references_dataset:
            self.analysis_orch.analyze_references_dataset(df_pd)
            return

        # 3. Main Analysis Pipeline
        self.analysis_orch.run_analysis(df_pd, refs_path)

        # 4. Export stage
        try:
            exporter = LaTeXExporter(self.output_dir)
            exporter.export_all()
        except Exception as e:
            logger.warning(f"Could not export LaTeX templates: {e}")

        logger.info(f"Pipeline complete. All results saved to {self.output_dir}")
