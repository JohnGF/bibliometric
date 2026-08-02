import os
import shutil
import sys

def organize_output_directory(output_dir="pipeline_results_37k"):
    out_path = os.path.abspath(output_dir)
    if not os.path.exists(out_path):
        print(f"[!] Target output directory {out_path} does not exist.")
        return

    fig_dir = os.path.join(out_path, "figures")
    tbl_dir = os.path.join(out_path, "tables")
    dat_dir = os.path.join(out_path, "data")

    os.makedirs(fig_dir, exist_ok=True)
    os.makedirs(tbl_dir, exist_ok=True)
    os.makedirs(dat_dir, exist_ok=True)

    keep_top_level = {
        "paper_scaffold.pdf",
        "paper_scaffold.tex",
        "paper_scaffold.aux",
        "paper_scaffold.log",
        "paper_scaffold.out",
        "IEEEtran.cls",
        "Makefile"
    }

    fig_count = 0
    tbl_count = 0
    dat_count = 0

    for fname in os.listdir(out_path):
        fpath = os.path.join(out_path, fname)
        if os.path.isdir(fpath) or fname in keep_top_level:
            continue

        if fname.endswith(".pdf") or fname.endswith(".png"):
            shutil.move(fpath, os.path.join(fig_dir, fname))
            fig_count += 1
        elif fname.endswith(".tex"):
            shutil.move(fpath, os.path.join(tbl_dir, fname))
            tbl_count += 1
        elif fname.endswith(".csv") or fname.endswith(".parquet") or fname.endswith(".json"):
            shutil.move(fpath, os.path.join(dat_dir, fname))
            dat_count += 1

    print(f"[✓] Successfully organized {out_path}:")
    print(f"    - {fig_count} figure files -> figures/")
    print(f"    - {tbl_count} table files  -> tables/")
    print(f"    - {dat_count} data files   -> data/")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results_37k"
    organize_output_directory(target)
