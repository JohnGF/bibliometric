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
    missing = list(set([w.strip().lower().split("/")[-1] for w in w_ids if w.strip().lower() not in lookup and w.strip().split("/")[-1].lower().startswith("w")]))
    if not missing:
        return

    import urllib.request
    new_entries = {}

    try:
        # Process in chunks of 50
        for i in range(0, len(missing), 50):
            chunk = [m.upper() for m in missing[i:i+50]]
            pipe_ids = "|".join(chunk)
            url = f"https://api.openalex.org/works?filter=openalex:{pipe_ids}&per_page=50"
            req = urllib.request.Request(url, headers={"User-Agent": "BibliometricPipeline/1.0"})

            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
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
                    for req_id in missing[i:i+50]:
                        if req_id in returned_entries:
                            lookup[req_id] = returned_entries[req_id]
                            new_entries[req_id] = returned_entries[req_id]

                    # Fallback for IDs that still failed in the batch query
                    still_missing = [m for m in missing[i:i+50] if m not in new_entries]
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
            except Exception as e:
                logger.warning(f"Batch query failed for chunk: {e}")

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

        # 1. Compute top 200 cited references in sub-second speed using Polars (to gather candidates)
        c1 = lazy_df.group_by("cited_1").agg(pl.col("co_citation_count").sum().alias("count")).rename({"cited_1": "cited"})
        c2 = lazy_df.group_by("cited_2").agg(pl.col("co_citation_count").sum().alias("count")).rename({"cited_2": "cited"})
        top_cand_df = pl.concat([c1, c2]).group_by("cited").agg(pl.col("count").sum()).sort("count", descending=True).limit(200).collect()

        # 2. Extract top 200 co-citation pairs for Annex table candidates
        top_annex_cand_df = lazy_df.sort("co_citation_count", descending=True).limit(200).collect().to_pandas()

        dataset_lookup = build_dynamic_title_lookup(output_dir)

        # Collect all unique IDs from candidates to fetch
        all_candidate_ids = set()
        for x in top_cand_df["cited"]:
            all_candidate_ids.add(str(x))
        for _, r in top_annex_cand_df.iterrows():
            all_candidate_ids.add(str(r['cited_1']))
            all_candidate_ids.add(str(r['cited_2']))

        fetch_and_cache_missing_openalex_titles(list(all_candidate_ids), dataset_lookup, output_dir)

        rejected_ids = set()

        # Filter top 20 main table candidates
        valid_top_20 = []
        for row in top_cand_df.to_dicts():
            ref_id = str(row["cited"]).strip()
            cnt = int(row["count"])
            clean_id = ref_id.replace("https://doi.org/", "").replace("https://openalex.org/", "").strip().lower()

            if clean_id in dataset_lookup:
                valid_top_20.append((ref_id, cnt, clean_id))
            else:
                rejected_ids.add(ref_id)

            if len(valid_top_20) >= 20:
                break

        # Filter top 25 annex table candidates
        valid_annex = []
        for _, r in top_annex_cand_df.iterrows():
            c1_val = str(r['cited_1']).strip()
            c2_val = str(r['cited_2']).strip()
            cnt = int(r['co_citation_count'])

            clean1 = c1_val.replace("https://doi.org/", "").replace("https://openalex.org/", "").strip().lower()
            clean2 = c2_val.replace("https://doi.org/", "").replace("https://openalex.org/", "").strip().lower()

            if clean1 in dataset_lookup and clean2 in dataset_lookup:
                valid_annex.append((c1_val, c2_val, cnt, clean1, clean2))
            else:
                if clean1 not in dataset_lookup:
                    rejected_ids.add(c1_val)
                if clean2 not in dataset_lookup:
                    rejected_ids.add(c2_val)

            if len(valid_annex) >= 25:
                break

        # Write rejected references to a CSV
        reject_file = os.path.join(output_dir, "data", "unresolved_references_reject.csv")
        os.makedirs(os.path.dirname(reject_file), exist_ok=True)
        with open(reject_file, "w", encoding="utf-8") as rf:
            rf.write("rejected_id\n")
            for rid in rejected_ids:
                rf.write(f"{rid}\n")
        logger.info(f"Exported {len(rejected_ids)} unresolved reference IDs to {reject_file}")

        # Build Main Table III
        tex = []
        tex.append(r"\begin{table}[htbp]")
        tex.append(r"\caption{Top 20 Most Referenced Landmark Publications}")
        tex.append(r"\label{tab:top_references_pagerank}")
        tex.append(r"\footnotesize")
        tex.append(r"\begin{tabular}{p{0.75\linewidth} r}")
        tex.append(r"\toprule")
        tex.append(r"\textbf{Landmark Reference Publication} & \textbf{Citations} \\")
        tex.append(r"\midrule")

        for ref_id, cnt, clean_id in valid_top_20:
            title, url = dataset_lookup[clean_id]
            clean_t = title.replace("&", r"\&").replace("_", r"\_").replace("#", r"\#").replace("%", r"\%")
            link_str = f"\\href{{{url}}}{{{clean_t}}}"
            tex.append(f"{link_str} & {cnt:,} \\\\")

        tex.append(r"\bottomrule")
        tex.append(r"\end{tabular}")
        tex.append(r"\end{table}")

        with open(t1, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
        with open(t1_top, "w", encoding="utf-8") as f:
            f.write("\n".join(tex))

        # Build Annex Table IV
        atex = []
        atex.append(r"\subsection{Co-Citation Document Pairs \& Shared Reference Network}")
        atex.append(r"\begin{table}[htbp]")
        atex.append(r"\caption{Co-Cited Document Pair Mapping}")
        atex.append(r"\label{tab:CoCitationLabels}")
        atex.append(r"\scriptsize")
        atex.append(r"\setlength{\tabcolsep}{4pt}")
        atex.append(r"\begin{tabular}{p{0.32\linewidth} p{0.32\linewidth} r}")
        atex.append(r"\toprule")
        atex.append(r"\textbf{Cited Reference 1} & \textbf{Cited Reference 2} & \textbf{Co-Citations} \\")
        atex.append(r"\midrule")

        for c1_val, c2_val, cnt, clean1, clean2 in valid_annex:
            t1_str, u1_str = dataset_lookup[clean1]
            t2_str, u2_str = dataset_lookup[clean2]

            cl1 = str(t1_str).replace("&", r"\&").replace("_", r"\_").replace("#", r"\#").replace("%", r"\%")
            cl2 = str(t2_str).replace("&", r"\&").replace("_", r"\_").replace("#", r"\#").replace("%", r"\%")
            s1_link = f"\\href{{{u1_str}}}{{{cl1}}}"
            s2_link = f"\\href{{{u2_str}}}{{{cl2}}}"
            atex.append(f"{s1_link} & {s2_link} & {cnt:,} \\\\")

        atex.append(r"\bottomrule")
        atex.append(r"\end{tabular}")
        atex.append(r"\end{table}")

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
