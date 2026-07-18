    podman run --rm -it \
      --device nvidia.com/gpu=all \
      -p 8550:8550 \
      -v ./pipeline_results:/app/pipeline_results:Z \
      localhost/bibliometric-pipeline

