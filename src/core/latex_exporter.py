import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

from src.core.exporters import (
    export_author_table,
    export_keywords_table,
    export_cocitation_tables,
    export_coupling_tables,
    export_llm_table,
    export_temporal_table,
    export_country_table,
    export_bertopic_table,
    export_method_application_table,
    export_query_table,
    export_meta_tables,
)

class LaTeXExporter:
    """
    Orchestration Layer for IEEEtran LaTeX paper scaffolds.
    Supports both standard Bibliometric Review and PRISMA 2020 Meta-Analysis manuscript scaffolds.
    """
    def __init__(self, output_dir: str = "pipeline_results"):
        self.output_dir = output_dir
        self.figures_dir = os.path.join(self.output_dir, "figures")
        self.tables_dir = os.path.join(self.output_dir, "tables")
        self.data_dir = os.path.join(self.output_dir, "data")

        os.makedirs(self.figures_dir, exist_ok=True)
        os.makedirs(self.tables_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)

    def export_all(self, title: str = "Automated Bibliometric Review", force: bool = False):
        logger.info(f"LaTeXExporter: Assembling IEEEtran paper scaffold in {self.output_dir}...")
        self.copy_cls_template()
        self.export_tables(force=force)
        self.export_figure_links()
        self.export_annexes(force=force)
        self.export_paper_scaffold(title=title)
        self.export_meta_analysis_scaffold(title=f"A Systematic Literature Review and Quantitative Meta-Analysis")
        logger.info("LaTeXExporter: IEEEtran paper scaffolds assembled successfully!")

    def copy_cls_template(self):
        cls_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates", "IEEEtran.cls"))
        cls_target = os.path.join(self.output_dir, "IEEEtran.cls")
        if os.path.exists(cls_src):
            import shutil
            shutil.copyfile(cls_src, cls_target)
            logger.info("Copied IEEEtran.cls into output directory.")

    def export_tables(self, force: bool = False):
        """Generates formatted IEEEtran LaTeX table .tex files."""
        export_cocitation_tables(self.output_dir, force=force)
        export_coupling_tables(self.output_dir, force=force)
        export_meta_tables(self.output_dir, force=force)

    def export_figure_links(self):
        """Maps output PDF/PNG files to IEEEtran Figure_X filenames inside figures/ subfolder."""
        fig_dir = self.figures_dir
        fig_mappings = {
            "yearly_growth.pdf": "Figure_1.pdf",
            "co_citation_count.pdf": "Figure_2.pdf",
            "percolation_analysis.pdf": "Figure_3.png",
            "cocitation_graph.pdf": "Figure_5.pdf",
            "country_world_map.pdf": "Figure_10.pdf",
            "topic_word_scores.pdf": "Figure_20.pdf",
            "temporal_delta_shifts.pdf": "Figure_15.pdf",
            "author_leadership_matrix.pdf": "Figure_22.pdf",
            "method_application_matrix.pdf": "Figure_25.pdf",
        }

        if os.path.exists(os.path.join(self.output_dir, "network_circular_chord.pdf")) or os.path.exists(os.path.join(fig_dir, "network_circular_chord.pdf")):
            fig_mappings["network_circular_chord.pdf"] = "Figure_8.pdf"
        elif os.path.exists(os.path.join(self.output_dir, "network_circular_chord.png")) or os.path.exists(os.path.join(fig_dir, "network_circular_chord.png")):
            fig_mappings["network_circular_chord.png"] = "Figure_8.pdf"
        else:
            fig_mappings["network_graph.pdf"] = "Figure_8.pdf"

        for src_name, target_name in fig_mappings.items():
            src_path = os.path.join(fig_dir, src_name)
            if not os.path.exists(src_path):
                src_path = os.path.join(self.output_dir, src_name)
            target_path = os.path.join(fig_dir, target_name)
            if os.path.exists(src_path):
                try:
                    import shutil
                    shutil.copyfile(src_path, target_path)
                except Exception:
                    pass

    def export_annexes(self, force: bool = False):
        """Generates populated annex LaTeX files from analysis results."""
        export_author_table(self.output_dir, force=force)
        export_keywords_table(self.output_dir, force=force)
        export_llm_table(self.output_dir, force=force)
        export_temporal_table(self.output_dir, force=force)
        export_country_table(self.output_dir, force=force)
        export_bertopic_table(self.output_dir, force=force)
        export_method_application_table(self.output_dir, force=force)
        export_query_table(self.output_dir, force=force)

    def _build_scaffold_content(self, title: str, onecolumn: bool = False) -> str:
        tex = []
        tex.append(f"\\documentclass[journal{',onecolumn' if onecolumn else ''}]{{IEEEtran}}")
        tex.append("\\usepackage[utf8]{inputenc}")
        tex.append("\\usepackage[english]{babel}")
        tex.append("\\usepackage{graphicx}")
        tex.append("\\graphicspath{{figures/}}")
        tex.append("\\usepackage{booktabs}")
        tex.append("\\usepackage{amsmath}")
        tex.append("\\usepackage{hyperref}")
        tex.append("\\usepackage{ragged2e}")
        tex.append("\\usepackage{array}")
        tex.append("\\usepackage{longtable}")
        tex.append("\\usepackage{rotating}")
        tex.append("\\usepackage{xcolor}")
        tex.append("\\newcolumntype{P}[1]{>{\\RaggedRight\\arraybackslash}p{#1}}")
        tex.append("")
        tex.append(f"\\title{{{title}}}")
        tex.append("\\author{Automated Research Pipeline}")
        tex.append("")
        tex.append("\\begin{document}")
        tex.append("\\maketitle")
        tex.append("")
        tex.append("\\begin{abstract}")
        tex.append("This bibliometric review analyzes publication growth, co-authorship networks, and reference co-citations across the domain.")
        tex.append("\\end{abstract}")
        tex.append("")
        tex.append("\\section{Introduction}")
        tex.append("This paper presents a systematic bibliometric mapping of the research landscape.")
        tex.append("")
        tex.append("\\section{Landscape \\& Bibliometric Dynamics}")
        tex.append("\\subsection{Publication Growth Trajectory}")
        tex.append("\\begin{figure}[htbp]\\centering\\IfFileExists{figures/Figure_1.pdf}{\\includegraphics[width=0.95\\linewidth]{Figure_1.pdf}}{}\\caption{Annual Publication Trajectory}\\label{fig:growth}\\end{figure}")
        tex.append("")
        tex.append("\\subsection{Thematic AI Clustering \\& Content Analysis}")
        tex.append("\\begin{figure}[htbp]\\centering\\IfFileExists{figures/Figure_20.pdf}{\\includegraphics[width=0.95\\linewidth]{Figure_20.pdf}}{}\\caption{BERTopic Word Distributions}\\label{fig:topic_scores}\\end{figure}")
        tex.append("\\IfFileExists{tables/annex_llm_screening.tex}{\\input{tables/annex_llm_screening.tex}}{}")
        tex.append("")
        tex.append("\\subsection{Co-Authorship Network and Communities}")
        tex.append("\\begin{figure}[htbp]\\centering\\IfFileExists{figures/Figure_8.pdf}{\\includegraphics[width=0.95\\linewidth]{Figure_8.pdf}}{}\\caption{Co-Authorship Network Communities}\\label{fig:network}\\end{figure}")
        tex.append("\\begin{figure}[htbp]\\centering\\IfFileExists{figures/Figure_10.pdf}{\\includegraphics[width=0.95\\linewidth]{Figure_10.pdf}}{}\\caption{Geographic Publication Heatmap}\\label{fig:map}\\end{figure}")
        tex.append("")
        tex.append("\\subsection{Citation Structure}")
        tex.append("\\begin{figure}[htbp]\\centering\\IfFileExists{figures/Figure_5.pdf}{\\includegraphics[width=0.95\\linewidth]{Figure_5.pdf}}{}\\caption{Co-Citation Network}\\label{fig:cocitation}\\end{figure}")
        tex.append("\\IfFileExists{tables/tab_top_references_pagerank.tex}{\\input{tables/tab_top_references_pagerank.tex}}{}")
        tex.append("")
        tex.append("\\section{Discussion \\& Conclusion}")
        tex.append("This study provides a structured overview of the domain dynamics.")
        tex.append("")
        tex.append("\\section{Annex}")
        tex.append("\\IfFileExists{tables/annex_query.tex}{\\input{tables/annex_query.tex}}{}")
        tex.append("\\IfFileExists{tables/annex_keywords.tex}{\\input{tables/annex_keywords.tex}}{}")
        tex.append("\\IfFileExists{tables/annex_country_growth.tex}{\\input{tables/annex_country_growth.tex}}{}")
        tex.append("\\IfFileExists{tables/annex_temporal_deltas.tex}{\\input{tables/annex_temporal_deltas.tex}}{}")
        tex.append("\\IfFileExists{tables/annex_bertopic_details.tex}{\\input{tables/annex_bertopic_details.tex}}{}")
        tex.append("")
        tex.append("\\end{document}")
        return "\n".join(tex)

    def _build_meta_scaffold_content(self, title: str, onecolumn: bool = False) -> str:
        """Constructs a PRISMA 2020-compliant Systematic Literature Review & Meta-Analysis LaTeX scaffold."""
        tex = []
        tex.append(f"\\documentclass[journal{',onecolumn' if onecolumn else ''}]{{IEEEtran}}")
        tex.append("\\usepackage[utf8]{inputenc}")
        tex.append("\\usepackage[english]{babel}")
        tex.append("\\usepackage{graphicx}")
        tex.append("\\graphicspath{{figures/}}")
        tex.append("\\usepackage{booktabs}")
        tex.append("\\usepackage{amsmath}")
        tex.append("\\usepackage{hyperref}")
        tex.append("\\usepackage{ragged2e}")
        tex.append("\\usepackage{array}")
        tex.append("\\usepackage{longtable}")
        tex.append("\\usepackage{xcolor}")
        tex.append("")
        tex.append(f"\\title{{{title}}}")
        tex.append("\\author{Automated Meta-Analysis Engine}")
        tex.append("")
        tex.append("\\begin{document}")
        tex.append("\\maketitle")
        tex.append("")
        tex.append("\\begin{abstract}")
        tex.append("\\textbf{Background:} Quantitative synthesis of empirical findings across primary studies is essential for evidence-based decision making. ")
        tex.append("\\textbf{Methods:} Following PRISMA 2020 guidelines, we searched multi-source academic indices, applied eligibility screening, extracted quantitative study effect sizes, and performed random-effects meta-analysis (DerSimonian--Laird). ")
        tex.append("\\textbf{Results:} Studies were synthesized to assess pooled effect size, between-study heterogeneity ($I^2$, $\\tau^2$), and small-study publication bias. ")
        tex.append("\\textbf{Conclusions:} This review offers a rigorous quantitative synthesis of empirical outcomes.")
        tex.append("\\end{abstract}")
        tex.append("")
        tex.append("\\section{Introduction}")
        tex.append("Systematic literature reviews and quantitative meta-analyses synthesize empirical findings to establish consensus effect sizes and identify sources of heterogeneity across studies.")
        tex.append("")
        tex.append("\\section{Methods (PRISMA 2020 Protocol)}")
        tex.append("\\subsection{Eligibility Criteria \\& Information Sources}")
        tex.append("Studies were identified through automated multi-source queries across OpenAlex, Scopus, IEEE Xplore, PubMed, and preprint archives. Inclusion criteria followed a structured PICOS framework.")
        tex.append("")
        tex.append("\\subsection{Quantitative Extraction \\& Statistical Synthesis}")
        tex.append("Effect sizes ($d$) were extracted and synthesized using inverse-variance weighted fixed-effects and DerSimonian--Laird random-effects models. Heterogeneity was evaluated via Cochran's $Q$, Higgins \\& Thompson's $I^2$, and between-study variance $\\tau^2$. Publication bias was assessed using Egger's linear regression.")
        tex.append("")
        tex.append("\\section{Meta-Analytic Results}")
        tex.append("\\subsection{PRISMA Study Flow}")
        tex.append("\\begin{figure}[htbp]\\centering\\IfFileExists{figures/prisma_flowchart.pdf}{\\includegraphics[width=0.85\\linewidth]{prisma_flowchart.pdf}}{}\\caption{PRISMA 2020 Flow Diagram of Identification, Screening, Eligibility, and Inclusion.}\\label{fig:prisma}\\end{figure}")
        tex.append("")
        tex.append("\\IfFileExists{tables/tab_study_characteristics.tex}{\\input{tables/tab_study_characteristics.tex}}{}")
        tex.append("")
        tex.append("\\subsection{Quantitative Synthesis \\& Forest Plot}")
        tex.append("\\begin{figure}[htbp]\\centering\\IfFileExists{figures/forest_plot.pdf}{\\includegraphics[width=0.95\\linewidth]{forest_plot.pdf}}{}\\caption{Forest Plot of Study-Level Effect Sizes ($95\\%$ CI) and Summary Pooled Estimate Diamond.}\\label{fig:forest}\\end{figure}")
        tex.append("")
        tex.append("\\IfFileExists{tables/tab_meta_analysis_summary.tex}{\\input{tables/tab_meta_analysis_summary.tex}}{}")
        tex.append("")
        tex.append("\\subsection{Publication Bias \\& Funnel Plot}")
        tex.append("\\begin{figure}[htbp]\\centering\\IfFileExists{figures/funnel_plot.pdf}{\\includegraphics[width=0.85\\linewidth]{funnel_plot.pdf}}{}\\caption{Funnel Plot with Pseudo $95\\%$ Confidence Limits Evaluating Publication Bias.}\\label{fig:funnel}\\end{figure}")
        tex.append("")
        tex.append("\\section{Discussion \\& Limitations}")
        tex.append("Between-study heterogeneity and subgroup variations illustrate divergent empirical contexts across the literature.")
        tex.append("")
        tex.append("\\section{Conclusion}")
        tex.append("This automated meta-analysis synthesizes the current state of evidence and provides empirical benchmarks for future research.")
        tex.append("")
        tex.append("\\end{document}")
        return "\n".join(tex)

    def export_paper_scaffold(self, title: str = "Automated Bibliometric Review"):
        """Generates standard bibliometric review templates."""
        scaffold_path = os.path.join(self.output_dir, "paper_scaffold.tex")
        onecol_path = os.path.join(self.output_dir, "paper_scaffold_onecolumn.tex")

        with open(scaffold_path, "w", encoding="utf-8") as f:
            f.write(self._build_scaffold_content(title, onecolumn=False))
        with open(onecol_path, "w", encoding="utf-8") as f:
            f.write(self._build_scaffold_content(title, onecolumn=True))

    def export_meta_analysis_scaffold(self, title: str = "Automated Systematic Literature Review and Meta-Analysis"):
        """Generates dedicated PRISMA-compliant Meta-Analysis templates."""
        meta_scaffold_path = os.path.join(self.output_dir, "meta_paper_scaffold.tex")
        meta_onecol_path = os.path.join(self.output_dir, "meta_paper_scaffold_onecolumn.tex")

        with open(meta_scaffold_path, "w", encoding="utf-8") as f:
            f.write(self._build_meta_scaffold_content(title, onecolumn=False))
        with open(meta_onecol_path, "w", encoding="utf-8") as f:
            f.write(self._build_meta_scaffold_content(title, onecolumn=True))
        logger.info(f"LaTeXExporter: Generated PRISMA Meta-Analysis scaffold -> {meta_scaffold_path}")
