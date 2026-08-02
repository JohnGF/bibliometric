#!/usr/bin/env bash
set -e
podman run --rm -v .:/app:z --entrypoint python biblio-pipeline /app/scripts/build_paper_scaffold.py pipeline_results_37k
cd pipeline_results_37k
pdflatex -interaction=nonstopmode paper_scaffold.tex
pdflatex -interaction=nonstopmode paper_scaffold.tex
echo "[✓] IEEEtran Paper Scaffold compilation complete -> pipeline_results_37k/paper_scaffold.pdf"
