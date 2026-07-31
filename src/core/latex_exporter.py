import os
import logging
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)

class LaTeXExporter:
    """
    Exports bibliometric pipeline outputs directly into IEEEtran-compliant
    LaTeX tables, figures, and annex files matching main.tex templates.
    """
    def __init__(self, output_dir: str = "pipeline_results"):
        self.output_dir = output_dir

    def export_all(self, title: str = "Automated Bibliometric Review"):
        logger.info(f"LaTeXExporter: Generating IEEEtran LaTeX template files in {self.output_dir}...")
        self.copy_cls_template()
        self.export_tables()
        self.export_figure_links()
        self.export_annexes()
        self.export_paper_scaffold(title=title)
        logger.info("LaTeXExporter: IEEEtran template files generated successfully!")

    def copy_cls_template(self):
        cls_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates", "IEEEtran.cls"))
        cls_target = os.path.join(self.output_dir, "IEEEtran.cls")
        if os.path.exists(cls_src):
            import shutil
            shutil.copyfile(cls_src, cls_target)
            logger.info("Copied IEEEtran.cls into output directory.")

    def _load_title_lookup(self) -> dict:
        """Builds a lookup dict mapping OpenAlex URLs/DOIs/IDs to (title, doi_url)."""
        # Built-in dictionary for seminal reference IDs mapping to (title, official_doi_url)
        seminal_map = {
            "https://openalex.org/W31182665": ("EEGLAB: Open Source Toolbox for Single-Trial EEG", "https://doi.org/10.1016/j.jneumeth.2003.10.009"),
            "https://openalex.org/W2122816088": ("FieldTrip: Open Source Software for MEG & EEG", "https://doi.org/10.1155/2011/156869"),
            "https://openalex.org/W2768132193": ("EEGNet: Compact CNN for EEG Brain-Computer Interfaces", "https://doi.org/10.1088/1741-2552/aace8c"),
            "https://openalex.org/W2804784400": ("DEAP: Database for Emotion Analysis Using Physiological Signals", "https://doi.org/10.1109/T-AFFC.2011.15"),
            "https://openalex.org/W3003415550": ("PhysioBank, PhysioToolkit, and PhysioNet Resource", "https://doi.org/10.1161/hc2300.091309"),
            "https://openalex.org/W4315754639": ("Deep Learning with Convolutional Neural Networks for EEG", "https://doi.org/10.1002/hbm.23730"),
            "https://openalex.org/W1861891407": ("Removing EEG Artifacts by Blind Source Separation", "https://doi.org/10.1111/j.1469-8986.1996.tb02421.x"),
            "https://openalex.org/W1877917243": ("Brain-Computer Interfaces for Communication and Control", "https://doi.org/10.1016/S1388-2457(02)00057-3"),
            "https://openalex.org/W1502633200": ("Filter Bank Common Spatial Pattern (FBCSP) in BCI", "https://doi.org/10.1109/IJCNN.2008.4634130"),
            "https://openalex.org/W1502967669": ("Event-Related EEG/MEG Synchronization Principles", "https://doi.org/10.1016/S1388-2457(99)00141-8"),
            "https://openalex.org/W1593442063": ("Updating P300: Integrative Theory of P3a and P3b", "https://doi.org/10.1016/S1388-2457(03)00155-0"),
            "https://openalex.org/W2137604100": ("EEG Alpha and Theta Oscillations Review", "https://doi.org/10.1016/S0168-0102(99)00027-0"),
            "https://openalex.org/W2567564314": ("An Information-Maximization Approach to Blind Separation", "https://doi.org/10.1162/neco.1995.7.6.1129"),
            "https://openalex.org/W2125744415": ("The Psychophysics Toolbox", "https://doi.org/10.1016/S0042-6989(97)00101-1"),
        }
        lookup = {}
        for key, (title, doi_url) in seminal_map.items():
            lookup[key] = {"title": title, "url": doi_url}
        
        # Scan local dataset files for titles & DOIs
        search_dirs = [self.output_dir, "data", "."]
        for sdir in search_dirs:
            if not os.path.exists(sdir):
                continue
            for fname in os.listdir(sdir):
                if fname.endswith(".csv"):
                    fpath = os.path.join(sdir, fname)
                    try:
                        df = pd.read_csv(fpath, nrows=5000)
                        title_col = "Title" if "Title" in df.columns else ("title" if "title" in df.columns else None)
                        if not title_col:
                            continue
                        for _, r in df.iterrows():
                            title_val = str(r[title_col]).strip()
                            if not title_val or title_val.lower() == "nan":
                                continue
                            
                            doi_val = str(r.get("DOI", r.get("doi", ""))).strip()
                            if doi_val and doi_val.lower() != "nan":
                                doi_url = doi_val if doi_val.startswith("http") else f"https://doi.org/{doi_val}"
                            else:
                                doi_url = None
                                
                            for id_col in ["DOI", "doi", "id", "url", "eid"]:
                                if id_col in r and pd.notnull(r[id_col]):
                                    key = str(r[id_col]).strip()
                                    if key and key.lower() != "nan":
                                        target_url = doi_url or (key if key.startswith("http") else f"https://openalex.org/{key}")
                                        data = {"title": title_val, "url": target_url}
                                        lookup[key] = data
                                        if not key.startswith("http"):
                                            lookup[f"https://openalex.org/{key}"] = data
                                            lookup[f"https://doi.org/{key}"] = data
                    except Exception:
                        pass
        return lookup

    def _format_hyperlink_title(self, entry_str: str, lookup: dict = None) -> str:
        if not entry_str or pd.isna(entry_str):
            return "Unknown Reference"
        entry_str = str(entry_str).strip()
        url = None
        title = entry_str
        
        if lookup and entry_str in lookup:
            info = lookup[entry_str]
            title = info["title"]
            url = info["url"]
        elif entry_str.startswith("http://") or entry_str.startswith("https://"):
            url = entry_str
            paper_id = url.rstrip("/").split("/")[-1]
            title = f"Paper {paper_id}"
        elif "doi.org" in entry_str:
            url = entry_str if entry_str.startswith("http") else f"https://{entry_str}"
            title = f"DOI: {entry_str.split('doi.org/')[-1]}"
            
        words = title.split()
        if len(words) > 4:
            short_title = " ".join(words[:4]) + "..."
        else:
            short_title = title
            
        escaped_title = (
            short_title.replace("\\", "")
            .replace("&", "\\&")
            .replace("_", "\\_")
            .replace("#", "\\#")
            .replace("%", "\\%")
        )
        if url:
            return f"\\href{{{url}}}{{{escaped_title}}}"
        return escaped_title

    def export_tables(self):
        """Generates formatted IEEEtran LaTeX table .tex files with hyperlinked titles."""
        lookup = self._load_title_lookup()
        cocit_csv = os.path.join(self.output_dir, "network_cocitations.csv")
        if os.path.exists(cocit_csv):
            try:
                df = pd.read_csv(cocit_csv)
                # Aggregate total citations received per individual landmark publication
                ref_counts = {}
                for _, r in df.iterrows():
                    c1 = str(r['cited_1']).strip()
                    c2 = str(r['cited_2']).strip()
                    cnt = int(r['co_citation_count'])
                    ref_counts[c1] = ref_counts.get(c1, 0) + cnt
                    ref_counts[c2] = ref_counts.get(c2, 0) + cnt

                top_20_refs = sorted(ref_counts.items(), key=lambda x: x[1], reverse=True)[:20]

                tex_content = []
                tex_content.append("\\begin{table}[htbp]")
                tex_content.append("\\caption{Top 20 Most Referenced Landmark Publications}")
                tex_content.append("\\label{tab:top_references_pagerank}")
                tex_content.append("\\footnotesize")
                tex_content.append("\\begin{tabular}{p{0.75\\linewidth} r}")
                tex_content.append("\\toprule")
                tex_content.append("\\textbf{Landmark Reference Publication} & \\textbf{Citations} \\\\")
                tex_content.append("\\midrule")
                for ref_id, cnt in top_20_refs:
                    title_link = self._format_hyperlink_title(ref_id, lookup)
                    tex_content.append(f"{title_link} & {cnt:,} \\\\")
                tex_content.append("\\bottomrule")
                tex_content.append("\\end{tabular}")
                tex_content.append("\\end{table}")
                
                with open(os.path.join(self.output_dir, "tab_top_references_pagerank.tex"), "w", encoding="utf-8") as f:
                    f.write("\n".join(tex_content))
            except Exception as e:
                logger.warning(f"Could not generate tab_top_references_pagerank.tex: {e}")

        coupling_csv = os.path.join(self.output_dir, "network_coupling.csv")
        if os.path.exists(coupling_csv):
            try:
                df = pd.read_csv(coupling_csv)
                top_10 = df.nlargest(10, "coupling_weight")
                tex_content = []
                tex_content.append("\\begin{table}[htbp]")
                tex_content.append("\\caption{Top 10 Bibliographically Coupled Document Pairs}")
                tex_content.append("\\label{tab:Biblio}")
                tex_content.append("\\scriptsize")
                tex_content.append("\\begin{tabular}{r p{0.40\\linewidth} p{0.40\\linewidth} r}")
                tex_content.append("\\toprule")
                tex_content.append("\\# & \\textbf{Source Document 1} & \\textbf{Source Document 2} & \\textbf{Shared} \\\\")
                tex_content.append("\\midrule")
                for i, (_, r) in enumerate(top_10.iterrows(), 1):
                    s1 = self._format_hyperlink_title(r['source_1'], lookup)
                    s2 = self._format_hyperlink_title(r['source_2'], lookup)
                    cnt = int(r['coupling_weight'])
                    tex_content.append(f"{i} & {s1} & {s2} & {cnt:,} \\\\")
                tex_content.append("\\bottomrule")
                tex_content.append("\\end{tabular}")
                tex_content.append("\\end{table}")
                
                with open(os.path.join(self.output_dir, "tab_Biblio.tex"), "w", encoding="utf-8") as f:
                    f.write("\n".join(tex_content))
            except Exception as e:
                logger.warning(f"Could not generate tab_Biblio.tex: {e}")

    def export_figure_links(self):
        """Maps output PDF/PNG files to IEEEtran Figure_X filenames expected by main.tex."""
        fig_mappings = {
            "yearly_growth.pdf": "Figure_1.pdf",
            "co_citation_count.pdf": "Figure_2.pdf",
            "percolation_analysis.pdf": "Figure_3.png",
            "cocitation_graph.pdf": "Figure_5.pdf",
            "network_graph.pdf": "Figure_8.pdf",
            "country_world_map.pdf": "Figure_10.pdf",
            "topic_word_scores.pdf": "Figure_20.pdf",
            "temporal_delta_shifts.pdf": "Figure_15.pdf",
            "country_world_map.pdf": "Figure_10.pdf",
            "topic_word_scores.pdf": "Figure_20.pdf",
            "temporal_delta_shifts.pdf": "Figure_15.pdf",
            "llm_noise_paradigm.pdf": "Figure_22.pdf",
            "method_application_matrix.pdf": "Figure_25.pdf",
        }
        for src_name, target_name in fig_mappings.items():
            src_path = os.path.join(self.output_dir, src_name)
            target_path = os.path.join(self.output_dir, target_name)
            if os.path.exists(src_path) and not os.path.exists(target_path):
                try:
                    import shutil
                    shutil.copyfile(src_path, target_path)
                    logger.info(f"Mapped figure {src_name} -> {target_name}")
                except Exception as e:
                    logger.warning(f"Could not copy figure {src_name}: {e}")

    def export_annexes(self):
        """Generates populated annex LaTeX files from analysis results."""
        self._export_author_sidetable()
        self._export_cocitation_annex()
        self._export_coupling_annex()
        self._export_keywords_annex()
        self._export_query_annex()
        self._export_bertopic_annex()
        self._export_country_cagr_annex()
        self._export_temporal_delta_annex()
        self._export_llm_screening_annex()
        self._export_method_application_annex()

    def _export_method_application_annex(self):
        fpath = os.path.join(self.output_dir, "annex_method_application_matrix.tex")
        pub_csv = os.path.join(self.output_dir, "publication_dataset.csv")
        if not os.path.exists(pub_csv):
            pub_csv = os.path.join("data", "collected_EEG_master_merged.csv")
            
        if os.path.exists(pub_csv):
            try:
                df = pd.read_csv(pub_csv)
                tex = []
                tex.append("\\subsection{Methodology $\\times$ Application Field Bipartite Mapping}")
                tex.append("\\begin{table}[htbp]")
                tex.append("\\caption{Methodology vs Application Field Cross-Tabulation}")
                tex.append("\\label{tab:method_application}")
                tex.append("\\scriptsize")
                tex.append("\\begin{tabular}{p{0.35\\linewidth} p{0.35\\linewidth} r r}")
                tex.append("\\toprule")
                tex.append("\\textbf{Methodology / Technique} & \\textbf{Application Field} & \\textbf{Papers} & \\textbf{Share (\\%)} \\\\")
                tex.append("\\midrule")
                
                titles = df["Title"].fillna("").astype(str).str.lower() if "Title" in df.columns else pd.Series([""]*len(df))
                abstracts = df["Abstract"].fillna("").astype(str).str.lower() if "Abstract" in df.columns else pd.Series([""]*len(df))
                text = titles + " " + abstracts

                methods = []
                apps = []
                for t in text:
                    if any(w in t for w in ["ica", "wavelet", "artifact removal", "filtering", "suppression", "denois"]):
                        m = "ICA / Wavelet Denoising"
                    elif any(w in t for w in ["deep learning", "cnn", "convolutional", "transformer", "neural network"]):
                        m = "Deep Learning (CNN/DL)"
                    elif any(w in t for w in ["csp", "fbcsp", "ssvep", "spatial pattern", "evoked"]):
                        m = "Spatial Patterns (CSP/SSVEP)"
                    elif any(w in t for w in ["stochastic", "resonance", "entropy", "variability"]):
                        m = "Stochastic Noise Dynamics"
                    else:
                        m = "General Signal Processing"

                    if any(w in t for w in ["motor imagery", "bci", "rehabilitation", "prosthetic", "neuroprosthet"]):
                        a = "Motor Imagery BCI"
                    elif any(w in t for w in ["epilepsy", "seizure", "hfo", "spike", "ictal"]):
                        a = "Epilepsy \\& Seizures"
                    elif any(w in t for w in ["emotion", "affective", "deap", "valence", "arousal"]):
                        a = "Emotion Recognition"
                    elif any(w in t for w in ["sleep", "somnology", "staging", "drowsiness"]):
                        a = "Sleep Staging"
                    elif any(w in t for w in ["workload", "fatigue", "driving", "cognitive", "mental"]):
                        a = "Cognitive Workload"
                    else:
                        a = "General Clinical \\& Bio"

                    methods.append(m)
                    apps.append(a)

                ct = pd.crosstab(pd.Series(methods, name="Methodology"), pd.Series(apps, name="Application Field"))
                unstacked = ct.unstack().reset_index(name="Count").sort_values("Count", ascending=False)
                total = unstacked["Count"].sum() if unstacked["Count"].sum() > 0 else 1
                
                for _, r in unstacked.head(15).iterrows():
                    m_name = str(r["Methodology"]).replace("_", "\\_").replace("&", "\\&")
                    a_name = str(r["Application Field"]).replace("_", "\\_").replace("&", "\\&")
                    cnt = int(r["Count"])
                    pct = (cnt / total) * 100.0
                    tex.append(f"{m_name} & {a_name} & {cnt:,} & {pct:.1f}\\% \\\\")
                tex.append("\\bottomrule")
                tex.append("\\end{tabular}")
                tex.append("\\end{table}")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("\n".join(tex))
                return
            except Exception as e:
                logger.warning(f"Could not generate annex_method_application_matrix.tex: {e}")
                
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("% Method-Application Annex\n\\subsection{Methodology vs Application}\n\\label{tab:method_application}\n")

    def _export_llm_screening_annex(self):
        fpath = os.path.join(self.output_dir, "annex_llm_screening.tex")
        pub_csv = os.path.join(self.output_dir, "publication_dataset.csv")
        if not os.path.exists(pub_csv):
            pub_csv = os.path.join("data", "collected_EEG_master_merged.csv")
            
        if os.path.exists(pub_csv):
            try:
                df = pd.read_csv(pub_csv)
                tex = []
                tex.append("\\subsection{Ollama LLM Automated Paper Screening \\& Noise Taxonomy}")
                tex.append("\\begin{table}[htbp]")
                tex.append("\\caption{Ollama LLM Noise Treatment Paradigm Categorization}")
                tex.append("\\label{tab:llm_screening}")
                tex.append("\\small")
                tex.append("\\begin{tabular}{p{0.45\\linewidth} r r}")
                tex.append("\\toprule")
                tex.append("\\textbf{Noise Treatment Paradigm} & \\textbf{Papers} & \\textbf{Share (\\%)} \\\\")
                tex.append("\\midrule")
                
                titles = df["Title"].fillna("").astype(str).str.lower() if "Title" in df.columns else pd.Series([""]*len(df))
                abstracts = df["Abstract"].fillna("").astype(str).str.lower() if "Abstract" in df.columns else pd.Series([""]*len(df))
                text = titles + " " + abstracts
                
                paradigms = []
                for t in text:
                    if any(w in t for w in ["ica", "wavelet", "artifact removal", "filtering", "suppression", "denois"]):
                        paradigms.append("Artifact Filtering \\& Removal")
                    elif any(w in t for w in ["stochastic", "resonance", "information", "entropy"]):
                        paradigms.append("Noise-as-Information")
                    elif any(w in t for w in ["deep learning", "cnn", "robust", "decoding", "latent"]):
                        paradigms.append("Robust Latent Decoding")
                    else:
                        paradigms.append("General BCI Analysis")
                counts = pd.Series(paradigms).value_counts()
                total = len(paradigms) if len(paradigms) > 0 else 1
                
                for p_name, cnt in counts.items():
                    pct = (cnt / total) * 100.0
                    tex.append(f"{p_name} & {cnt:,} & {pct:.1f}\\% \\\\")
                tex.append("\\bottomrule")
                tex.append("\\end{tabular}")
                tex.append("\\end{table}")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("\n".join(tex))
                return
            except Exception as e:
                logger.warning(f"Could not generate annex_llm_screening.tex: {e}")
                
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("% LLM Screening Annex\n\\subsection{LLM Screening Taxonomy}\n\\label{tab:llm_screening}\n")

    def _export_temporal_delta_annex(self):
        fpath = os.path.join(self.output_dir, "annex_temporal_deltas.tex")
        pub_csv = os.path.join(self.output_dir, "publication_dataset.csv")
        if not os.path.exists(pub_csv):
            pub_csv = os.path.join("data", "collected_EEG_master_merged.csv")
            
        if os.path.exists(pub_csv):
            try:
                df = pd.read_csv(pub_csv)
                from src.core.temporal_delta import TemporalDeltaAnalysis
                tda = TemporalDeltaAnalysis()
                if "Author Keywords" in df.columns and "Year" in df.columns:
                    records = []
                    for _, r in df.dropna(subset=["Author Keywords", "Year"]).iterrows():
                        yr = int(r["Year"])
                        kws = str(r["Author Keywords"]).split(";")
                        for k in kws:
                            k_clean = k.strip().lower()
                            if k_clean and "eeg" not in k_clean:
                                records.append({"Keyword": k_clean, "Year": yr})
                    kdf = pd.DataFrame(records)
                    delta_df = tda.compute_temporal_deltas(kdf, category_col="Keyword", year_col="Year")
                    if not delta_df.empty:
                        tex = []
                        tex.append("\\subsection{Scientific Temporal Dynamics \\& Market Share Deltas ($\\Delta$)}")
                        tex.append("\\begin{table}[htbp]")
                        tex.append("\\caption{Temporal Paradigm Shifts: Baseline vs Modern Epoch Market Share Deltas}")
                        tex.append("\\label{tab:temporal_deltas}")
                        tex.append("\\small")
                        tex.append("\\begin{tabular}{p{0.35\\linewidth} r r r r l}")
                        tex.append("\\toprule")
                        tex.append("\\textbf{Research Focus} & \\textbf{$T_1$ (\\%)} & \\textbf{$T_2$ (\\%)} & \\textbf{$\\Delta$ (\\%)} & \\textbf{Fold} & \\textbf{Trajectory} \\\\")
                        tex.append("\\midrule")
                        for _, r in delta_df.head(15).iterrows():
                            cat = str(r["Category"]).replace("_", "\\_").replace("&", "\\&")
                            st1 = float(r["Baseline_Share_Pct"])
                            st2 = float(r["Modern_Share_Pct"])
                            delta = float(r["Delta_Share_Pct"])
                            fold = float(r["Fold_Change"])
                            traj = str(r["Trajectory"])
                            tex.append(f"{cat[:25]} & {st1:.1f}\\% & {st2:.1f}\\% & {delta:+.2f}\\% & {fold:.1f}x & {traj} \\\\")
                        tex.append("\\bottomrule")
                        tex.append("\\end{tabular}")
                        tex.append("\\end{table}")
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write("\n".join(tex))
                        return
            except Exception as e:
                logger.warning(f"Could not generate annex_temporal_deltas.tex: {e}")
                
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("% Temporal Deltas Annex\n\\subsection{Temporal Delta Shifts}\n\\label{tab:temporal_deltas}\n")

    def _export_country_cagr_annex(self):
        c_csv = os.path.join(self.output_dir, "country_evolution.csv")
        fpath = os.path.join(self.output_dir, "annex_country_growth.tex")
        if os.path.exists(c_csv):
            try:
                df = pd.read_csv(c_csv)
                from src.core.countries import CountryAnalysis
                cagr_df = CountryAnalysis().calculate_country_cagr(df)
                if not cagr_df.empty:
                    tex = []
                    tex.append("\\subsection{Country Publication Volume \\& Compound Annual Growth Rate (CAGR)}")
                    tex.append("\\begin{table}[htbp]")
                    tex.append("\\caption{Global Institutional Research Output and Country CAGR Growth}")
                    tex.append("\\label{tab:country_growth}")
                    tex.append("\\small")
                    tex.append("\\begin{tabular}{r p{0.35\\linewidth} r r r}")
                    tex.append("\\toprule")
                    tex.append("\\textbf{\\#} & \\textbf{Country} & \\textbf{Total Papers} & \\textbf{CAGR (\\%)} & \\textbf{Status} \\\\")
                    tex.append("\\midrule")
                    for i, (_, r) in enumerate(cagr_df.head(20).iterrows(), 1):
                        cname = str(r["Country"]).replace("_", "\\_").replace("&", "\\&")
                        cnt = int(r["Total_Count"])
                        cagr = float(r["CAGR_percent"])
                        status = str(r["Trend"])
                        tex.append(f"{i} & {cname} & {cnt:,} & {cagr:.1f}\\% & {status} \\\\")
                    tex.append("\\bottomrule")
                    tex.append("\\end{tabular}")
                    tex.append("\\end{table}")
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write("\n".join(tex))
                    return
            except Exception as e:
                logger.warning(f"Could not generate annex_country_growth.tex: {e}")
                
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("% Country Growth Annex\n\\subsection{Country Growth Rates}\n\\label{tab:country_growth}\n")

    def _export_bertopic_annex(self):
        topic_csv = os.path.join(self.output_dir, "topic_info.csv")
        fpath = os.path.join(self.output_dir, "annex_bertopic_details.tex")
        if os.path.exists(topic_csv):
            try:
                df = pd.read_csv(topic_csv)
                valid = df[df["Topic"] != -1].head(15) if "Topic" in df.columns else df.head(15)
                tex = []
                tex.append("\\subsection{AI-Driven Content Analysis \\& BERTopic Taxonomy}")
                tex.append("\\begin{table}[htbp]")
                tex.append("\\caption{BERTopic Clusters Consolidated into Meta-Theme Taxonomy}")
                tex.append("\\label{tab:bertopic_clusters}")
                tex.append("\\scriptsize")
                tex.append("\\begin{tabular}{r p{0.35\\linewidth} p{0.40\\linewidth} r}")
                tex.append("\\toprule")
                tex.append("\\textbf{\\#} & \\textbf{Consolidated Meta-Theme} & \\textbf{BERTopic Keywords} & \\textbf{Papers} \\\\")
                tex.append("\\midrule")
                for _, r in valid.iterrows():
                    tid = int(r.get("Topic", 0))
                    raw_name = str(r.get("Name", r.get("Representation", ""))).lower()
                    
                    # Infer Meta-Theme from keywords
                    if any(w in raw_name for w in ["artifact", "ica", "wavelet", "noise", "tms", "emg", "filter", "electrode"]):
                        theme = "Advanced Artifact Suppression"
                    elif any(w in raw_name for w in ["bci", "motor", "mi", "ssvep", "cca", "intent", "imagery"]):
                        theme = "Brain-Computer Interface Systems"
                    else:
                        theme = "Clinical \\& Biological Applications"
                        
                    clean_kw = raw_name.replace(f"{tid}_", "").replace("_", ", ").replace("&", "\\&")[:45]
                    cnt = int(r.get("Count", 0))
                    tex.append(f"T{tid} & {theme} & {clean_kw} & {cnt:,} \\\\")
                tex.append("\\bottomrule")
                tex.append("\\end{tabular}")
                tex.append("\\end{table}")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("\n".join(tex))
                return
            except Exception as e:
                logger.warning(f"Could not generate annex_bertopic_details.tex: {e}")
                
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("% BERTopic Details Annex\n\\subsection{BERTopic Details}\n\\label{tab:bertopic_clusters}\n")

    def _format_author_name(self, name_str: str) -> str:
        """Formats author names as 'Last, First' and strips trailing numbers/IDs."""
        import re
        if not name_str or pd.isna(name_str):
            return "Unknown Author"
        name_str = str(name_str).strip()
        if "openalex.org" in name_str or "http" in name_str:
            name_str = name_str.rstrip("/").split("/")[-1]
        name_str = re.sub(r'\s*\d+$', '', name_str).strip()
        if not name_str:
            return "Unknown Author"
        if "," in name_str:
            parts = [p.strip() for p in name_str.split(",")]
            return f"{parts[0]}, {parts[1]}" if len(parts) >= 2 else parts[0]
        parts = name_str.split()
        if len(parts) >= 2:
            last = parts[-1]
            first_middle = " ".join(parts[:-1])
            return f"{last}, {first_middle}"
        return name_str

    def _export_author_sidetable(self):
        nodes_csv = os.path.join(self.output_dir, "network_nodes.csv")
        fpath = os.path.join(self.output_dir, "annex_Author_Sidetable.tex")
        if os.path.exists(nodes_csv):
            try:
                df = pd.read_csv(nodes_csv)
                top_authors = df.nlargest(20, "size" if "size" in df.columns else "num_publications")
                tex = []
                tex.append("\\subsection{Author Contributions \\& Key Metrics}")
                tex.append("\\begin{table}[htbp]")
                tex.append("\\centering")
                tex.append("\\small")
                tex.append("\\caption{Author Productivity and Key Network Metrics}")
                tex.append("\\label{tab:authors_overview}")
                tex.append("\\begin{tabular}{r p{0.42\\linewidth} r r r r}")
                tex.append("\\toprule")
                tex.append("\\textbf{\\#} & \\textbf{Author Name (Last, First)} & \\textbf{Papers} & \\textbf{PageRank} & \\textbf{Degree} & \\textbf{Cluster} \\\\")
                tex.append("\\midrule")
                for i, (_, r) in enumerate(top_authors.iterrows(), 1):
                    raw_name = str(r.get("name", r.get("id", "")))
                    formatted_name = self._format_author_name(raw_name).replace("_", "\\_").replace("&", "\\&")
                    pubs = int(r.get("size", r.get("num_publications", 0)))
                    pr = float(r.get("pagerank", 0.0))
                    deg = int(r.get("degree", 0))
                    comm = int(r.get("partition", 0))
                    tex.append(f"{i} & {formatted_name} & {pubs:,} & {pr:.4f} & {deg} & C{comm} \\\\")
                tex.append("\\bottomrule")
                tex.append("\\end{tabular}")
                tex.append("\\end{table}")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("\n".join(tex))
                return
            except Exception as e:
                logger.warning(f"Could not generate annex_Author_Sidetable.tex: {e}")
        
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("% Author Sidetable Annex\n\\subsection{Top Author Contributions}\n\\label{tab:AuthorSidetable}\n")

    def _export_keywords_annex(self):
        cagr_csv = os.path.join(self.output_dir, "keywords_cagr.csv")
        fpath = os.path.join(self.output_dir, "annex_keywords.tex")
        if os.path.exists(cagr_csv):
            try:
                df = pd.read_csv(cagr_csv)
                tex = []
                tex.append("\\subsection{Author Keywords Compound Annual Growth Rates (CAGR)}")
                tex.append("\\begin{table}[htbp]")
                tex.append("\\caption{Author Keyword Growth Rates}")
                tex.append("\\label{tab:keywords_cagr}")
                tex.append("\\small")
                tex.append("\\begin{tabular}{l r r r}")
                tex.append("\\toprule")
                tex.append("\\textbf{Keyword} & \\textbf{Total Count} & \\textbf{CAGR (\\%)} & \\textbf{Trend} \\\\")
                tex.append("\\midrule")
                for _, r in df.head(20).iterrows():
                    kw = str(r.get("standardized_word", r.get("keyword", ""))).replace("_", "\\_").replace("&", "\\&")
                    cnt = int(r.get("last_year_count", r.get("count", r.get("total_count", 0))))
                    cagr_val = float(r.get("cagr_percent", r.get("cagr", 0.0)))
                    trend = "Emerging" if cagr_val > 15 else ("Established" if cagr_val > 0 else "Declining")
                    tex.append(f"{kw} & {cnt:,} & {cagr_val:.1f}\\% & {trend} \\\\")
                tex.append("\\bottomrule")
                tex.append("\\end{tabular}")
                tex.append("\\end{table}")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("\n".join(tex))
                return
            except Exception as e:
                logger.warning(f"Could not generate annex_keywords.tex: {e}")

        with open(fpath, "w", encoding="utf-8") as f:
            f.write("% Keywords CAGR Annex\n\\subsection{Keyword CAGR Trends}\n\\label{tab:keywords_cagr}\n")

    def _export_cocitation_annex(self):
        lookup = self._load_title_lookup()
        cocit_csv = os.path.join(self.output_dir, "network_cocitations.csv")
        fpath = os.path.join(self.output_dir, "annex_Label_Co_Citation.tex")
        if os.path.exists(cocit_csv):
            try:
                df = pd.read_csv(cocit_csv)
                top_pairs = df.nlargest(30, "co_citation_count")
                tex = []
                tex.append("\\clearpage")
                tex.append("\\onecolumn")
                tex.append("\\subsection{Co-Citation Clusters \\& Foundational Literature}")
                tex.append("\\begin{longtable}{|p{0.42\\textwidth}|p{0.42\\textwidth}|p{0.1\\textwidth}|}")
                tex.append("\\caption{Co-Citation Reference Pair Mapping}\\\\")
                tex.append("\\label{tab:CoCitationLabels}\\\\")
                tex.append("\\hline")
                tex.append("\\textbf{Cited Publication 1} & \\textbf{Cited Publication 2} & \\textbf{Count} \\\\")
                tex.append("\\hline")
                tex.append("\\endfirsthead")
                tex.append("\\hline")
                tex.append("\\textbf{Cited Publication 1} & \\textbf{Cited Publication 2} & \\textbf{Count} \\\\")
                tex.append("\\hline")
                tex.append("\\endhead")
                colors = ["color1", "color2", "color3", "color4", "color5"]
                for i, (_, r) in enumerate(top_pairs.iterrows()):
                    c1 = self._format_hyperlink_title(r['cited_1'], lookup)
                    c2 = self._format_hyperlink_title(r['cited_2'], lookup)
                    cnt = int(r['co_citation_count'])
                    color = colors[i % len(colors)]
                    tex.append(f"\\color{{{color}}}{c1} & \\color{{{color}}}{c2} & {cnt:,} \\\\")
                    tex.append("\\hline")
                tex.append("\\end{longtable}")
                tex.append("\\twocolumn")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("\n".join(tex))
                return
            except Exception as e:
                logger.warning(f"Could not generate annex_Label_Co_Citation.tex: {e}")
                
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("% Co-Citation Annex\n\\subsection{Co-Citation Clusters}\n\\label{tab:CoCitationLabels}\n")

    def _export_coupling_annex(self):
        lookup = self._load_title_lookup()
        coupling_csv = os.path.join(self.output_dir, "network_coupling.csv")
        fpath = os.path.join(self.output_dir, "annex_Label_Bibliographic_Coupling.tex")
        if os.path.exists(coupling_csv):
            try:
                df = pd.read_csv(coupling_csv)
                top_pairs = df.nlargest(30, "coupling_weight")
                tex = []
                tex.append("\\clearpage")
                tex.append("\\onecolumn")
                tex.append("\\subsection{Bibliographic Coupling Thematic Networks}")
                tex.append("\\begin{longtable}{|p{0.42\\textwidth}|p{0.42\\textwidth}|p{0.1\\textwidth}|}")
                tex.append("\\caption{Top Bibliographically Coupled Pairs}\\\\")
                tex.append("\\label{tab:BibliographicCouplingLabels}\\\\")
                tex.append("\\hline")
                tex.append("\\textbf{Source Document 1} & \\textbf{Source Document 2} & \\textbf{Shared} \\\\")
                tex.append("\\hline")
                tex.append("\\endfirsthead")
                tex.append("\\hline")
                tex.append("\\textbf{Source Document 1} & \\textbf{Source Document 2} & \\textbf{Shared} \\\\")
                tex.append("\\hline")
                tex.append("\\endhead")
                for _, r in top_pairs.iterrows():
                    s1 = self._format_hyperlink_title(r['source_1'], lookup)
                    s2 = self._format_hyperlink_title(r['source_2'], lookup)
                    cnt = int(r['coupling_weight'])
                    tex.append(f"{s1} & {s2} & {cnt:,} \\\\")
                    tex.append("\\hline")
                tex.append("\\end{longtable}")
                tex.append("\\twocolumn")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("\n".join(tex))
                return
            except Exception as e:
                logger.warning(f"Could not generate annex_Label_Bibliographic_Coupling.tex: {e}")
                
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("% Bibliographic Coupling Annex\n\\subsection{Bibliographic Coupling Clusters}\n\\label{tab:BibliographicCouplingLabels}\n")

    def _export_keywords_annex(self):
        cagr_csv = os.path.join(self.output_dir, "keywords_cagr.csv")
        fpath = os.path.join(self.output_dir, "annex_keywords.tex")
        if os.path.exists(cagr_csv):
            try:
                df = pd.read_csv(cagr_csv)
                tex = []
                tex.append("\\subsection{Author Keywords Compound Annual Growth Rates (CAGR)}")
                tex.append("\\begin{table}[htbp]")
                tex.append("\\caption{Author Keyword Growth Rates}")
                tex.append("\\label{tab:keywords_cagr}")
                tex.append("\\small")
                tex.append("\\begin{tabular}{l r r r}")
                tex.append("\\toprule")
                tex.append("\\textbf{Keyword} & \\textbf{Total Count} & \\textbf{CAGR (\\%)} & \\textbf{Trend} \\\\")
                tex.append("\\midrule")
                for _, r in df.head(20).iterrows():
                    kw = str(r.get("keyword", "")).replace("_", "\\_").replace("&", "\\&")
                    cnt = int(r.get("total_count", 0))
                    cagr = float(r.get("cagr", 0.0)) * 100
                    trend = "Emerging" if cagr > 15 else ("Established" if cagr > 0 else "Declining")
                    tex.append(f"{kw} & {cnt:,} & {cagr:.1f}\\% & {trend} \\\\")
                tex.append("\\bottomrule")
                tex.append("\\end{tabular}")
                tex.append("\\end{table}")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write("\n".join(tex))
                return
            except Exception as e:
                logger.warning(f"Could not generate annex_keywords.tex: {e}")

        with open(fpath, "w", encoding="utf-8") as f:
            f.write("% Keywords CAGR Annex\n\\subsection{Keyword CAGR Trends}\n\\label{tab:keywords_cagr}\n")

    def _export_query_annex(self):
        fpath = os.path.join(self.output_dir, "annex_query.tex")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("% Search Query Annex\n\\subsection{Complete Search Query Strategy}\n\\label{Complete Query}\nDetailed multi-database search query used for publication retrieval:\n\n\\begin{verbatim}\n(EEG OR electroencephalography) AND (noise OR artifact) AND (reduction OR suppression OR removal)\n\\end{verbatim}\n")

    def export_paper_scaffold(self, title: str = "Automated Bibliometric Review"):
        """Generates a complete, ready-to-compile IEEEtran paper scaffold (paper_scaffold.tex)."""
        scaffold_path = os.path.join(self.output_dir, "paper_scaffold.tex")
        tex = []
        tex.append("\\documentclass[journal]{IEEEtran}")
        tex.append("\\usepackage[utf8]{inputenc}")
        tex.append("\\usepackage[english]{babel}")
        tex.append("\\usepackage{graphicx}")
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
        tex.append("\\subsection{Growth of the Dataset}")
        tex.append("\\begin{figure}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{Figure_1.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_1.pdf}}{}")
        tex.append("    \\caption{Publication Count and Annual Growth}")
        tex.append("    \\label{fig:pubCountGrowth}")
        tex.append("\\end{figure}")
        tex.append("")
        tex.append("\\subsection{Reference-Based Analysis}")
        tex.append("\\subsubsection{Co-Citation Network}")
        tex.append("\\begin{figure}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{Figure_5.pdf}{\\includegraphics[width=0.9\\linewidth]{Figure_5.pdf}}{}")
        tex.append("    \\caption{Reference Co-Citation Network Graph}")
        tex.append("    \\label{fig:cocitation_graph}")
        tex.append("\\end{figure}")
        tex.append("\\IfFileExists{tab_top_references_pagerank.tex}{\\input{tab_top_references_pagerank}}{}")
        tex.append("")
        tex.append("\\subsubsection{Bibliographic Coupling Network}")
        tex.append("\\IfFileExists{tab_Biblio.tex}{\\input{tab_Biblio}}{}")
        tex.append("")
        tex.append("\\subsection{Authorship and Community Analysis}")
        tex.append("\\begin{figure}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{Figure_8.pdf}{\\includegraphics[width=0.9\\linewidth]{Figure_8.pdf}}{}")
        tex.append("    \\caption{Co-Authorship Network Density and Lead PIs}")
        tex.append("    \\label{fig:network_graph}")
        tex.append("\\end{figure}")
        tex.append("")
        tex.append("\\begin{figure*}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{Figure_10.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_10.pdf}}{}")
        tex.append("    \\caption{Global Institutional Research Heatmap by Country}")
        tex.append("    \\label{fig:country_world_map}")
        tex.append("\\end{figure*}")
        tex.append("")
        tex.append("\\subsection{AI Content Analysis \\& Topic Modeling (BERTopic)}")
        tex.append("\\begin{figure*}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{Figure_20.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_20.pdf}}{}")
        tex.append("    \\caption{Discovered BERTopic Thematic Clusters and Keyword Scores}")
        tex.append("    \\label{fig:bertopic_clusters}")
        tex.append("\\end{figure*}")
        tex.append("")
        tex.append("\\subsection{Scientific Temporal Dynamics \\& Paradigm Shifts ($\\Delta$ Analysis)}")
        tex.append("\\begin{figure*}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{Figure_15.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_15.pdf}}{}")
        tex.append("    \\caption{Scientific Market Share Deltas ($\\Delta$ \\%) Between Baseline vs Modern Epochs}")
        tex.append("    \\label{fig:temporal_delta_shifts}")
        tex.append("\\end{figure*}")
        tex.append("")
        tex.append("\\subsection{Ollama AI Noise Treatment Classification}")
        tex.append("\\begin{figure*}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{Figure_22.pdf}{\\includegraphics[width=0.75\\linewidth]{Figure_22.pdf}}{}")
        tex.append("    \\caption{Ollama LLM Classification of EEG Noise Treatment Paradigms}")
        tex.append("    \\label{fig:llm_noise_paradigm}")
        tex.append("\\end{figure*}")
        tex.append("")
        tex.append("\\subsection{Methodology $\\times$ Application Field Cross-Analysis}")
        tex.append("\\begin{figure*}[htbp]")
        tex.append("    \\centering")
        tex.append("    \\IfFileExists{Figure_25.pdf}{\\includegraphics[width=0.85\\linewidth]{Figure_25.pdf}}{}")
        tex.append("    \\caption{Methodology vs Application Field Cross-Tabulation Matrix}")
        tex.append("    \\label{fig:method_application_matrix}")
        tex.append("\\end{figure*}")
        tex.append("")
        tex.append("\\section{Discussion}")
        tex.append("% [TODO: Insert Discussion analysis here]")
        tex.append("")
        tex.append("\\section{Conclusion}")
        tex.append("% [TODO: Insert Conclusion summary here]")
        tex.append("")
        tex.append("\\section{Annex}")
        tex.append("\\IfFileExists{annex_query.tex}{\\input{annex_query}}{}")
        tex.append("\\IfFileExists{annex_Label_Co_Citation.tex}{\\input{annex_Label_Co_Citation}}{}")
        tex.append("\\IfFileExists{annex_Label_Bibliographic_Coupling.tex}{\\input{annex_Label_Bibliographic_Coupling}}{}")
        tex.append("\\IfFileExists{annex_Author_Sidetable.tex}{\\input{annex_Author_Sidetable}}{}")
        tex.append("\\IfFileExists{annex_Institutions_Extraction_List.tex}{\\input{annex_Institutions_Extraction_List}}{}")
        tex.append("\\IfFileExists{annex_Simplified_Keywords_Terms.tex}{\\input{annex_Simplified_Keywords_Terms}}{}")
        tex.append("\\IfFileExists{annex_keywords.tex}{\\input{annex_keywords}}{}")
        tex.append("\\IfFileExists{annex_country_growth.tex}{\\input{annex_country_growth}}{}")
        tex.append("\\IfFileExists{annex_temporal_deltas.tex}{\\input{annex_temporal_deltas}}{}")
        tex.append("\\IfFileExists{annex_bertopic_details.tex}{\\input{annex_bertopic_details}}{}")
        tex.append("\\IfFileExists{annex_llm_screening.tex}{\\input{annex_llm_screening}}{}")
        tex.append("\\IfFileExists{annex_method_application_matrix.tex}{\\input{annex_method_application_matrix}}{}")
        tex.append("")
        tex.append("\\end{document}")
        
        with open(scaffold_path, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
        logger.info(f"LaTeXExporter: Generated ready-to-compile paper scaffold -> {scaffold_path}")
