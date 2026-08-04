import os
import sys
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def build_dynamic_title_lookup(output_dir: str) -> dict:
    """Fully automated dynamic title resolution. Scans dataset CSVs and queries OpenAlex API for missing cited W... IDs."""
    lookup = {}
    cache_path = os.path.join(output_dir, "data", "openalex_title_cache.json")

    # 1. Load local JSON cache if present
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cdata = json.load(f)
                for k, v in cdata.items():
                    lookup[k.lower()] = tuple(v)
        except Exception:
            pass

    # 2. Scan local dataset CSV files
    search_files = [
        os.path.join(output_dir, "data", "publication_dataset.csv"),
        os.path.join(output_dir, "publication_dataset.csv"),
        os.path.join("data", "collected_EEG_master_merged.csv"),
    ]

    for fpath in search_files:
        if os.path.exists(fpath):
            try:
                df = pd.read_csv(fpath, usecols=lambda c: c in ["Title", "title", "DOI", "doi", "EID", "eid", "Authors", "authors", "Year", "year"])
                t_col = "Title" if "Title" in df.columns else ("title" if "title" in df.columns else None)
                if not t_col:
                    continue
                d_col = "DOI" if "DOI" in df.columns else ("doi" if "doi" in df.columns else None)
                e_col = "EID" if "EID" in df.columns else ("eid" if "eid" in df.columns else None)
                a_col = "Authors" if "Authors" in df.columns else ("authors" if "authors" in df.columns else None)
                y_col = "Year" if "Year" in df.columns else ("year" if "year" in df.columns else None)

                for _, r in df.iterrows():
                    raw_t = str(r[t_col]).strip() if pd.notnull(r[t_col]) else ""
                    if not raw_t or raw_t.lower() == "nan":
                        continue

                    words = raw_t.split()
                    short_t = " ".join(words[:4]) + ("..." if len(words) > 4 else "")
                    au_str = str(r[a_col]).strip() if a_col and pd.notnull(r[a_col]) else ""
                    yr_str = str(r[y_col]).strip() if y_col and pd.notnull(r[y_col]) else ""

                    if au_str and au_str.lower() != "nan":
                        first_au = au_str.split(";")[0].split(",")[0].strip()
                        yr_val = yr_str[:4] if yr_str and yr_str.lower() != "nan" else ""
                        memorable_name = f"{first_au} et al. ({yr_val}) {short_t}" if yr_val else f"{first_au} et al. {short_t}"
                    else:
                        memorable_name = short_t

                    doi_val = str(r[d_col]).strip() if d_col and pd.notnull(r[d_col]) else ""
                    eid_val = str(r[e_col]).strip() if e_col and pd.notnull(r[e_col]) else ""

                    if doi_val and doi_val.lower() != "nan":
                        clean_doi = doi_val.replace("https://doi.org/", "").replace("http://dx.doi.org/", "").strip().lower()
                        lookup[clean_doi] = (memorable_name, f"https://doi.org/{clean_doi}")

                    if eid_val and eid_val.lower() != "nan":
                        clean_eid = eid_val.replace("https://openalex.org/", "").strip().lower()
                        lookup[clean_eid] = (memorable_name, f"https://openalex.org/{clean_eid}")
            except Exception:
                pass

    return lookup

def fetch_and_cache_missing_openalex_titles(w_ids: list, lookup: dict, output_dir: str):
    """Automatically queries OpenAlex API in batch for missing cited W... IDs and caches results."""
    missing = [w.strip().lower() for w in w_ids if w.strip().lower() not in lookup and (w.startswith("W") or w.startswith("w"))]
    if not missing:
        return

    import urllib.request
    import json
    try:
        chunk = [m.upper() for m in missing[:50]]
        pipe_ids = "|".join(chunk)
        url = f"https://api.openalex.org/works?filter=openalex_id:{pipe_ids}&per_page=50"
        req = urllib.request.Request(url, headers={"User-Agent": "BibliometricPipeline/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            new_entries = {}
            for item in data.get("results", []):
                wid = item.get("id", "").split("/")[-1].lower()
                display_name = item.get("display_name", "")
                yr = str(item.get("publication_year", ""))
                authorships = item.get("authorships", [])
                doi = item.get("doi", f"https://openalex.org/{wid.upper()}")

                if authorships:
                    first_au = authorships[0].get("author", {}).get("display_name", "").split()[-1]
                    words = display_name.split()
                    short_t = " ".join(words[:4]) + ("..." if len(words) > 4 else "")
                    title_str = f"{first_au} et al. ({yr}) {short_t}" if yr else f"{first_au} et al. {short_t}"
                else:
                    words = display_name.split()
                    title_str = " ".join(words[:4]) + ("..." if len(words) > 4 else "")

                entry = (title_str, doi if doi else f"https://openalex.org/{wid.upper()}")
                lookup[wid] = entry
                new_entries[wid] = entry

            if new_entries:
                cache_path = os.path.join(output_dir, "data", "openalex_title_cache.json")
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                existing = {}
                if os.path.exists(cache_path):
                    try:
                        with open(cache_path, "r", encoding="utf-8") as f:
                            existing = json.load(f)
                    except Exception:
                        pass
                existing.update(new_entries)
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not fetch missing cited titles from OpenAlex API: {e}")

def build_dataset_title_lookup(output_dir: str) -> dict:
    lookup = {}
    for key, (t_str, u_str) in SEMINAL_MAP.items():
        lookup[key.lower()] = (t_str, u_str)

    search_files = [
        os.path.join(output_dir, "data", "publication_dataset.csv"),
        os.path.join(output_dir, "publication_dataset.csv"),
        os.path.join("data", "collected_EEG_master_merged.csv"),
    ]

    for fpath in search_files:
        if os.path.exists(fpath):
            try:
                df = pd.read_csv(fpath, usecols=lambda c: c in ["Title", "title", "DOI", "doi", "EID", "eid", "Authors", "authors", "Year", "year"])
                t_col = "Title" if "Title" in df.columns else ("title" if "title" in df.columns else None)
                if not t_col:
                    continue
                d_col = "DOI" if "DOI" in df.columns else ("doi" if "doi" in df.columns else None)
                e_col = "EID" if "EID" in df.columns else ("eid" if "eid" in df.columns else None)
                a_col = "Authors" if "Authors" in df.columns else ("authors" if "authors" in df.columns else None)
                y_col = "Year" if "Year" in df.columns else ("year" if "year" in df.columns else None)

                for _, r in df.iterrows():
                    raw_t = str(r[t_col]).strip() if pd.notnull(r[t_col]) else ""
                    if not raw_t or raw_t.lower() == "nan":
                        continue

                    # Build human-memorable paper name: "FirstAuthor et al. (Year) ShortTitle"
                    words = raw_t.split()
                    short_t = " ".join(words[:4]) + ("..." if len(words) > 4 else "")
                    
                    au_str = str(r[a_col]).strip() if a_col and pd.notnull(r[a_col]) else ""
                    yr_str = str(r[y_col]).strip() if y_col and pd.notnull(r[y_col]) else ""

                    if au_str and au_str.lower() != "nan":
                        first_au = au_str.split(";")[0].split(",")[0].strip()
                        yr_val = yr_str[:4] if yr_str and yr_str.lower() != "nan" else ""
                        if yr_val:
                            memorable_name = f"{first_au} et al. ({yr_val}) {short_t}"
                        else:
                            memorable_name = f"{first_au} et al. {short_t}"
                    else:
                        memorable_name = short_t

                    doi_val = str(r[d_col]).strip() if d_col and pd.notnull(r[d_col]) else ""
                    eid_val = str(r[e_col]).strip() if e_col and pd.notnull(r[e_col]) else ""

                    if doi_val and doi_val.lower() != "nan":
                        clean_doi = doi_val.replace("https://doi.org/", "").replace("http://dx.doi.org/", "").strip().lower()
                        lookup[clean_doi] = (memorable_name, f"https://doi.org/{clean_doi}")

                    if eid_val and eid_val.lower() != "nan":
                        clean_eid = eid_val.replace("https://openalex.org/", "").strip().lower()
                        lookup[clean_eid] = (memorable_name, f"https://openalex.org/{clean_eid}")
            except Exception:
                pass
    return lookup

def export_coupling_tables(output_dir: str = "pipeline_results", title_map: dict = None, style: str = "title", force: bool = False):
    """Generates tab_Biblio.tex and annex_Label_Bibliographic_Coupling.tex with human memorable paper names."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)

    t1 = os.path.join(tables_dir, "tab_Biblio.tex")
    t1_top = os.path.join(output_dir, "tab_Biblio.tex")
    t2 = os.path.join(tables_dir, "annex_Label_Bibliographic_Coupling.tex")
    t2_top = os.path.join(output_dir, "annex_Label_Bibliographic_Coupling.tex")

    if not force and os.path.exists(t1) and os.path.exists(t2) and os.path.getsize(t1) > 100 and os.path.getsize(t2) > 100:
        pass  # Always overwrite when updating exporters

    coupling_csv = os.path.join(output_dir, "data", "network_coupling.csv")
    if not os.path.exists(coupling_csv):
        coupling_csv = os.path.join(output_dir, "network_coupling.csv")

    if not os.path.exists(coupling_csv):
        return

    try:
        dataset_lookup = build_dynamic_title_lookup(output_dir)
        top_25_df = pl.scan_csv(coupling_csv).sort("coupling_weight", descending=True).limit(25).collect().to_pandas()
        top_10 = top_25_df.head(10)

        def _get_display(row, col_prefix):
            s_raw = str(row.get(col_prefix, "")).strip()
            clean_id = s_raw.replace("https://doi.org/", "").replace("https://openalex.org/", "").strip().lower()
            url = f"https://doi.org/{clean_id}" if clean_id.startswith("10.") else f"https://openalex.org/{clean_id}"

            if clean_id in dataset_lookup:
                return dataset_lookup[clean_id]

            s_title = str(row.get(f"{col_prefix}_title", "")).strip()
            if s_title and s_title != "nan" and not s_title.startswith("Document ") and not s_title.startswith("Paper "):
                words = s_title.split()
                short_t = " ".join(words[:4]) + ("..." if len(words) > 4 else "")
                return short_t, url

            short_ref = clean_id.replace("10.1109/", "").replace("10.1016/", "").replace("j.", "")
            return f"Publication ({short_ref[:20]})", url

        # 1. Main Table II: Top 10 Bibliographic Coupling Pairs
        tex = []
        tex.append("\\begin{table}[htbp]")
        tex.append("\\caption{Top 10 Bibliographically Coupled Document Pairs}")
        tex.append("\\label{tab:Biblio}")
        tex.append("\\scriptsize")
        tex.append("\\setlength{\\tabcolsep}{4pt}")
        tex.append("\\begin{tabular}{r p{0.32\\linewidth} p{0.32\\linewidth} r}")
        tex.append("\\toprule")
        tex.append("\\# & \\textbf{Source Document 1} & \\textbf{Source Document 2} & \\textbf{Shared} \\\\")
        tex.append("\\midrule")
        for i, (_, r) in enumerate(top_10.iterrows(), 1):
            t1_str, u1 = _get_display(r, "source_1")
            t2_str, u2 = _get_display(r, "source_2")

            c1 = t1_str.replace("&", "\\&").replace("_", "\\_").replace("#", "\\#").replace("%", "\\%")
            c2 = t2_str.replace("&", "\\&").replace("_", "\\_").replace("#", "\\#").replace("%", "\\%")
            s1_link = f"\\href{{{u1}}}{{{c1}}}"
            s2_link = f"\\href{{{u2}}}{{{c2}}}"
            cnt = int(r['coupling_weight'])
            tex.append(f"{i} & {s1_link} & {s2_link} & {cnt:,} \\\\")
        tex.append("\\bottomrule")
        tex.append("\\end{tabular}")
        tex.append("\\end{table}")

        with open(t1, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
        with open(t1_top, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))

        # 2. Annex Table III: Full Bibliographic Coupling Mapping
        top_annex = df.nlargest(25, "coupling_weight")
        atex = []
        atex.append("\\subsection{Bibliographic Coupling Clusters \\& Document Pairs}")
        atex.append("\\begin{table}[htbp]")
        atex.append("\\caption{Bibliographic Coupling Document Pair Mapping}")
        atex.append("\\label{tab:BibliographicCouplingLabels}")
        atex.append("\\scriptsize")
        atex.append("\\setlength{\\tabcolsep}{4pt}")
        atex.append("\\begin{tabular}{p{0.32\\linewidth} p{0.32\\linewidth} r}")
        atex.append("\\toprule")
        atex.append("\\textbf{Source Document 1} & \\textbf{Source Document 2} & \\textbf{Shared} \\\\")
        atex.append("\\midrule")

        for _, r in top_annex.iterrows():
            t1_str, u1 = _get_display(r, "source_1")
            t2_str, u2 = _get_display(r, "source_2")
            c1 = t1_str.replace("&", "\\&").replace("_", "\\_").replace("#", "\\#").replace("%", "\\%")
            c2 = t2_str.replace("&", "\\&").replace("_", "\\_").replace("#", "\\#").replace("%", "\\%")
            s1_link = f"\\href{{{u1}}}{{{c1}}}"
            s2_link = f"\\href{{{u2}}}{{{c2}}}"
            cnt = int(r['coupling_weight'])
            atex.append(f"{s1_link} & {s2_link} & {cnt:,} \\\\")
        atex.append("\\bottomrule")
        atex.append("\\end{tabular}")
        atex.append("\\end{table}")

        with open(t2, "w", encoding="utf-8") as f:
            f.write("\n".join(atex))
        with open(t2_top, "w", encoding="utf-8") as f:
            f.write("\n".join(atex))

        logger.info(f"Generated {t1} and {t2} with real paper titles!")
    except Exception as e:
        logger.warning(f"Could not generate coupling tables: {e}")

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    logging.basicConfig(level=logging.INFO, format="[+] %(message)s")
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results"
    export_coupling_tables(out_dir, force=True)
