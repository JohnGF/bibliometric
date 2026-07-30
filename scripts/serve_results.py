import http.server
import socketserver
import os
import sys

PORT = 8550
BIND_HOST = "0.0.0.0"

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

def run_server(port=PORT):
    workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(workspace_dir)
    
    handler = CustomHandler
    with socketserver.TCPServer((BIND_HOST, port), handler) as httpd:
        print(f"==================================================")
        print(f"  Bibliometric Results Server Live on VPN/Network ")
        print(f"==================================================")
        print(f" Local Address : http://localhost:{port}")
        print(f" VPN / Network : http://0.0.0.0:{port} (Use your 10.0.0.x IP)")
        print(f" Direct Links:")
        print(f"   - Broad Corpus Results  : http://localhost:{port}/pipeline_results_broad_33k/")
        print(f"   - Narrow Corpus Results : http://localhost:{port}/pipeline_results_narrow_query/")
        print(f"   - PDF Graph (Broad)     : http://localhost:{port}/pipeline_results_broad_33k/network_graph.pdf")
        print(f"   - Research Lines (CSV)  : http://localhost:{port}/pipeline_results_broad_33k/topic_research_lines.csv")
        print(f"==================================================\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_server(port_arg)
