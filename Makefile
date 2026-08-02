# Bibliometric Research Pipeline Makefile

.PHONY: help scaffold container-scaffold pipeline clean

help:
	@echo "========================================================================"
	@echo "                  BIBLIOMETRIC RESEARCH PIPELINE                       "
	@echo "========================================================================"
	@echo "  make scaffold           - Export & compile camera-ready paper scaffold PDF"
	@echo "  make container-scaffold - Export & compile scaffold via Podman container"
	@echo "  make pipeline           - Execute full bibliometric analysis on 37k dataset"
	@echo "  make clean              - Clean temporary TeX compilation artifacts"
	@echo "========================================================================"

scaffold:
	@echo "[+] Building IEEEtran Paper Scaffold..."
	python scripts/build_paper_scaffold.py pipeline_results_37k

container-scaffold:
	@echo "[+] Building IEEEtran Paper Scaffold via Container..."
	podman run --rm -v .:/app:z --entrypoint python biblio-pipeline /app/scripts/build_paper_scaffold.py pipeline_results_37k
	@cd pipeline_results_37k && pdflatex -interaction=nonstopmode paper_scaffold.tex && pdflatex -interaction=nonstopmode paper_scaffold.tex
	@echo "[✓] IEEEtran Paper Scaffold compiled -> pipeline_results_37k/paper_scaffold.pdf"

pipeline:
	@echo "[+] Running full 37k bibliometric pipeline..."
	uv run biblio-pipeline --file data/collected_EEG_master_merged.csv --output pipeline_results_37k

clean:
	@echo "[+] Removing TeX build logs and auxiliary files..."
	@rm -f pipeline_results_37k/*.aux pipeline_results_37k/*.log pipeline_results_37k/*.out pipeline_results_37k/*.toc
