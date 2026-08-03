"""
DEPRECATED: This file is kept for backwards compatibility.
Please use `src/cli.py` to run the pipeline, or import from `src.orchestrators.pipeline_manager` for API usage.
"""

from src.orchestrators.pipeline_manager import PipelineManager
from src.cli import main as cli_main

# Re-export BibliometricPipeline mapping to PipelineManager to avoid breaking existing imports (like src/api/main.py)
BibliometricPipeline = PipelineManager

def main():
    cli_main()

if __name__ == "__main__":
    main()
