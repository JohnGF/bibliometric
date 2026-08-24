import logging
import os
import time
import json
import subprocess
from typing import Optional, Dict
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

class PipelineProfiler:
    """Tracks execution time and percentage breakdown across all pipeline stages."""

    def __init__(self):
        self.start_total_time = time.perf_counter()
        self.stages: Dict[str, float] = {}
        self._active_timers: Dict[str, float] = {}

    def start(self, stage_name: str):
        self._active_timers[stage_name] = time.perf_counter()

    def stop(self, stage_name: str):
        if stage_name in self._active_timers:
            elapsed = time.perf_counter() - self._active_timers.pop(stage_name)
            self.stages[stage_name] = self.stages.get(stage_name, 0.0) + elapsed

    def print_summary(self, output_dir: Optional[str] = None):
        total_time = time.perf_counter() - self.start_total_time
        if total_time <= 0:
            total_time = 0.001

        lines = [
            "\n" + "=" * 70,
            f"=== PIPELINE EXECUTION PROFILE (Total: {total_time:.2f}s / {total_time/60:.2f} min) ===",
            "=" * 70,
            f"{'Stage / Component':<45} | {'Duration (s)':>12} | {'Share (%)':>9}",
            "-" * 70,
        ]

        for stage, dur in self.stages.items():
            pct = (dur / total_time) * 100.0
            lines.append(f"{stage:<45} | {dur:>11.2f}s | {pct:>8.1f}%")

        lines.append("=" * 70 + "\n")
        summary_str = "\n".join(lines)
        print(summary_str)

        if output_dir:
            profile_data = {
                "total_duration_seconds": total_time,
                "stages": {k: {"seconds": v, "percentage": (v / total_time) * 100.0} for k, v in self.stages.items()}
            }
            try:
                profile_path = os.path.join(output_dir, "pipeline_timing_profile.json")
                with open(profile_path, "w") as f:
                    json.dump(profile_data, f, indent=4)
            except Exception:
                pass


class PipelineManager:
    """High-level manager coordinating the Data, Analysis, and Export orchestrators."""

    def __init__(self, output_dir: str = "pipeline_results", config: Optional[dict] = None):
        self.output_dir = output_dir
        self.config = config or {}
        self.profiler = PipelineProfiler()

        self.data_orch = DataOrchestrator(self.config)
        self.analysis_orch = AnalysisOrchestrator(self.output_dir, self.config)

    def run_with_query(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None):
        """Fetches data and runs the pipeline."""
        print(f"\n>>> [PIPELINE INITIALIZATION] Starting autonomous collection for query: '{query}' ({start_year}-{end_year})...")
        self.profiler.start("1. Data Collection (APIs)")
        papers_path = self.data_orch.collect_data(query, limit, start_year, end_year)
        self.profiler.stop("1. Data Collection (APIs)")
        if papers_path:
            return self.run(papers_path)

    def run(self, papers_path: str, refs_path: Optional[str] = None):
        """Runs the pipeline on an existing file."""
        print(f"\n>>> [PIPELINE START] Running pipeline for dataset: '{papers_path}'")
        logger.info(f"PipelineManager: Starting pipeline for {papers_path}")

        # 1. Data Ingestion
        self.profiler.start("2. Data Ingestion & Validation")
        print(">>> [STAGE 1] Ingesting and validating input dataset...")
        df_pd = self.data_orch.load_and_validate_data(papers_path)
        self.profiler.stop("2. Data Ingestion & Validation")

        if df_pd is None or df_pd.empty:
            print(">>> [ERROR] Data validation/screening failed or dataset is empty. Aborting.")
            logger.error("Data validation/screening failed or dataset is empty. Aborting.")
            return

        df_pd.to_csv(os.path.join(self.output_dir, "publication_dataset.csv"), index=False)

        # 2. Routing based on dataset type
        is_references_dataset = "source" in df_pd.columns and "destination" in df_pd.columns
        if is_references_dataset:
            print(">>> [STAGE 2] Routing to dedicated references dataset analysis...")
            self.profiler.start("3. References Dataset Analysis")
            self.analysis_orch.analyze_references_dataset(df_pd)
            self.profiler.stop("3. References Dataset Analysis")
            return

        # 3. Main Analysis Pipeline
        print(">>> [STAGE 3] Running main analytical pipeline...")
        self.profiler.start("3. Main Bibliometric Analysis & Graphs")
        self.analysis_orch.run_analysis(df_pd, refs_path)
        self.profiler.stop("3. Main Bibliometric Analysis & Graphs")

        # 3.5 Meta-Analysis Pipeline
        if self.config.get("meta_analysis", False):
            print(">>> [STAGE 3.5] Running Meta-Analysis Pipeline...")
            try:
                from src.core.fulltext.retriever import PDFRetriever
                from src.core.fulltext.parser import PDFParser
                from src.core.extraction import VariableExtractor
                from src.core.meta_analysis import EffectSizeSynthesizer

                # 3.5.1 PDF Retrieval
                self.profiler.start("4. Parallel PDF Retrieval")
                retriever = PDFRetriever(
                    cache_dir=os.path.join(self.output_dir, "data", "fulltext_cache"),
                    max_concurrency=8,
                    timeout_seconds=8.0
                )
                df_with_pdfs = retriever.retrieve_pdfs(df_pd, max_papers=self.config.get("max_meta_papers", 30))
                self.profiler.stop("4. Parallel PDF Retrieval")

                # 3.5.2 PDF Parsing
                self.profiler.start("5. PDF Text & Section Parsing")
                parser = PDFParser()
                df_parsed = parser.parse_dataframe(df_with_pdfs)
                self.profiler.stop("5. PDF Text & Section Parsing")

                # 3.5.3 Variable Extraction
                self.profiler.start("6. Quantitative Variable Extraction")
                extractor = VariableExtractor()
                df_extracted = extractor.extract_dataframe(df_parsed)
                df_extracted.to_csv(os.path.join(self.output_dir, "extracted_study_data.csv"), index=False)
                self.profiler.stop("6. Quantitative Variable Extraction")

                # 3.5.4 Statistical Synthesis
                self.profiler.start("7. Meta-Analysis Stats & Plots")
                synthesizer = EffectSizeSynthesizer()
                meta_res, df_analyzed = synthesizer.run_meta_analysis(df_extracted)

                with open(os.path.join(self.output_dir, "meta_analysis_results.json"), "w") as f:
                    json.dump(meta_res, f, indent=4)

                figures_dir = os.path.join(self.output_dir, "figures")
                os.makedirs(figures_dir, exist_ok=True)

                if not df_analyzed.empty:
                    self.analysis_orch.viz.plot_forest(df_analyzed, meta_res, save_path=os.path.join(figures_dir, "forest_plot.pdf"))
                    self.analysis_orch.viz.plot_funnel(df_analyzed, save_path=os.path.join(figures_dir, "funnel_plot.pdf"))

                prisma_file = os.path.join(self.output_dir, "prisma_metrics.json")
                if os.path.exists(prisma_file):
                    with open(prisma_file, "r") as f:
                        prisma_data = json.load(f)
                    self.analysis_orch.viz.plot_prisma_flowchart(prisma_data, save_path=os.path.join(figures_dir, "prisma_flowchart.pdf"))

                self.profiler.stop("7. Meta-Analysis Stats & Plots")
                print(">>> [SUCCESS] Meta-Analysis Pipeline completed.")
            except Exception as e:
                print(f">>> [ERROR] Meta-Analysis Pipeline failed: {e}")
                logger.exception("Meta-Analysis failure")

        # 4. Export stage
        print("\n>>> [STAGE 4] Exporting LaTeX table and manuscript templates...")
        self.profiler.start("8. LaTeX Template Exporters")
        try:
            exporter = LaTeXExporter(self.output_dir)
            exporter.export_all(force=True)
            print(">>> LaTeX templates exported successfully.")
        except Exception as e:
            print(f">>> [WARNING] Could not export LaTeX templates: {e}")
            logger.warning(f"Could not export LaTeX templates: {e}")
        self.profiler.stop("8. LaTeX Template Exporters")

        # 5. Compile the IEEEtran scaffold into the final PDF document
        self.profiler.start("9. pdflatex PDF Compilation")
        self._compile_pdf()
        self.profiler.stop("9. pdflatex PDF Compilation")

        # Print detailed profiling summary
        self.profiler.print_summary(output_dir=self.output_dir)

        print(f"\n>>> [PIPELINE COMPLETE] All results, figures, tables, and manuscript PDF saved to: {self.output_dir}")
        logger.info(f"Pipeline complete. All results saved to {self.output_dir}")

    def _compile_pdf(self):
        scaffold_tex = os.path.join(self.output_dir, "paper_scaffold.tex")
        onecol_tex = os.path.join(self.output_dir, "paper_scaffold_onecolumn.tex")
        meta_onecol_tex = os.path.join(self.output_dir, "meta_paper_scaffold_onecolumn.tex")
        
        if not os.path.exists(scaffold_tex) and not os.path.exists(meta_onecol_tex):
            print(">>> [WARNING] No paper scaffolds found; skipping PDF compilation.")
            logger.warning("Paper scaffolds not found; skipping PDF compilation.")
            return
        
        print("\n>>> [STAGE 5] Compiling IEEEtran paper scaffolds to PDF via pdflatex...")
        try:
            if os.path.exists(scaffold_tex):
                subprocess.run(["pdflatex", "-interaction=nonstopmode", "paper_scaffold.tex"], cwd=self.output_dir, check=False)
                subprocess.run(["pdflatex", "-interaction=nonstopmode", "paper_scaffold.tex"], cwd=self.output_dir, check=False)
            
            if os.path.exists(onecol_tex):
                subprocess.run(["pdflatex", "-interaction=nonstopmode", "paper_scaffold_onecolumn.tex"], cwd=self.output_dir, check=False)
                subprocess.run(["pdflatex", "-interaction=nonstopmode", "paper_scaffold_onecolumn.tex"], cwd=self.output_dir, check=False)
                pdf_path = os.path.join(self.output_dir, "paper_scaffold_onecolumn.pdf")
                if os.path.exists(pdf_path):
                    print(f">>> [SUCCESS] Bibliometric PDF generated: {pdf_path}")

            if os.path.exists(meta_onecol_tex):
                print(">>> Compiling PRISMA Meta-Analysis scaffold (meta_paper_scaffold_onecolumn.tex)...")
                subprocess.run(["pdflatex", "-interaction=nonstopmode", "meta_paper_scaffold_onecolumn.tex"], cwd=self.output_dir, check=False)
                subprocess.run(["pdflatex", "-interaction=nonstopmode", "meta_paper_scaffold_onecolumn.tex"], cwd=self.output_dir, check=False)
                meta_pdf_path = os.path.join(self.output_dir, "meta_paper_scaffold_onecolumn.pdf")
                if os.path.exists(meta_pdf_path):
                    print(f">>> [SUCCESS] PRISMA Meta-Analysis PDF generated: {meta_pdf_path}")
        except Exception as e:
            print(f">>> [ERROR] PDF compilation failed: {e}")
            logger.warning(f"PDF compilation error: {e}")
