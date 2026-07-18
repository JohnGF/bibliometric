import os
import shutil
import subprocess
import sys

def verify():
    print("=== Running Pipeline Integration Test ===")
    
    test_output_dir = "pipeline_test_results"
    if os.path.exists(test_output_dir):
        shutil.rmtree(test_output_dir)
        
    query = "quantum gravity"
    limit = 2
    
    print(f"Running biblio-pipeline CLI with query='{query}', limit={limit}, output_dir='{test_output_dir}'...")
    
    cmd = [
        sys.executable, "-m", "src.pipeline",
        "--query", query,
        "--limit", str(limit),
        "--start-year", "2024",
        "--end-year", "2025",
        "--output", test_output_dir
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("Pipeline executed successfully!")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Pipeline execution FAILED with exit code:", e.returncode)
        print("--- STDOUT ---")
        print(e.stdout)
        print("--- STDERR ---")
        print(e.stderr)
        sys.exit(1)
        
    expected_files = [
        "yearly_growth.pdf",
        "network_edges.csv",
        "network_nodes.csv",
        "network_graph.pdf"
    ]
    
    print("\nVerifying output files...")
    missing_files = []
    for f in expected_files:
        path = os.path.join(test_output_dir, f)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  [OK] {f} exists ({size} bytes)")
        else:
            print(f"  [MISSING] {f}")
            missing_files.append(f)
            
    collected_data_path = f"data/collected_{query.replace(' ', '_')}.csv"
    if os.path.exists(collected_data_path):
        size = os.path.getsize(collected_data_path)
        print(f"  [OK] {collected_data_path} exists ({size} bytes)")
    else:
        print(f"  [MISSING] {collected_data_path}")
        missing_files.append(collected_data_path)
        
    if os.path.exists(test_output_dir):
        shutil.rmtree(test_output_dir)
        print(f"\nCleaned up test directory '{test_output_dir}'.")
        
    if missing_files:
        print(f"\nIntegration test FAILED. Missing files: {missing_files}")
        sys.exit(1)
    else:
        print("\nIntegration test PASSED successfully!")
        sys.exit(0)

if __name__ == "__main__":
    verify()
