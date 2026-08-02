import os
import sys
import shutil
import pandas as pd
from src.core.ingestion import add_pdf_name_column
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
)

def resolve_output_dir(target_dir: str = "pipeline_results_37k") -> str:
    """Seamlessly resolves output directory whether '.' or 'pipeline_results_37k' is passed."""
    if os.path.exists(os.path.join(target_dir, "data")) or os.path.exists(os.path.join(target_dir, "tables")):
        return target_dir
    if os.path.exists("data") or os.path.exists("tables"):
        return "."
    if os.path.exists("pipeline_results_37k"):
        return "pipeline_results_37k"
    return target_dir

def update_all_tables(target_dir: str = "pipeline_results_37k"):
    output_dir = resolve_output_dir(target_dir)
    print(f"[+] Output directory resolved to: '{output_dir}'")

    data_dir = os.path.join(output_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    pub_csv = os.path.join(data_dir, "publication_dataset.csv")

    # If publication_dataset.csv doesn't exist, create it from master merged dataset
    if not os.path.exists(pub_csv):
        source_candidates = [
            os.path.join("data", "collected_EEG_master_merged.csv"),
            os.path.join("..", "data", "collected_EEG_master_merged.csv"),
            os.path.join("data", "collected_EEG_expanded_merged.csv"),
        ]
        for src in source_candidates:
            if os.path.exists(src):
                print(f"[+] Copying master dataset from '{src}' -> '{pub_csv}'...")
                shutil.copy(src, pub_csv)
                break

    if os.path.exists(pub_csv):
        print(f"[+] Enriching {pub_csv} with 'pdf_name' column...")
        df = pd.read_csv(pub_csv)
        df = add_pdf_name_column(df)
        df.to_csv(pub_csv, index=False)
        print(f"[✓] Created and updated {pub_csv} with 'pdf_name' column!")
    else:
        print(f"[!] Warning: Master dataset CSV not found.")

    tables_out = os.path.join(output_dir, "tables")
    print(f"[+] Exporting updated TeX tables with 'pdf_name' labels to '{tables_out}'...")
    export_author_table(output_dir, force=True)
    export_keywords_table(output_dir, force=True)
    export_cocitation_tables(output_dir, force=True)
    export_coupling_tables(output_dir, force=True)
    export_llm_table(output_dir, force=True)
    export_temporal_table(output_dir, force=True)
    export_country_table(output_dir, force=True)
    export_bertopic_table(output_dir, force=True)
    export_method_application_table(output_dir, force=True)
    export_query_table(output_dir, force=True)
    print(f"[✓] All TeX tables updated successfully with 'pdf_name' labels!")

if __name__ == "__main__":
    t_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    update_all_tables(t_dir)
