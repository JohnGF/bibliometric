import os
import sys
import re
import pandas as pd
import urllib.request
import json

def load_title_lookup(output_dir="pipeline_results_37k"):
    seminal_map = {
        "W31182665": ("Delorme et al., EEGLAB Toolbox", "https://doi.org/10.1016/j.jneumeth.2003.10.009"),
        "W2122816088": ("Oostenveld et al., FieldTrip Software", "https://doi.org/10.1155/2011/156869"),
        "W2768132193": ("Lawhern et al., EEGNet CNN BCI", "https://doi.org/10.1088/1741-2552/aace8c"),
        "W2804784400": ("Koelstra et al., DEAP Emotion Dataset", "https://doi.org/10.1109/T-AFFC.2011.15"),
        "W3003415550": ("Goldberger et al., PhysioNet Database", "https://doi.org/10.1161/hc2300.091309"),
        "W4315754639": ("Schirrmeister et al., Deep Learning CNN", "https://doi.org/10.1002/hbm.23730"),
        "W1861891407": ("Makeig et al., BSS Artifact Removal", "https://doi.org/10.1111/j.1469-8986.1996.tb02421.x"),
        "W1877917243": ("Wolpaw et al., Brain-Computer Interfaces", "https://doi.org/10.1016/S1388-2457(02)00057-3"),
        "W1502633200": ("Ang et al., Filter Bank CSP (FBCSP)", "https://doi.org/10.1109/IJCNN.2008.4634130"),
        "W1502967669": ("Pfurtscheller et al., Event-Related Sync", "https://doi.org/10.1016/S1388-2457(99)00141-8"),
        "W1593442063": ("Polich et al., Updating P300 Theory", "https://doi.org/10.1016/S1388-2457(03)00155-0"),
        "W2137604100": ("Klimesch et al., EEG Alpha Oscillator", "https://doi.org/10.1016/S0168-0102(99)00027-0"),
        "W2567564314": ("Bell & Sejnowski, InfoMax ICA", "https://doi.org/10.1162/neco.1995.7.6.1129"),
        "W2125744415": ("Brainard et al., Psychophysics Toolbox", "https://doi.org/10.1016/S0042-6989(97)00101-1"),
    }
    lookup = {}
    for key, (title, doi_url) in seminal_map.items():
        data = {"title": title, "url": doi_url}
        lookup[key] = data
        lookup[f"https://openalex.org/{key}"] = data

    search_dirs = [output_dir, "data"]
    for sdir in search_dirs:
        if not os.path.exists(sdir):
            continue
        for fname in os.listdir(sdir):
            if fname.endswith(".csv") and "network" not in fname:
                fpath = os.path.join(sdir, fname)
                try:
                    df = pd.read_csv(fpath, usecols=lambda c: c in ["Title", "title", "DOI", "doi", "EID", "eid", "Authors", "Year"])
                    t_col = "Title" if "Title" in df.columns else ("title" if "title" in df.columns else None)
                    if not t_col:
                        continue
                    t_arr = df[t_col].fillna("").astype(str).values
                    doi_col = "DOI" if "DOI" in df.columns else ("doi" if "doi" in df.columns else None)
                    eid_col = "EID" if "EID" in df.columns else ("eid" if "eid" in df.columns else None)
                    aut_col = "Authors" if "Authors" in df.columns else ("authors" if "authors" in df.columns else None)
                    yr_col = "Year" if "Year" in df.columns else ("year" if "year" in df.columns else None)

                    d_arr = df[doi_col].fillna("").astype(str).values if doi_col else [""] * len(t_arr)
                    e_arr = df[eid_col].fillna("").astype(str).values if eid_col else [""] * len(t_arr)
                    au_arr = df[aut_col].fillna("").astype(str).values if aut_col else [""] * len(t_arr)
                    y_arr = df[yr_col].fillna("").astype(str).values if yr_col else [""] * len(t_arr)

                    for d, e, t, au, y in zip(d_arr, e_arr, t_arr, au_arr, y_arr):
                        t_clean = t.strip()
                        if not t_clean or t_clean.lower() == "nan":
                            continue
                        
                        # Short title formatting
                        words = t_clean.split()
                        short_t = " ".join(words[:5]) + ("..." if len(words) > 5 else "")
                        
                        if au and au.lower() != "nan":
                            first_author = au.split(";")[0].split(",")[0].strip()
                            if yr and yr.lower() != "nan":
                                short_t = f"{first_author} et al. ({yr[:4]}) {short_t}"

                        d_clean = d.strip()
                        if d_clean and d_clean.lower() != "nan":
                            url = f"https://doi.org/{d_clean}"
                            data = {"title": short_t, "url": url}
                            lookup[d_clean] = data
                            lookup[url] = data

                        e_clean = e.strip()
                        if e_clean and e_clean.lower() != "nan":
                            raw_id = e_clean.split("/")[-1]
                            url = e_clean if e_clean.startswith("http") else f"https://openalex.org/{e_clean}"
                            data = {"title": short_t, "url": url}
                            lookup[raw_id] = data
                            lookup[url] = data
                except Exception:
                    pass
    return lookup

def fetch_openalex_title(wid):
    url = f"https://api.openalex.org/works/{wid}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BibliometricPipeline/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            title = data.get("display_name", "")
            authors = data.get("authorships", [])
            year = data.get("publication_year", "")
            
            if authors:
                first_author = authors[0].get("author", {}).get("display_name", "").split()[-1]
                words = title.split()
                short_t = " ".join(words[:4]) + ("..." if len(words) > 4 else "")
                return f"{first_author} et al. ({year}) {short_t}"
            words = title.split()
            return " ".join(words[:5]) + ("..." if len(words) > 5 else "")
    except Exception:
        return f"Reference {wid}"

def fix_latex_tables(output_dir="pipeline_results_37k"):
    print(f"[+] Loading title lookup for hyperlinked table titles in {output_dir}...")
    lookup = load_title_lookup(output_dir)

    target_files = [
        "tab_top_references_pagerank.tex",
        "tab_Biblio.tex",
        "annex_Label_Co_Citation.tex",
        "annex_Label_Bibliographic_Coupling.tex"
    ]

    for fname in target_files:
        fpath = os.path.join(output_dir, fname)
        if not os.path.exists(fpath):
            continue

        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()

        def _replace_href(match):
            url = match.group(1)
            raw_title = match.group(2)
            
            # Check if title is generic or raw ID
            if "Paper W" in raw_title or "Reference W" in raw_title or raw_title.startswith("W") or "10." in raw_title or "DOI:" in raw_title:
                raw_id = url.rstrip("/").split("/")[-1]
                if raw_id in lookup:
                    t_info = lookup[raw_id]
                    clean_t = t_info["title"]
                elif url in lookup:
                    clean_t = lookup[url]["title"]
                elif raw_id.startswith("W"):
                    clean_t = fetch_openalex_title(raw_id)
                    lookup[raw_id] = {"title": clean_t, "url": url}
                else:
                    clean_t = raw_title
                    
                escaped_t = clean_t.replace("&", "\\&").replace("_", "\\_").replace("#", "\\#").replace("%", "\\%")
                return f"\\href{{{url}}}{{{escaped_t}}}"
            return match.group(0)

        # Match \href{url}{title}
        new_content = re.sub(r'\\href\{([^}]+)\}\{([^}]+)\}', _replace_href, content)

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"[✓] Updated {fname} with concise real paper titles and hyperlinked URLs!")

if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results_37k"
    fix_latex_tables(out_dir)
