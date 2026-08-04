import re

with open("src/core/exporters/cocitation_exporter.py", "r") as f:
    content = f.read()

# We will just write a simpler script to replace the function directly
start_idx = content.find("def export_cocitation_tables")
end_idx = content.find("if __name__ == \"__main__\":")

if start_idx != -1 and end_idx != -1:
    new_func = """def export_cocitation_tables(output_dir: str = "pipeline_results", title_map: dict = None, style: str = "title", force: bool = False):
    \"\"\"Generates tab_top_references_pagerank.tex and annex_Label_Co_Citation.tex streaming 6.2GB CSV with Polars.\"\"\"
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
            rf.write("rejected_id\\n")
            for rid in rejected_ids:
                rf.write(f"{rid}\\n")
        logger.info(f"Exported {len(rejected_ids)} unresolved reference IDs to {reject_file}")

        # Build Main Table III
        tex = []
        tex.append(r"\\begin{table}[htbp]")
        tex.append(r"\\caption{Top 20 Most Referenced Landmark Publications}")
        tex.append(r"\\label{tab:top_references_pagerank}")
        tex.append(r"\\footnotesize")
        tex.append(r"\\begin{tabular}{p{0.75\\linewidth} r}")
        tex.append(r"\\toprule")
        tex.append(r"\\textbf{Landmark Reference Publication} & \\textbf{Citations} \\\\")
        tex.append(r"\\midrule")

        for ref_id, cnt, clean_id in valid_top_20:
            title, url = dataset_lookup[clean_id]
            clean_t = title.replace("&", r"\\&").replace("_", r"\\_").replace("#", r"\\#").replace("%", r"\\%")
            link_str = f"\\href{{{url}}}{{{clean_t}}}"
            tex.append(f"{link_str} & {cnt:,} \\\\")

        tex.append(r"\\bottomrule")
        tex.append(r"\\end{tabular}")
        tex.append(r"\\end{table}")

        with open(t1, "w", encoding="utf-8") as f:
            f.write("\\n".join(tex))
        with open(t1_top, "w", encoding="utf-8") as f:
            f.write("\\n".join(tex))

        # Build Annex Table IV
        atex = []
        atex.append(r"\\subsection{Co-Citation Document Pairs \\& Shared Reference Network}")
        atex.append(r"\\begin{table}[htbp]")
        atex.append(r"\\caption{Co-Cited Document Pair Mapping}")
        atex.append(r"\\label{tab:CoCitationLabels}")
        atex.append(r"\\scriptsize")
        atex.append(r"\\begin{tabular}{p{0.42\\linewidth} p{0.42\\linewidth} r}")
        atex.append(r"\\toprule")
        atex.append(r"\\textbf{Cited Reference 1} & \\textbf{Cited Reference 2} & \\textbf{Co-Citations} \\\\")
        atex.append(r"\\midrule")

        for c1_val, c2_val, cnt, clean1, clean2 in valid_annex:
            t1_str, u1_str = dataset_lookup[clean1]
            t2_str, u2_str = dataset_lookup[clean2]

            cl1 = str(t1_str).replace("&", r"\\&").replace("_", r"\\_").replace("#", r"\\#").replace("%", r"\\%")
            cl2 = str(t2_str).replace("&", r"\\&").replace("_", r"\\_").replace("#", r"\\#").replace("%", r"\\%")
            s1_link = f"\\href{{{u1_str}}}{{{cl1}}}"
            s2_link = f"\\href{{{u2_str}}}{{{cl2}}}"
            atex.append(f"{s1_link} & {s2_link} & {cnt:,} \\\\")

        atex.append(r"\\bottomrule")
        atex.append(r"\\end{tabular}")
        atex.append(r"\\end{table}")

        with open(t2, "w", encoding="utf-8") as f:
            f.write("\\n".join(atex))
        with open(t2_top, "w", encoding="utf-8") as f:
            f.write("\\n".join(atex))

        logger.info(f"Generated {t1} and {t2} using Polars fast engine!")
    except Exception as e:
        logger.warning(f"Could not generate co-citation tables: {e}")

"""
    new_content = content[:start_idx] + new_func + content[end_idx:]
    with open("src/core/exporters/cocitation_exporter.py", "w") as f:
        f.write(new_content)
