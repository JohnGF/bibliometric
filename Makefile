# Bibliometric Research Pipeline Makefile

# Project Directories & Datasets
OUT_DIR ?= pipeline_results_37k
DATASET_FILE ?= data/collected_EEG_master_merged.csv

# Container Configuration (Modular, No Hardcoded Flags)
CONTAINER_ENGINE ?= podman
IMAGE_NAME ?= biblio-pipeline
GPU_FLAGS ?= --device nvidia.com/gpu=all
MOUNT_FLAGS ?= -v .:/app:z

# Query Parameters (Modular, No Hardcoded Query Values)
QUERY ?= "brain-computer interface"
LIMIT ?= 100
START_YEAR ?= 2020
END_YEAR ?= 2025

.PHONY: help scaffold container-scaffold pipeline container-pipeline container-query clean

help:
	@echo "========================================================================"
	@echo "                  BIBLIOMETRIC RESEARCH PIPELINE                       "
	@echo "========================================================================"
	@echo "  make scaffold           - Regenerate analysis figures & build scaffold PDF"
	@echo "  make container-scaffold - Export & compile scaffold via Container"
	@echo "  make pipeline           - Execute full bibliometric analysis locally (CPU)"
	@echo "  make container-pipeline - Execute full bibliometric analysis inside Container (GPU)"
	@echo "  make container-query    - Execute query collection & analysis inside Container (GPU)"
	@echo "  make clean              - Clean temporary TeX compilation artifacts"
	@echo ""
	@echo "  Parameters (Override via CLI, e.g. QUERY=\"EEG\" LIMIT=50):"
	@echo "    QUERY                 - Search query (default: $(QUERY))"
	@echo "    LIMIT                 - Collection limit per source (default: $(LIMIT))"
	@echo "    START_YEAR / END_YEAR - Year boundaries (default: $(START_YEAR) to $(END_YEAR))"
	@echo "    OUT_DIR               - Output directory (default: $(OUT_DIR))"
	@echo "    DATASET_FILE          - Input dataset path (default: $(DATASET_FILE))"
	@echo "    CONTAINER_ENGINE      - Container tool (default: $(CONTAINER_ENGINE))"
	@echo "    GPU_FLAGS             - Container GPU settings (default: $(GPU_FLAGS))"
	@echo "    MOUNT_FLAGS           - Container volume mounts (default: $(MOUNT_FLAGS))"
	@echo "========================================================================"

scaffold:
	@echo "[+] Regenerating analysis figures from dataset..."
	uv run python scripts/regenerate_figures.py $(OUT_DIR)
	@echo "[+] Building IEEEtran Paper Scaffold..."
	uv run python scripts/build_paper_scaffold.py $(OUT_DIR)

container-scaffold:
	@echo "[+] Regenerating analysis figures via Container..."
	$(CONTAINER_ENGINE) run --rm $(MOUNT_FLAGS) --entrypoint python $(IMAGE_NAME) /app/scripts/regenerate_figures.py $(OUT_DIR)
	@echo "[+] Building IEEEtran Paper Scaffold via Container..."
	$(CONTAINER_ENGINE) run --rm $(MOUNT_FLAGS) --entrypoint python $(IMAGE_NAME) /app/scripts/build_paper_scaffold.py $(OUT_DIR)
	@cd $(OUT_DIR) && pdflatex -interaction=nonstopmode paper_scaffold.tex && pdflatex -interaction=nonstopmode paper_scaffold.tex
	@echo "[✓] IEEEtran Paper Scaffold compiled -> $(OUT_DIR)/paper_scaffold.pdf"

pipeline:
	@echo "[+] Running full bibliometric pipeline..."
	uv run biblio-pipeline --file $(DATASET_FILE) --output $(OUT_DIR)

container-pipeline:
	@echo "[+] Running full bibliometric pipeline inside Container with GPU acceleration..."
	$(CONTAINER_ENGINE) run -it --rm $(GPU_FLAGS) $(MOUNT_FLAGS) $(IMAGE_NAME) --file $(DATASET_FILE) --output $(OUT_DIR)

container-query:
	@echo "[+] Running query collection and analysis inside Container with GPU acceleration..."
	$(CONTAINER_ENGINE) run -it --rm $(GPU_FLAGS) $(MOUNT_FLAGS) $(IMAGE_NAME) --query "$(QUERY)" --limit $(LIMIT) --start-year $(START_YEAR) --end-year $(END_YEAR) --output $(OUT_DIR)

clean:
	@echo "[+] Removing TeX build logs and auxiliary files..."
	@rm -f $(OUT_DIR)/*.aux $(OUT_DIR)/*.log $(OUT_DIR)/*.out $(OUT_DIR)/*.toc
