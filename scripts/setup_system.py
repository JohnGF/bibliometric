import os
import sys
import shutil
import subprocess
import platform

def log(msg: str):
    print(f"\n[SystemSetup] {msg}")

def check_command(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def detect_gpu() -> bool:
    if check_command("nvidia-smi"):
        try:
            res = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True)
            gpu_name = res.stdout.strip()
            if gpu_name:
                log(f"NVIDIA GPU Detected: {gpu_name}")
                return True
        except Exception:
            pass
    return False

def setup_python_env(has_gpu: bool):
    log("Configuring Python Environment with 'uv'...")
    os.environ["UV_LINK_MODE"] = "copy"
    
    use_uv = check_command("uv")
    if not use_uv:
        log("Installing 'uv' package manager...")
        subprocess.run([sys.executable, "-m", "pip", "install", "uv"])

    pip_cmd = ["uv", "pip"] if use_uv else [sys.executable, "-m", "pip"]

    # Base requirements installation
    log("Installing core pipeline dependencies...")
    subprocess.run(pip_cmd + ["install", "-e", "."])

    if has_gpu:
        log("Installing Native GPU Acceleration (NVIDIA RAPIDS cuDF, cuGraph, cuML, PyTorch CUDA)...")
        # Install RAPIDS extra index packages
        rapids_pkgs = [
            "cudf-cu12",
            "cugraph-cu12",
            "cuml-cu12",
            "rmm-cu12",
            "cupy-cuda12x"
        ]
        cmd = pip_cmd + ["install", "--extra-index-url", "https://pypi.nvidia.com"] + rapids_pkgs
        subprocess.run(cmd)
        log("Native GPU RAPIDS & PyTorch CUDA setup complete!")
    else:
        log("CPU mode configured (No NVIDIA GPU detected).")

def setup_podman_cdi(has_gpu: bool):
    if not has_gpu or not check_command("podman"):
        return

    cdi_path = "/etc/cdi/nvidia.yaml"
    if os.path.exists(cdi_path):
        log(f"Podman NVIDIA CDI configuration verified at '{cdi_path}'.")
        return

    log("Checking Podman NVIDIA GPU pass-through (CDI)...")
    if check_command("nvidia-ctk"):
        log("Generating Podman CDI specification file...")
        try:
            subprocess.run(["sudo", "nvidia-ctk", "cdi", "generate", f"--output={cdi_path}"], check=True)
            log("Podman CDI GPU pass-through configured successfully!")
        except Exception as e:
            print(f"[SystemSetup] Note: Could not auto-generate CDI spec ({e}).")
    else:
        print("\n  [Podman GPU Setup Tip]")
        if os.path.exists("/etc/arch-release") or check_command("pacman"):
            print("  To enable '--device nvidia.com/gpu=all' in Podman on CachyOS / Arch, run:")
            print("    sudo pacman -S --needed nvidia-container-toolkit")
            print(f"    sudo nvidia-ctk cdi generate --output={cdi_path}")
        elif os.path.exists("/etc/debian_version") or check_command("apt"):
            print("  To enable '--device nvidia.com/gpu=all' in Podman on Debian / Ubuntu, run:")
            print("    sudo apt-get install -y nvidia-container-toolkit")
            print(f"    sudo nvidia-ctk cdi generate --output={cdi_path}")

def main():
    print("=" * 80)
    print("  BIBLIOMETRIC RESEARCH PIPELINE - SYSTEM-AWARE AUTOMATED SETUP")
    print("=" * 80)
    print(f"  OS Platform   : {platform.system()} ({platform.platform()})")
    print(f"  Python Version: {platform.python_version()}")

    has_gpu = detect_gpu()
    setup_python_env(has_gpu)
    setup_podman_cdi(has_gpu)

    print("\n" + "=" * 80)
    print("  SYSTEM SETUP COMPLETE!")
    print("  You can now run your pipeline natively or interactively:")
    print("    uv run biblio-pipeline --interactive --output pipeline_results_18k")
    print("    python run_local.py")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
