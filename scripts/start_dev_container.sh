#!/bin/bash
# ==============================================================================
# PERSISTENT DEVELOPMENT CONTAINER LAUNCHER
# Starts a persistent background container named 'biblio-dev' with GPU support.
# Both you and the AI assistant can execute commands inside it via 'podman exec'.
# ==============================================================================

# Stop existing container if running
podman stop biblio-dev >/dev/null 2>&1
podman rm biblio-dev >/dev/null 2>&1

echo "Starting persistent GPU development container 'biblio-dev'..."

# Detect host libcuda library path
CUDA_LIB=$(ls /usr/lib/libcuda.so* 2>/dev/null | head -n 1)
CUDA_VOL=""
if [ -n "$CUDA_LIB" ]; then
    CUDA_VOL="-v /usr/lib/libcuda.so.1:/lib/x86_64-linux-gnu/libcuda.so.1:ro -v /usr/lib/libcuda.so.1:/usr/lib/x86_64-linux-gnu/libcuda.so.1:ro"
fi

podman run -d --name biblio-dev --rm \
  --device /dev/nvidia0 --device /dev/nvidiactl --device /dev/nvidia-uvm \
  $CUDA_VOL \
  -v .:/app:z \
  -p 8000:8000 \
  --entrypoint sleep \
  biblio-pipeline infinity

echo "================================================================================"
echo " SUCCESS: Development container 'biblio-dev' is now running in the background!"
echo "================================================================================"
echo " Useful Commands:"
echo "   1. Execute python command inside container (Host / AI Assistant):"
echo "      podman exec biblio-dev python -m src.pipeline --output pipeline_results_18k"
echo ""
echo "   2. Enter interactive bash prompt inside container (Your Terminal):"
echo "      podman exec -it biblio-dev bash"
echo ""
echo "   3. Stop background container:"
echo "      podman stop biblio-dev"
echo "================================================================================"
