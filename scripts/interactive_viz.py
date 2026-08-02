import os
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import logging

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.viz import Visualization

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class InteractiveVizSession:
    """
    Holds graph network data and visualization configuration in memory.
    Allows instant parameter adjustments and re-rendering without reloading disk CSVs.
    """
    def __init__(self, output_dir: str = "pipeline_results"):
        self.output_dir = output_dir
        self.viz = Visualization()
        self.edges_df = None
        self.node_meta = None
        self.load_data()

    def load_data(self):
        edges_path = os.path.join(self.output_dir, "network_edges.csv")
        nodes_path = os.path.join(self.output_dir, "network_nodes.csv")

        if not (os.path.exists(edges_path) and os.path.exists(nodes_path)):
            candidates = [
                d for d in os.listdir(".")
                if os.path.isdir(d) and os.path.exists(os.path.join(d, "network_nodes.csv"))
            ]
            if candidates:
                print(f"[InteractiveViz] Note: '{self.output_dir}' has no pre-computed network files yet.")
                print(f"[InteractiveViz] Auto-detected existing network data in: {candidates}")
                self.output_dir = candidates[0]
                edges_path = os.path.join(self.output_dir, "network_edges.csv")
                nodes_path = os.path.join(self.output_dir, "network_nodes.csv")
                print(f"[InteractiveViz] Switching output directory to '{self.output_dir}'...")

        if os.path.exists(edges_path) and os.path.exists(nodes_path):
            print(f"[InteractiveViz] Loading network dataset from '{self.output_dir}' into memory...")
            self.edges_df = pd.read_csv(edges_path)
            self.node_meta = pd.read_csv(nodes_path)
            print(f"[InteractiveViz] SUCCESS: Loaded {len(self.node_meta):,} author nodes and {len(self.edges_df):,} edges into RAM!\n")
        else:
            print(f"[InteractiveViz] Warning: Could not find network_nodes.csv / network_edges.csv in '{self.output_dir}'")

    def render_network(self, top_per_community: int = 1, min_publications: int = 1, show_heatmap: bool = True, save: bool = True, show: bool = True):
        if self.edges_df is None or self.node_meta is None:
            print("[Error] No network data loaded in memory!")
            return

        filtered_nodes = self.node_meta.copy()
        filtered_edges = self.edges_df.copy()

        if min_publications > 1:
            filtered_nodes = filtered_nodes[filtered_nodes['num_publications'] >= min_publications]
            valid_vertices = set(filtered_nodes['vertex'])
            filtered_edges = filtered_edges[filtered_edges['source_id'].isin(valid_vertices) & filtered_edges['dest_id'].isin(valid_vertices)]

        save_path = os.path.join(self.output_dir, "network_graph.pdf") if save else None
        print(f"[InteractiveViz] Re-rendering Network Graph (nodes={len(filtered_nodes):,}, edges={len(filtered_edges):,}, top_per_community={top_per_community}, min_publications={min_publications}, heatmap={show_heatmap})...")
        
        fig = self.viz.plot_network(
            filtered_edges,
            filtered_nodes,
            save_path=save_path,
            top_per_community=top_per_community,
            show_heatmap=show_heatmap
        )

        if save_path:
            print(f"[InteractiveViz] Updated static graph saved to -> {save_path}")

        if show and fig is not None:
            try:
                plt.show(block=False)
                plt.pause(0.5)
            except Exception as e:
                print(f"[InteractiveViz] Note: Display non-GUI mode ({e}). Saved PDF output.")

    def render_cocitation(self, top_n: int = 30, save: bool = True):
        cocit_path = os.path.join(self.output_dir, "network_cocitations.csv")
        if not os.path.exists(cocit_path):
            print(f"[Error] No 'network_cocitations.csv' found in '{self.output_dir}'")
            return
            
        cocit_df = pd.read_csv(cocit_path)
        save_path = os.path.join(self.output_dir, "cocitation_graph.pdf") if save else None
        print(f"[InteractiveViz] Re-rendering Co-Citation Network Graph (top_n={top_n}, pairs={len(cocit_df):,})...")
        self.viz.plot_cocitation_network(cocit_df, top_n=top_n, save_path=save_path)
        if save_path:
            print(f"[InteractiveViz] Updated Co-Citation graph saved to -> {save_path}")

    def run_menu(self):
        """Runs a user-friendly interactive CLI command menu."""
        print("================================================================================")
        print("  INTERACTIVE GRAPH VISUALIZATION CLI ENGINE")
        print("================================================================================")
        print(" Commands:")
        print("   network <top_per_comm> <min_pub> [heatmap 0/1] -> Re-render network graph instantly")
        print("   python                                          -> Drop into Python REPL with RAM data")
        print("   reload                                          -> Reload CSV files from disk")
        print("   help                                            -> Print command menu")
        print("   exit                                            -> Quit interactive engine")
        print("================================================================================\n")

        while True:
            try:
                cmd_input = input("viz-engine> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting interactive engine.")
                break

            if not cmd_input:
                continue

            parts = cmd_input.split()
            cmd = parts[0].lower()

            if cmd in ("exit", "quit", "q"):
                print("Exiting interactive visualization engine.")
                break
            elif cmd == "help":
                print("\n  network <top_per_comm> <min_pub> [heatmap 0/1] - Render network with parameters")
                print("  python - Drop into Python REPL for raw inspection")
                print("  reload - Reload network CSVs from disk\n")
            elif cmd == "reload":
                self.load_data()
            elif cmd == "python":
                self.start_python_shell()
            elif cmd == "network":
                top_comm = int(parts[1]) if len(parts) > 1 else 1
                min_pub = int(parts[2]) if len(parts) > 2 else 1
                heatmap = bool(int(parts[3])) if len(parts) > 3 else True
                self.render_network(top_per_community=top_comm, min_publications=min_pub, show_heatmap=heatmap)
            else:
                print(f"Unknown command: '{cmd_input}'. Type 'help' or 'network 3 2' or 'python'.")

    def start_python_shell(self):
        import code
        banner = """
--------------------------------------------------------------------------------
  Interactive Python REPL (Data in RAM)
  In-memory variables:
    session  : InteractiveVizSession instance
    edges_df : Network edges DataFrame
    node_meta: Network node metadata DataFrame
    viz      : Visualization class instance

  Example snippet:
    session.render_network(top_per_community=3, min_publications=2)
--------------------------------------------------------------------------------
"""
        namespace = {
            "session": self,
            "edges_df": self.edges_df,
            "node_meta": self.node_meta,
            "viz": self.viz,
            "render_network": self.render_network,
            "plt": plt,
            "pd": pd,
        }
        code.interact(banner=banner, local=namespace)

def main():
    parser = argparse.ArgumentParser(description="Interactive Graph Visualization CLI Engine")
    parser.add_argument("--output", type=str, default="pipeline_results", help="Output directory containing network CSVs")
    parser.add_argument("--top-per-community", type=int, default=1, help="Top representative leaders per community")
    parser.add_argument("--min-publications", type=int, default=1, help="Minimum publications threshold")
    parser.add_argument("--python", action="store_true", help="Drop directly into Python shell")
    args = parser.parse_args()

    session = InteractiveVizSession(output_dir=args.output)
    if args.python:
        session.start_python_shell()
    else:
        # Render initial preview
        session.render_network(top_per_community=args.top_per_community, min_publications=args.min_publications)
        session.run_menu()

if __name__ == "__main__":
    main()
