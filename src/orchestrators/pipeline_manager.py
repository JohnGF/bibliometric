import os
import json
import logging
import subprocess
import time
import pandas as pd
from typing import Optional, Dict, Any

from src.orchestrators.data_orchestrator import DataOrchestrator
from src.orchestrators.analysis_orchestrator import AnalysisOrchestrator
from src.orchestrators.meta_orchestrator import MetaAnalysisOrchestrator
from src.orchestrators.systematic_orchestrator import SystematicReviewOrchestrator
from src.core.latex_exporter import LaTeXExporter

logger = logging.getLogger(__name__)

class PipelineProfiler:
    """Tracks latency for each phase and prints an ASCII summary table."""

    def __init__(self):
        self.stages = {}
        self._current_starts = {}

    def start(self, stage_name: str):
        self._current_starts[stage_name] = time.perf_counter()

    def stop(self, stage_name: str):
        if stage_name in self._current_starts:
            elapsed = time.perf_counter() - self._current_starts.pop(stage_name)
            self.stages[stage_name] = self.stages.get(stage_name, 0.0) + elapsed

    def print_summary(self, output_dir: Optional[str] = None):
        total_time = sum(self.stages.values())
        if total_time <= 0:
            return

        lines = [
            "",
            "=" * 70,
            f"=== PIPELINE EXECUTION PROFILE (Total: {total_time:.2f}s / {total_time / 60:.2f} min) ===",
            "=" * 70,
            f"{'Stage / Component':<45} | {'Duration (s)':>12} | {'Share (%)':>9}",
            "-" * 70,
        ]

        for stage, duration in self.stages.items():
            pct = (duration / total_time) * 100.0
            lines.append(f"{stage:<45} | {duration:>11.2f}s | {pct:>8.1f}%")

        lines.append("=" * 70)
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
    """
    Central Pipeline Dispatcher coordinating the three specialized pipelines:
    1. 'biblio': Bibliometric & Macro Scientometrics (graphs, citations, CAGR, BERTopic)
    2. 'systematic': Systematic Literature Review (PRISMA screening, qualitative taxonomy)
    3. 'meta': Quantitative Meta-Analysis (PDF retrieval, effect extraction, Forest/Funnel plots)
    4. 'all': Executes all three pipelines concurrently in dedicated outputs.
    """

    def __init__(self, output_dir: str = "pipeline_results", config: Optional[dict] = None):
        self.output_dir = output_dir
        self.config = config or {}
        self.mode = self.config.get("mode", "biblio").lower()
        if self.config.get("meta_analysis", False) and self.mode == "biblio":
            self.mode = "meta"

        self.profiler = PipelineProfiler()
        self.data_orch = DataOrchestrator(self.config)
        self.analysis_orch = AnalysisOrchestrator(self.output_dir, self.config)

    def run_with_query(self, query: str, limit: int = 100, start_year: Optional[int] = None, end_year: Optional[int] = None):
        """Fetches data from APIs and runs the pipeline for the given mode."""
        print(f"\n>>> [PIPELINE INITIALIZATION] Mode: '{self.mode.upper()}' | Query: '{query}' ({start_year}-{end_year})...")
        self.profiler.start("1. Data Collection (APIs)")
        papers_path = self.data_orch.collect_data(query, limit, start_year, end_year)
        self.profiler.stop("1. Data Collection (APIs)")
        if papers_path:
            return self.run(papers_path)

    def run(self, papers_path: str, refs_path: Optional[str] = None):
        """Runs the pipeline mode on an existing dataset file."""
        print(f"\n>>> [PIPELINE START] Running mode: '{self.mode.upper()}' on dataset: '{papers_path}'")
        logger.info(f"PipelineManager: Starting {self.mode} pipeline for {papers_path}")

        # Ingest and validate data
        self.profiler.start("2. Data Ingestion & Validation")
        print(">>> Ingesting and validating input dataset...")
        df_pd = self.data_orch.load_and_validate_data(papers_path)
        self.profiler.stop("2. Data Ingestion & Validation")

        if df_pd is None or df_pd.empty:
            print(">>> [ERROR] Data validation failed or dataset is empty. Aborting.")
            return

        os.makedirs(os.path.join(self.output_dir, "data"), exist_ok=True)
        df_pd.to_csv(os.path.join(self.output_dir, "data", "publication_dataset.csv"), index=False)

        # Dispatch based on Mode
        if self.mode == "meta":
            meta_orch = MetaAnalysisOrchestrator(self.output_dir, profiler=self.profiler)
            meta_orch.run(df_pd)
        elif self.mode == "systematic":
            slr_orch = SystematicReviewOrchestrator(self.output_dir, profiler=self.profiler)
            slr_orch.run(df_pd)
        elif self.mode == "all":
            # Run Bibliometric
            self.profiler.start("3. Bibliometric Analysis")
            self.analysis_orch.run_analysis(df_pd, refs_path)
            self.profiler.stop("3. Bibliometric Analysis")

            # Run Systematic
            slr_orch = SystematicReviewOrchestrator(self.output_dir, profiler=self.profiler)
            slr_orch.run(df_pd)

            # Run Meta
            meta_orch = MetaAnalysisOrchestrator(self.output_dir, profiler=self.profiler)
            meta_orch.run(df_pd)
        else:
            # Default: 'biblio'
            self.profiler.start("3. Bibliometric Analysis & Network Graphs")
            self.analysis_orch.run_analysis(df_pd, refs_path)
            self.profiler.stop("3. Bibliometric Analysis & Network Graphs")

            self.profiler.start("4. LaTeX Template Exporters")
            exporter = LaTeXExporter(self.output_dir)
            exporter.export_all(force=True)
            self.profiler.stop("4. LaTeX Template Exporters")

            self.profiler.start("5. pdflatex PDF Compilation")
            self._compile_pdf()
            self.profiler.stop("5. pdflatex PDF Compilation")

        # Print profiling summary
        self.profiler.print_summary(output_dir=self.output_dir)
        print(f"\n>>> [PIPELINE COMPLETE] Mode '{self.mode.upper()}' finished. All outputs saved to: {self.output_dir}")

    def _compile_pdf(self):
        scaffold_tex = os.path.join(self.output_dir, "paper_scaffold.tex")
        onecol_tex = os.path.join(self.output_dir, "paper_scaffold_onecolumn.tex")

        if not os.path.exists(scaffold_tex):
            return

        print("\n>>> Compiling IEEEtran Bibliometric manuscript via pdflatex...")
        try:
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "paper_scaffold.tex"], cwd=self.output_dir, check=False)
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "paper_scaffold.tex"], cwd=self.output_dir, check=False)
            if os.path.exists(onecol_tex):
                subprocess.run(["pdflatex", "-interaction=nonstopmode", "paper_scaffold_onecolumn.tex"], cwd=self.output_dir, check=False)
                subprocess.run(["pdflatex", "-interaction=nonstopmode", "paper_scaffold_onecolumn.tex"], cwd=self.output_dir, check=False)
                pdf_path = os.path.join(self.output_dir, "paper_scaffold_onecolumn.pdf")
                if os.path.exists(pdf_path):
                    print(f">>> [SUCCESS] Bibliometric PDF generated: {pdf_path}")
        except Exception as e:
            logger.warning(f"PDF compilation error: {e}")
