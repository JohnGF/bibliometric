# Use RAPIDS 25.06 with CUDA 12.8 to match the host's 12.8 driver
FROM nvcr.io/nvidia/rapidsai/base:25.06-cuda12.8-py3.11

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvbin/uv

WORKDIR /app

# Copy the dependency files and src first
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src

# Install project dependencies
# We explicitly use cu124 index and pin to cu12 to prevent pulling in CUDA 13
RUN /uvbin/uv pip install --system --no-cache \
    --extra-index-url https://download.pytorch.org/whl/cu124 \
    "torch<2.6.0" \
    "nvidia-cuda-runtime-cu12" \
    "nvidia-cudnn-cu12" \
    "nvidia-cublas-cu12" \
    "nvidia-curand-cu12" \
    "nvidia-cusolver-cu12" \
    "nvidia-cusparse-cu12" \
    "nvidia-nccl-cu12" \
    "nvidia-nvtx-cu12" \
    "python-louvain" \
    .

LABEL maintainer="Bibliometric Research Team"
LABEL description="Containerized Bibliometric Research Pipeline with GPU support and FastAPI Backend"

# Set environment variables for the SSD and GPU
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV UV_LINK_MODE=copy

# Volume for data and results
VOLUME ["/app/data", "/app/pipeline_results"]

# FastAPI port
EXPOSE 8000

# The entrypoint will use the RAPIDS environment's python
ENTRYPOINT ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
