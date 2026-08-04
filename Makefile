# Bibliometric Research Pipeline Makefile

OUT_DIR ?= pipeline_results_37k

.PHONY: help scaffold container-scaffold pipeline clean

help:
	@echo "========================================================================"
	@echo "                  BIBLIOMETRIC RESEARCH PIPELINE                       "
	@echo "========================================================================"
	@echo "  make scaffold           - Regenerate growth figure, export & compile scaffold PDF"
	@echo "  make container-scaffold - Export & compile scaffold via Podman container"
	@echo "  make pipeline           - Execute full bibliometric analysis on 37k dataset"
	@echo "  make clean              - Clean temporary TeX compilation artifacts"
	@echo ""
	@echo "  OUT_DIR=<dir> overrides the output directory (default: $(OUT_DIR))."
	@echo "  Query & study period are read from data/query.txt (start-year/end-year)."
	@echo "========================================================================"

scaffold:
	@echo "[+] Regenerating yearly growth figure from dataset..."
	uv run python scripts/regenerate_growth.py $(OUT_DIR)
	@echo "[+] Building IEEEtran Paper Scaffold..."
	uv run python scripts/build_paper_scaffold.py $(OUT_DIR)

container-scaffold:
	@echo "[+] Regenerating yearly growth figure via Container..."
	podman run --rm -v .:/app:z --entrypoint python biblio-pipeline /app/scripts/regenerate_growth.py $(OUT_DIR)
	@echo "[+] Building IEEEtran Paper Scaffold via Container..."
	podman run --rm -v .:/app:z --entrypoint python biblio-pipeline /app/scripts/build_paper_scaffold.py $(OUT_DIR)
	@cd $(OUT_DIR) && pdflatex -interaction=nonstopmode paper_scaffold.tex && pdflatex -interaction=nonstopmode paper_scaffold.tex
	@echo "[✓] IEEEtran Paper Scaffold compiled -> $(OUT_DIR)/paper_scaffold.pdf"

pipeline:
	@echo "[+] Running full 37k bibliometric pipeline (study period from data/query.txt)..."
	uv run biblio-pipeline --file data/collected_EEG_master_merged.csv --output $(OUT_DIR)

clean:
	@echo "[+] Removing TeX build logs and auxiliary files..."
	@rm -f $(OUT_DIR)/*.aux $(OUT_DIR)/*.log $(OUT_DIR)/*.out $(OUT_DIR)/*.toc
