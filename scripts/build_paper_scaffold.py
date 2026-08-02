import os
import sys
import subprocess

# Ensure repo root is in python path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.core.latex_exporter import LaTeXExporter

def build_and_compile():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "pipeline_results_37k"
    output_path = os.path.abspath(output_dir)
    
    print(f"[+] Exporting IEEEtran LaTeX template files to: {output_path}")
    exporter = LaTeXExporter(output_path)
    exporter.export_all()
    print("[✓] LaTeX templates exported successfully!")

    scaffold_tex = os.path.join(output_path, "paper_scaffold.tex")
    if os.path.exists(scaffold_tex):
        print(f"[+] Compiling {scaffold_tex} with pdflatex...")
        try:
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "paper_scaffold.tex"],
                cwd=output_path,
                check=False
            )
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "paper_scaffold.tex"],
                cwd=output_path,
                check=False
            )
            pdf_path = os.path.join(output_path, "paper_scaffold.pdf")
            if os.path.exists(pdf_path):
                print(f"[✓] PDF compilation complete -> {pdf_path}")
            else:
                print(f"[!] PDF file not found after compilation.")
        except Exception as e:
            print(f"[!] Compilation error: {e}")

if __name__ == "__main__":
    build_and_compile()
