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
)

class LaTeXExporter:
    """
    Lightweight Orchestration Layer for IEEEtran LaTeX paper scaffold generation.
    Delegates individual table generation to modular exporters in src.core.exporters.
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
        logger.info("LaTeXExporter: IEEEtran paper scaffold assembled successfully!")

    def copy_cls_template(self):
        cls_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates", "IEEEtran.cls"))
        cls_target = os.path.join(self.output_dir, "IEEEtran.cls")
        if os.path.exists(cls_src):
            import shutil
            shutil.copyfile(cls_src, cls_target)
            logger.info("Copied IEEEtran.cls into output directory.")

    def export_tables(self, force: bool = False):
        """Generates formatted IEEEtran LaTeX table .tex files with hyperlinked titles."""
        export_cocitation_tables(self.output_dir, force=force)
        export_coupling_tables(self.output_dir, force=force)

    def export_figure_links(self):
        """Maps output PDF/PNG files to IEEEtran Figure_X filenames inside figures/ subfolder."""
        fig_dir = self.figures_dir
        fig_mappings = {}
        if os.path.exists(os.path.join(self.output_dir, "network_circular_chord.pdf")) or os.path.exists(os.path.join(fig_dir, "network_circular_chord.pdf")):
            fig_mappings["network_circular_chord.pdf"] = "Figure_8.pdf"
        elif os.path.exists(os.path.join(self.output_dir, "network_circular_chord.png")) or os.path.exists(os.path.join(fig_dir, "network_circular_chord.png")):
            fig_mappings["network_circular_chord.png"] = "Figure_8.pdf"
        else:
            fig_mappings["network_graph.pdf"] = "Figure_8.pdf"

        fig_mappings.update({
            "yearly_growth.pdf": "Figure_1.pdf",
            "co_citation_count.pdf": "Figure_2.pdf",
            "percolation_analysis.pdf": "Figure_3.png",
            "cocitation_graph.pdf": "Figure_5.pdf",
            "country_world_map.pdf": "Figure_10.pdf",
            "topic_word_scores.pdf": "Figure_20.pdf",
            "temporal_delta_shifts.pdf": "Figure_15.pdf",
            "llm_noise_paradigm.pdf": "Figure_22.pdf",
            "method_application_matrix.pdf": "Figure_25.pdf",
        })

        for src_name, target_name in fig_mappings.items():
            src_path = os.path.join(fig_dir, src_name) if os.path.exists(os.path.join(fig_dir, src_name)) else os.path.join(self.output_dir, src_name)
            target_path = os.path.join(fig_dir, target_name)
            top_target_path = os.path.join(self.output_dir, target_name)
            if os.path.exists(src_path):
                try:
                    import shutil
                    shutil.copyfile(src_path, target_path)
                    shutil.copyfile(src_path, top_target_path)
                    logger.info(f"Mapped figure {src_name} -> {target_name}")
                except Exception as e:
                    logger.warning(f"Could not copy figure {src_name}: {e}")

    def export_annexes(self, force: bool = False):
        """Generates populated annex LaTeX files from analysis results."""
        export_author_table(self.output_dir, force=force)
        export_keywords_table(self.output_dir, force=force)
        export_llm_table(self.output_dir, force=force)
        export_temporal_table(self.output_dir, force=force)
        export_country_table(self.output_dir, force=force)
        export_bertopic_table(self.output_dir, force=force)
        export_method_application_table(self.output_dir, force=force)

    def export_paper_scaffold(self, title: str = "Automated Bibliometric Review"):
        """Generates ready-to-compile master paper_scaffold.tex template."""
        scaffold_path = os.path.join(self.output_dir, "paper_scaffold.tex")
        tex = []
        tex.append("\\documentclass[journal]{IEEEtran}")
        tex.append("\\usepackage[utf8]{inputenc}")
        tex.append("\\usepackage[english]{babel}")
        tex.append("\\usepackage{graphicx}")
        tex.append("\\graphicspath{{figures/}{./}}")
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
        tex.append("\\definecolor{color1}{HTML}{1F77B4}")
        tex.append("\\definecolor{color2}{HTML}{AEC7E8}")
        tex.append("\\definecolor{color3}{HTML}{FF7F0E}")
        tex.append("\\definecolor{color4}{HTML}{FFBB78}")
        tex.append("\\definecolor{color5}{HTML}{2CA02C}")
        tex.append("")
        tex.append(f"\\title{{{title}}}")
        tex.append("\\author{Author Name(s)}")
        tex.append("")
        tex.append("\\begin{document}")
        tex.append("\\maketitle")
        tex.append("")
        tex.append("\\begin{abstract}")
        tex.append("% [TODO: Insert paper abstract summary here]")
        tex.append("This bibliometric review analyzes publication growth, co-authorship networks, and reference co-citations.")
        tex.append("\\end{abstract}")
        tex.append("")
        tex.append("\\section{Introduction}")
        tex.append("% [TODO: Insert Introduction text here]")
        tex.append("")
        tex.append("\\section{Methodology}")
        tex.append("% [TODO: Insert Methodology description here]")
        tex.append("")
        tex.append("\\section{Bibliometric Analysis}")
        tex.append("")
        tex.append("\\subsection{Growth of the Dataset \\& LLM Noise Screening}")
        tex.append("\\begin{figure}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{figures/Figure_1.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_1.pdf}}{\\IfFileExists{Figure_1.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_1.pdf}}{}}")
        tex.append("    \\caption{Publication Count and Annual Growth}")
        tex.append("    \\label{fig:pubCountGrowth}")
        tex.append("\\end{figure}")
        tex.append("")
        tex.append("% Ollama LLM Screening & Data Pruning Justification Table")
        tex.append("\\IfFileExists{tables/annex_llm_screening.tex}{\\input{tables/annex_llm_screening.tex}}{\\IfFileExists{annex_llm_screening.tex}{\\input{annex_llm_screening.tex}}{}}")
        tex.append("")
        tex.append("\\subsection{AI Content Analysis, BERTopic \\& LLM Noise Treatment Paradigms}")
        tex.append("\\begin{figure*}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{figures/Figure_20.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_20.pdf}}{\\IfFileExists{Figure_20.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_20.pdf}}{}}")
        tex.append("    \\caption{Discovered BERTopic Thematic Clusters and Keyword Scores}")
        tex.append("    \\label{fig:bertopic_clusters}")
        tex.append("\\end{figure*}")
        tex.append("")
        tex.append("\\begin{figure}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{figures/Figure_22.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_22.pdf}}{\\IfFileExists{Figure_22.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_22.pdf}}{}}")
        tex.append("    \\caption{Ollama LLM Classification of EEG Noise Treatment Paradigms}")
        tex.append("    \\label{fig:llm_noise_paradigm}")
        tex.append("\\end{figure}")
        tex.append("")
        tex.append("\\begin{figure*}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{figures/Figure_25.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_25.pdf}}{\\IfFileExists{Figure_25.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_25.pdf}}{}}")
        tex.append("    \\caption{Methodology vs Application Field Cross-Tabulation Bipartite Matrix}")
        tex.append("    \\label{fig:method_application_matrix}")
        tex.append("\\end{figure*}")
        tex.append("")
        tex.append("\\subsection{Scientific Temporal Dynamics \\& Paradigm Shifts ($\\Delta$ Analysis)}")
        tex.append("\\begin{figure*}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{figures/Figure_15.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_15.pdf}}{\\IfFileExists{Figure_15.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_15.pdf}}{}}")
        tex.append("    \\caption{Scientific Market Share Deltas ($\\Delta$ \\%) Between Baseline vs Modern Epochs}")
        tex.append("    \\label{fig:temporal_delta_shifts}")
        tex.append("\\end{figure*}")
        tex.append("")
        tex.append("\\subsection{Authorship and Community Analysis}")
        tex.append("\\begin{figure*}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{figures/Figure_8.pdf}{\\includegraphics[width=0.88\\linewidth]{Figure_8.pdf}}{\\IfFileExists{Figure_8.pdf}{\\includegraphics[width=0.88\\linewidth]{Figure_8.pdf}}{}}")
        tex.append("    \\caption{Louvain Community Clustered Co-Authorship Ring Network}")
        tex.append("    \\label{fig:network_graph}")
        tex.append("\\end{figure*}")
        tex.append("")
        tex.append("\\begin{figure*}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{figures/Figure_10.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_10.pdf}}{\\IfFileExists{Figure_10.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_10.pdf}}{}}")
        tex.append("    \\caption{Global Institutional Research Heatmap by Country}")
        tex.append("    \\label{fig:country_world_map}")
        tex.append("\\end{figure*}")
        tex.append("")
        tex.append("\\subsection{Reference-Based Analysis}")
        tex.append("\\subsubsection{Co-Citation Network}")
        tex.append("\\begin{figure}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{figures/Figure_5.pdf}{\\includegraphics[width=0.9\\linewidth]{Figure_5.pdf}}{\\IfFileExists{Figure_5.pdf}{\\includegraphics[width=0.9\\linewidth]{Figure_5.pdf}}{}}")
        tex.append("    \\caption{Reference Co-Citation Network Graph with Clickable OpenAlex Hyperlinks}")
        tex.append("    \\label{fig:cocitation_graph}")
        tex.append("\\end{figure}")
        tex.append("\\IfFileExists{tables/tab_top_references_pagerank.tex}{\\input{tables/tab_top_references_pagerank.tex}}{\\IfFileExists{tab_top_references_pagerank.tex}{\\input{tab_top_references_pagerank.tex}}{}}")
        tex.append("")
        tex.append("\\subsubsection{Bibliographic Coupling Network}")
        tex.append("\\IfFileExists{tables/tab_Biblio.tex}{\\input{tables/tab_Biblio.tex}}{\\IfFileExists{tab_Biblio.tex}{\\input{tab_Biblio.tex}}{}}")
        tex.append("")
        tex.append("\\section{Discussion}")
        tex.append("% [TODO: Insert Discussion analysis here]")
        tex.append("")
        tex.append("\\section{Conclusion}")
        tex.append("% [TODO: Insert Conclusion summary here]")
        tex.append("")
        tex.append("\\section{Annex}")
        tex.append("\\IfFileExists{tables/annex_query.tex}{\\input{tables/annex_query.tex}}{\\IfFileExists{annex_query.tex}{\\input{annex_query.tex}}{}}")
        tex.append("\\IfFileExists{tables/annex_Label_Co_Citation.tex}{\\input{tables/annex_Label_Co_Citation.tex}}{\\IfFileExists{annex_Label_Co_Citation.tex}{\\input{annex_Label_Co_Citation.tex}}{}}")
        tex.append("\\IfFileExists{tables/annex_Label_Bibliographic_Coupling.tex}{\\input{tables/annex_Label_Bibliographic_Coupling.tex}}{\\IfFileExists{annex_Label_Bibliographic_Coupling.tex}{\\input{annex_Label_Bibliographic_Coupling.tex}}{}}")
        tex.append("\\IfFileExists{tables/annex_Author_Sidetable.tex}{\\input{tables/annex_Author_Sidetable.tex}}{\\IfFileExists{annex_Author_Sidetable.tex}{\\input{annex_Author_Sidetable.tex}}{}}")
        tex.append("\\IfFileExists{tables/annex_Institutions_Extraction_List.tex}{\\input{tables/annex_Institutions_Extraction_List.tex}}{\\IfFileExists{annex_Institutions_Extraction_List.tex}{\\input{annex_Institutions_Extraction_List.tex}}{}}")
        tex.append("\\IfFileExists{tables/annex_Simplified_Keywords_Terms.tex}{\\input{tables/annex_Simplified_Keywords_Terms.tex}}{\\IfFileExists{annex_Simplified_Keywords_Terms.tex}{\\input{annex_Simplified_Keywords_Terms.tex}}{}}")
        tex.append("\\IfFileExists{tables/annex_keywords.tex}{\\input{tables/annex_keywords.tex}}{\\IfFileExists{annex_keywords.tex}{\\input{annex_keywords.tex}}{}}")
        tex.append("\\IfFileExists{tables/annex_country_growth.tex}{\\input{tables/annex_country_growth.tex}}{\\IfFileExists{annex_country_growth.tex}{\\input{annex_country_growth.tex}}{}}")
        tex.append("\\IfFileExists{tables/annex_temporal_deltas.tex}{\\input{tables/annex_temporal_deltas.tex}}{\\IfFileExists{annex_temporal_deltas.tex}{\\input{annex_temporal_deltas.tex}}{}}")
        tex.append("\\IfFileExists{tables/annex_bertopic_details.tex}{\\input{tables/annex_bertopic_details.tex}}{\\IfFileExists{annex_bertopic_details.tex}{\\input{annex_bertopic_details.tex}}{}}")
        tex.append("\\IfFileExists{tables/annex_method_application_matrix.tex}{\\input{tables/annex_method_application_matrix.tex}}{\\IfFileExists{annex_method_application_matrix.tex}{\\input{annex_method_application_matrix.tex}}{}}")
        tex.append("")
        tex.append("\\end{document}")

        with open(scaffold_path, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
        logger.info(f"LaTeXExporter: Generated ready-to-compile paper scaffold -> {scaffold_path}")
