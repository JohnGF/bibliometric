import os
import json
import logging
import asyncio
import subprocess
import pandas as pd
from typing import Optional, Dict, Any

from src.core.fulltext.retriever import PDFRetriever
from src.core.fulltext.parser import PDFParser
from src.core.extraction import VariableExtractor
from src.core.meta_analysis import EffectSizeSynthesizer
from src.core.viz import Visualization
from src.core.exporters.meta_exporter import export_meta_tables

logger = logging.getLogger(__name__)

class MetaAnalysisOrchestrator:
    """
    Dedicated Orchestrator for Quantitative Systematic Review & Meta-Analysis.
    Executes only the stages required for quantitative synthesis:
    1. Candidate filtering & Async PDF retrieval
    2. Section and table parsing
    3. Multi-domain quantitative extraction & effect size standardization
    4. Fixed/Random effects synthesis & heterogeneity diagnostics
    5. PRISMA, Forest, and Funnel visual generation
    6. PRISMA Meta-Analysis LaTeX compilation
    """

    def __init__(self, output_dir: str = "pipeline_results_meta", profiler=None):
        self.output_dir = output_dir
        self.profiler = profiler
        self.figures_dir = os.path.join(self.output_dir, "figures")
        self.tables_dir = os.path.join(self.output_dir, "tables")
        self.data_dir = os.path.join(self.output_dir, "data")
        self.viz = Visualization()

        os.makedirs(self.figures_dir, exist_ok=True)
        os.makedirs(self.tables_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)

    def run(self, df: pd.DataFrame) -> Dict[str, Any]:
        print("\n========================================================")
        print(">>> [META-ANALYSIS PIPELINE] Starting Quantitative Synthesis")
        print("========================================================")

        # Stage 1: Filter Candidates & Parallel Async PDF Retrieval
        if self.profiler: self.profiler.start("1. Candidate Filter & PDF Retrieval")
        print("\n>>> [META STAGE 1] Retrieving Open-Access Full-Text PDFs asynchronously...")
        retriever = PDFRetriever(cache_dir=os.path.join(self.data_dir, "fulltext_cache"))
        df_with_pdfs = retriever.retrieve_pdfs(df)
        if self.profiler: self.profiler.stop("1. Candidate Filter & PDF Retrieval")

        # Stage 2: PDF Parsing
        if self.profiler: self.profiler.start("2. PDF Section Parsing")
        print("\n>>> [META STAGE 2] Parsing Canonical Sections (Methods, Results, Abstracts)...")
        parser = PDFParser()
        df_parsed = parser.parse_dataframe(df_with_pdfs)
        if self.profiler: self.profiler.stop("2. PDF Section Parsing")

        # Stage 3: Multi-Domain Variable Extraction
        if self.profiler: self.profiler.start("3. Multi-Domain Variable Extraction")
        print("\n>>> [META STAGE 3] Extracting Empirical Estimates & Standardizing Effect Sizes...")
        extractor = VariableExtractor()
        df_extracted = extractor.extract_dataframe(df_parsed)
        extracted_csv = os.path.join(self.output_dir, "extracted_study_data.csv")
        df_extracted.to_csv(extracted_csv, index=False)
        print(f">>> Extracted study dataset saved to: {extracted_csv}")
        if self.profiler: self.profiler.stop("3. Multi-Domain Variable Extraction")

        # Stage 4: Statistical Synthesis (Fixed & Random Effects)
        if self.profiler: self.profiler.start("4. Statistical Synthesis Engine")
        print("\n>>> [META STAGE 4] Running DerSimonian-Laird Random Effects Meta-Analysis...")
        synthesizer = EffectSizeSynthesizer()
        meta_res, df_analyzed = synthesizer.run_meta_analysis(df_extracted)

        results_json = os.path.join(self.output_dir, "meta_analysis_results.json")
        with open(results_json, "w") as f:
            json.dump(meta_res, f, indent=4)
        print(f">>> Statistical results saved to: {results_json}")
        if self.profiler: self.profiler.stop("4. Statistical Synthesis Engine")

        # Stage 5: Visualizations (Forest, Funnel, PRISMA)
        if self.profiler: self.profiler.start("5. Meta-Analytic Visuals")
        print("\n>>> [META STAGE 5] Generating Publication-Quality Forest & Funnel Plots...")
        if not df_analyzed.empty and len(df_analyzed) >= 2:
            self.viz.plot_forest(df_analyzed, meta_res, save_path=os.path.join(self.figures_dir, "forest_plot.pdf"))
            self.viz.plot_funnel(df_analyzed, save_path=os.path.join(self.figures_dir, "funnel_plot.pdf"))
            print(">>> Generated Forest Plot & Funnel Plot.")
        else:
            print(">>> [NOTE] Forest plot skipped (fewer than 2 quantitative studies with standardizable effects).")

        prisma_file = os.path.join(self.output_dir, "prisma_metrics.json")
        if os.path.exists(prisma_file):
            with open(prisma_file, "r") as f:
                prisma_data = json.load(f)
            self.viz.plot_prisma_flowchart(prisma_data, save_path=os.path.join(self.figures_dir, "prisma_flowchart.pdf"))
        if self.profiler: self.profiler.stop("5. Meta-Analytic Visuals")

        # Stage 6: LaTeX Scaffold & PDF Compilation
        if self.profiler: self.profiler.start("6. LaTeX PRISMA Compilation")
        print("\n>>> [META STAGE 6] Exporting PRISMA LaTeX tables and compiling manuscript...")
        export_meta_tables(self.output_dir, force=True)

        from src.core.latex_exporter import LaTeXExporter
        exporter = LaTeXExporter(self.output_dir)
        exporter.copy_cls_template()
        exporter.export_meta_analysis_scaffold(title="Quantitative Systematic Review \\& Meta-Analysis")

        meta_onecol_tex = os.path.join(self.output_dir, "meta_paper_scaffold_onecolumn.tex")
        if os.path.exists(meta_onecol_tex):
            try:
                subprocess.run(["pdflatex", "-interaction=nonstopmode", "meta_paper_scaffold_onecolumn.tex"], cwd=self.output_dir, check=False)
                subprocess.run(["pdflatex", "-interaction=nonstopmode", "meta_paper_scaffold_onecolumn.tex"], cwd=self.output_dir, check=False)
                meta_pdf = os.path.join(self.output_dir, "meta_paper_scaffold_onecolumn.pdf")
                if os.path.exists(meta_pdf):
                    print(f">>> [SUCCESS] PRISMA Meta-Analysis PDF generated: {meta_pdf}")
            except Exception as e:
                logger.warning(f"Could not compile meta_paper_scaffold: {e}")
        if self.profiler: self.profiler.stop("6. LaTeX PRISMA Compilation")

        print(f"\n>>> [COMPLETE] Quantitative Meta-Analysis completed in {self.output_dir}")
        return meta_res
