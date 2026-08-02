import os
import sys
import argparse

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.interactive_viz import InteractiveVizSession

def main():
    parser = argparse.ArgumentParser(description="Instant Network Graph Renderer for Outside Shells")
    parser.add_argument("--folder", type=str, default="pipeline_results", help="Folder containing network CSVs")
    parser.add_argument("--top-per-community", type=int, default=1, help="Top representative leaders per community")
    parser.add_argument("--min-publications", type=int, default=1, help="Minimum publications threshold")
    parser.add_argument("--no-heatmap", action="store_true", help="Disable density heatmap background")
    args = parser.parse_args()

    session = InteractiveVizSession(output_dir=args.folder)
    session.render_network(
        top_per_community=args.top_per_community,
        min_publications=args.min_publications,
        show_heatmap=not args.no_heatmap,
        show=False,
        save=True
    )

if __name__ == "__main__":
    main()
