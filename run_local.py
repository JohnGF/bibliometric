import subprocess
import sys
import os
import signal
import time

def run():
    print("=== Initializing Bibliometric Pipeline (Cross-Platform) ===")
    
    # Check if 'uv' is available
    use_uv = False
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        use_uv = True
    except Exception:
        pass
        
    if use_uv:
        print("Using 'uv' for dependency management...")
        subprocess.run(["uv", "pip", "install", "-e", "."])
    else:
        print("'uv' not found. Falling back to standard pip...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."])
        
    # Check Node.js dependencies
    frontend_dir = os.path.join(os.getcwd(), "frontend")
    if not os.path.exists(os.path.join(frontend_dir, "node_modules")):
        print("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=frontend_dir, shell=(os.name == 'nt'))

    print("Starting Backend API on port 8000...")
    # Find Python executable
    python_bin = sys.executable
    backend_cmd = [python_bin, "-m", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--port", "8000"]
    if use_uv:
        backend_cmd = ["uv", "run", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--port", "8000"]
        
    backend_proc = subprocess.Popen(backend_cmd, env=os.environ.copy())
    
    print("Starting Frontend App on port 3000...")
    frontend_env = os.environ.copy()
    frontend_env["NEXT_PUBLIC_API_URL"] = "http://localhost:8000"
    
    frontend_cmd = ["npm", "run", "dev", "--", "-p", "3000"]
    frontend_proc = subprocess.Popen(frontend_cmd, cwd=frontend_dir, env=frontend_env, shell=(os.name == 'nt'))
    
    def cleanup(signum, frame):
        print("\nStopping servers...")
        backend_proc.terminate()
        frontend_proc.terminate()
        backend_proc.wait()
        frontend_proc.wait()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Wait for processes
    try:
        while True:
            if backend_proc.poll() is not None:
                print("Backend process terminated.")
                break
            if frontend_proc.poll() is not None:
                print("Frontend process terminated.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup(None, None)

if __name__ == "__main__":
    run()
