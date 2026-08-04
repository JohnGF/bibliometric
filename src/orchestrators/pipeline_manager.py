import logging
import os
import subprocess
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
        print(f"\n>>> [PIPELINE INITIALIZATION] Starting autonomous collection for query: '{query}' ({start_year}-{end_year})...")
        papers_path = self.data_orch.collect_data(query, limit, start_year, end_year)
        if papers_path:
            return self.run(papers_path)

    def run(self, papers_path: str, refs_path: Optional[str] = None):
        """Runs the pipeline on an existing file."""
        print(f"\n>>> [PIPELINE START] Running pipeline for dataset: '{papers_path}'")
        logger.info(f"PipelineManager: Starting pipeline for {papers_path}")

        # 1. Data Ingestion
        print(">>> [STAGE 1] Ingesting and validating input dataset...")
        df_pd = self.data_orch.load_and_validate_data(papers_path)
        if df_pd is None or df_pd.empty:
            print(">>> [ERROR] Data validation/screening failed or dataset is empty. Aborting.")
            logger.error("Data validation/screening failed or dataset is empty. Aborting.")
            return

        # Save active dataset to output directory for exporters
        df_pd.to_csv(os.path.join(self.output_dir, "publication_dataset.csv"), index=False)

        # 2. Routing based on dataset type
        is_references_dataset = "source" in df_pd.columns and "destination" in df_pd.columns
        if is_references_dataset:
            print(">>> [STAGE 2] Routing to dedicated references dataset analysis...")
            self.analysis_orch.analyze_references_dataset(df_pd)
            return

        # 3. Main Analysis Pipeline
        print(">>> [STAGE 3] Running main analytical pipeline...")
        self.analysis_orch.run_analysis(df_pd, refs_path)

        # 4. Export stage
        print("\n>>> [STAGE 4] Exporting LaTeX table and manuscript templates...")
        try:
            exporter = LaTeXExporter(self.output_dir)
            exporter.export_all(force=True)
            print(">>> LaTeX templates exported successfully.")
        except Exception as e:
            print(f">>> [WARNING] Could not export LaTeX templates: {e}")
            logger.warning(f"Could not export LaTeX templates: {e}")

        # 5. Compile the IEEEtran scaffold into the final PDF document
        self._compile_pdf()

        print(f"\n>>> [PIPELINE COMPLETE] All results, figures, tables, and manuscript PDF saved to: {self.output_dir}")
        logger.info(f"Pipeline complete. All results saved to {self.output_dir}")

    def _compile_pdf(self):
        scaffold_tex = os.path.join(self.output_dir, "paper_scaffold.tex")
        onecol_tex = os.path.join(self.output_dir, "paper_scaffold_onecolumn.tex")
        
        if not os.path.exists(scaffold_tex):
            print(">>> [WARNING] paper_scaffold.tex not found; skipping PDF compilation.")
            logger.warning("paper_scaffold.tex not found; skipping PDF compilation.")
            return
        
        print("\n>>> [STAGE 5] Compiling IEEEtran paper scaffolds to PDF via pdflatex...")
        try:
            print(">>> Compiling 2-column layout (paper_scaffold.tex)...")
            print("  * Pass 1 (generating aux and log files)...")
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "paper_scaffold.tex"],
                cwd=self.output_dir, check=False,
            )
            print("  * Pass 2 (resolving cross-references and margins)...")
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "paper_scaffold.tex"],
                cwd=self.output_dir, check=False,
            )
            pdf_path = os.path.join(self.output_dir, "paper_scaffold.pdf")
            if os.path.exists(pdf_path):
                print(f">>> [SUCCESS] 2-column PDF generated: {pdf_path}")
                logger.info(f"PDF compilation complete -> {pdf_path}")
            else:
                print(">>> [WARNING] 2-column PDF file not found after pdflatex compilation finished.")
                logger.warning("PDF file not found after compilation.")

            if os.path.exists(onecol_tex):
                print(">>> Compiling 1-column layout (paper_scaffold_onecolumn.tex)...")
                print("  * Pass 1 (generating aux and log files)...")
                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "paper_scaffold_onecolumn.tex"],
                    cwd=self.output_dir, check=False,
                )
                print("  * Pass 2 (resolving cross-references and margins)...")
                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "paper_scaffold_onecolumn.tex"],
                    cwd=self.output_dir, check=False,
                )
                onecol_pdf_path = os.path.join(self.output_dir, "paper_scaffold_onecolumn.pdf")
                if os.path.exists(onecol_pdf_path):
                    print(f">>> [SUCCESS] 1-column PDF generated: {onecol_pdf_path}")
                    logger.info(f"PDF compilation complete -> {onecol_pdf_path}")
                else:
                    print(">>> [WARNING] 1-column PDF file not found after pdflatex compilation finished.")
                    logger.warning("1-column PDF file not found after compilation.")
        except Exception as e:
            print(f">>> [ERROR] PDF compilation failed: {e}")
            logger.warning(f"PDF compilation error: {e}")


