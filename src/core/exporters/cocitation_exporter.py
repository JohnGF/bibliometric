import os
import sys
import json
import polars as pl
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
    try:
        chunk = [m.upper() for m in missing[:50]]
        pipe_ids = "|".join(chunk)
        url = f"https://api.openalex.org/works?filter=openalex:{pipe_ids}&per_page=50"
        req = urllib.request.Request(url, headers={"User-Agent": "BibliometricPipeline/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            new_entries = {}
            # To handle OpenAlex redirects/merges, we need to map returned IDs back to the requested IDs
            # First create a map of original IDs to entries
            returned_entries = {}
            for item in data.get("results", []):
                actual_wid = item.get("id", "").split("/")[-1].lower()
                display_name = item.get("display_name", "")
                yr = str(item.get("publication_year", ""))
                authorships = item.get("authorships", [])
                doi = item.get("doi", f"https://openalex.org/{actual_wid.upper()}")

                display_name = display_name or "Unknown Title"
                if authorships:
                    author_name = authorships[0].get("author", {}).get("display_name", "")
                    first_au = author_name.split()[-1] if author_name else "Unknown"
                    words = display_name.split()
                    short_t = " ".join(words[:4]) + ("..." if len(words) > 4 else "")
                    title_str = f"{first_au} et al. ({yr}) {short_t}" if yr else f"{first_au} et al. {short_t}"
                else:
                    words = display_name.split()
                    title_str = " ".join(words[:4]) + ("..." if len(words) > 4 else "")

                entry = (title_str, doi if doi else f"https://openalex.org/{actual_wid.upper()}")
                returned_entries[actual_wid] = entry

                # Also check 'ids' field for merged/old IDs that we might have requested
                openalex_id = item.get("ids", {}).get("openalex")
                if isinstance(openalex_id, str):
                    old_id = openalex_id.split("/")[-1].lower()
                    returned_entries[old_id] = entry

            # Now assign the found entries back to the original requested IDs
            for req_id in missing[:50]:
                if req_id in returned_entries:
                    lookup[req_id] = returned_entries[req_id]
                    new_entries[req_id] = returned_entries[req_id]

            # Fallback for IDs that still failed in the batch query
            still_missing = [m for m in missing[:50] if m not in new_entries]
            for sm in still_missing:
                try:
                    url_single = f"https://api.openalex.org/works/{sm.upper()}"
                    req_single = urllib.request.Request(url_single, headers={"User-Agent": "BibliometricPipeline/1.0"})
                    with urllib.request.urlopen(req_single, timeout=5) as resp_single:
                        item = json.loads(resp_single.read().decode('utf-8'))
                        actual_wid = item.get("id", "").split("/")[-1].lower()
                        display_name = item.get("display_name", "")
                        yr = str(item.get("publication_year", ""))
                        authorships = item.get("authorships", [])
                        doi = item.get("doi", f"https://openalex.org/{actual_wid.upper()}")

                        display_name = display_name or "Unknown Title"
                        if authorships:
                            author_name = authorships[0].get("author", {}).get("display_name", "")
                            first_au = author_name.split()[-1] if author_name else "Unknown"
                            words = display_name.split()
                            short_t = " ".join(words[:4]) + ("..." if len(words) > 4 else "")
                            title_str = f"{first_au} et al. ({yr}) {short_t}" if yr else f"{first_au} et al. {short_t}"
                        else:
                            words = display_name.split()
                            title_str = " ".join(words[:4]) + ("..." if len(words) > 4 else "")

                        entry = (title_str, doi if doi else f"https://openalex.org/{actual_wid.upper()}")
                        lookup[sm] = entry
                        new_entries[sm] = entry
                except Exception as ex:
                    pass

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

def export_cocitation_tables(output_dir: str = "pipeline_results", title_map: dict = None, style: str = "title", force: bool = False):
    """Generates tab_top_references_pagerank.tex and annex_Label_Co_Citation.tex streaming 6.2GB CSV with Polars."""
    tables_dir = os.path.join(output_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)

    t1 = os.path.join(tables_dir, "tab_top_references_pagerank.tex")
    t1_top = os.path.join(output_dir, "tab_top_references_pagerank.tex")
    t2 = os.path.join(tables_dir, "annex_Label_Co_Citation.tex")
    t2_top = os.path.join(output_dir, "annex_Label_Co_Citation.tex")

    cocit_csv = os.path.join(output_dir, "data", "network_cocitations.csv")
    if not os.path.exists(cocit_csv):
        cocit_csv = os.path.join(output_dir, "network_cocitations.csv")

    if not os.path.exists(cocit_csv):
        return

    try:
        logger.info(f"Scanning {cocit_csv} using Polars fast lazy engine...")
        lazy_df = pl.scan_csv(cocit_csv)

        # 1. Compute top 20 cited references in sub-second speed using Polars
        c1 = lazy_df.group_by("cited_1").agg(pl.col("co_citation_count").sum().alias("count")).rename({"cited_1": "cited"})
        c2 = lazy_df.group_by("cited_2").agg(pl.col("co_citation_count").sum().alias("count")).rename({"cited_2": "cited"})
        top_20_df = pl.concat([c1, c2]).group_by("cited").agg(pl.col("count").sum()).sort("count", descending=True).limit(20).collect()

        # 2. Extract top 25 co-citation pairs for Annex table
        top_annex_df = lazy_df.sort("co_citation_count", descending=True).limit(25).collect().to_pandas()

        dataset_lookup = build_dynamic_title_lookup(output_dir)
        fetch_and_cache_missing_openalex_titles([str(x) for x in top_20_df["cited"]], dataset_lookup, output_dir)

        # Build Main Table III
        tex = []
        tex.append("\\begin{table}[htbp]")
        tex.append("\\caption{Top 20 Most Referenced Landmark Publications}")
        tex.append("\\label{tab:top_references_pagerank}")
        tex.append("\\footnotesize")
        tex.append("\\begin{tabular}{p{0.75\\linewidth} r}")
        tex.append("\\toprule")
        tex.append("\\textbf{Landmark Reference Publication} & \\textbf{Citations} \\\\")
        tex.append("\\midrule")

        for row in top_20_df.to_dicts():
            ref_id = str(row["cited"]).strip()
            cnt = int(row["count"])

            clean_id = ref_id.replace("https://doi.org/", "").replace("https://openalex.org/", "").strip().lower()
            url = f"https://doi.org/{clean_id}" if clean_id.startswith("10.") else f"https://openalex.org/{clean_id}"

            if clean_id in dataset_lookup:
                title, url = dataset_lookup[clean_id]
            else:
                short_ref = clean_id.replace("10.1109/", "").replace("10.1016/", "").replace("j.", "")
                title = f"Landmark Reference ({short_ref[:20]})"

            clean_t = title.replace("&", "\\&").replace("_", "\\_").replace("#", "\\#").replace("%", "\\%")
            link_str = f"\\href{{{url}}}{{{clean_t}}}"
            tex.append(f"{link_str} & {cnt:,} \\\\")

        tex.append("\\bottomrule")
        tex.append("\\end{tabular}")
        tex.append("\\end{table}")

        with open(t1, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
        with open(t1_top, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))

        # Build Annex Table IV
        atex = []
        atex.append("\\subsection{Co-Citation Document Pairs \\& Shared Reference Network}")
        atex.append("\\begin{table}[htbp]")
        atex.append("\\caption{Co-Cited Document Pair Mapping}")
        atex.append("\\label{tab:CoCitationLabels}")
        atex.append("\\scriptsize")
        atex.append("\\begin{tabular}{p{0.42\\linewidth} p{0.42\\linewidth} r}")
        atex.append("\\toprule")
        atex.append("\\textbf{Cited Reference 1} & \\textbf{Cited Reference 2} & \\textbf{Co-Citations} \\\\")
        atex.append("\\midrule")

        for _, r in top_annex_df.iterrows():
            c1_val = str(r['cited_1']).strip()
            c2_val = str(r['cited_2']).strip()
            cnt = int(r['co_citation_count'])

            clean1 = c1_val.replace("https://doi.org/", "").replace("https://openalex.org/", "").strip().lower()
            clean2 = c2_val.replace("https://doi.org/", "").replace("https://openalex.org/", "").strip().lower()

            if clean1 in dataset_lookup:
                t1_str, u1_str = dataset_lookup[clean1]
            else:
                t1_str = f"Reference ({clean1[:20]})"
                u1_str = f"https://openalex.org/{clean1}"

            if clean2 in dataset_lookup:
                t2_str, u2_str = dataset_lookup[clean2]
            else:
                t2_str = f"Reference ({clean2[:20]})"
                u2_str = f"https://openalex.org/{clean2}"

            cl1 = str(t1_str).replace("&", "\\&").replace("_", "\\_").replace("#", "\\#").replace("%", "\\%")
            cl2 = str(t2_str).replace("&", "\\&").replace("_", "\\_").replace("#", "\\#").replace("%", "\\%")
            s1_link = f"\\href{{{u1_str}}}{{{cl1}}}"
            s2_link = f"\\href{{{u2_str}}}{{{cl2}}}"
            atex.append(f"{s1_link} & {s2_link} & {cnt:,} \\\\")

        atex.append("\\bottomrule")
        atex.append("\\end{tabular}")
        atex.append("\\end{table}")

        with open(t2, "w", encoding="utf-8") as f:
            f.write("\n".join(atex))
        with open(t2_top, "w", encoding="utf-8") as f:
            f.write("\n".join(atex))

        logger.info(f"Generated {t1} and {t2} using Polars fast engine!")
    except Exception as e:
        logger.warning(f"Could not generate co-citation tables: {e}")

if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    logging.basicConfig(level=logging.INFO, format="[+] %(message)s")
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results"
    export_cocitation_tables(out_dir, force=True)
