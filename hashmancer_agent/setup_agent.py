import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict

import requests


CONFIG_FILE = Path(".env")
SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:8000")
WORKER_ID_FILE = Path(os.environ.get("WORKER_ID_FILE", "worker_id"))
PUBLIC_KEY_FILE = Path(os.environ.get("PUBLIC_KEY_FILE", "worker_public.pem"))


def prompt(key: str, default: str = "") -> str:
    """Prompt user for a value with an optional default."""
    return input(f"{key} [{default}]: ") or default


def write_config(server: str, redis_host: str, redis_port: str) -> None:
    """Persist connection settings to the CONFIG_FILE."""
    with CONFIG_FILE.open("w") as f:
        f.write(f"SERVER_URL={server}\n")
        f.write(f"REDIS_HOST={redis_host}\n")
        f.write(f"REDIS_PORT={redis_port}\n")
    print(f"Configuration written to {CONFIG_FILE}")


def install_python_requirements() -> None:
    """Install Python packages listed in requirements.txt."""
    req = Path("requirements.txt")
    if req.exists():
        print("Installing Python dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req)], check=False)


def _have(cmd: str) -> bool:
    return subprocess.run(["which", cmd], capture_output=True).returncode == 0


def install_system_packages() -> None:
    """Attempt to install hashcat and NVIDIA drivers using apt."""
    if not _have("hashcat"):
        print("Installing hashcat...")
        subprocess.run(["sudo", "apt-get", "update"], check=False)
        subprocess.run(["sudo", "apt-get", "-y", "install", "hashcat"], check=False)
    if not _have("nvidia-smi"):
        print("Installing NVIDIA drivers...")
        subprocess.run(["sudo", "apt-get", "-y", "install", "nvidia-driver-525"], check=False)


def _run_nvidia_smi() -> str:
    """Return raw output from nvidia-smi or an empty string if unavailable."""
    try:
        return subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,pci.link.width.max,memory.max_bandwidth,power.limit",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def collect_gpu_info() -> List[Dict[str, str]]:
    """Collect information for all detected GPUs."""
    output = _run_nvidia_smi()
    gpus: List[Dict[str, str]] = []
    for line in output.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 6:
            idx, name, mem, pcie, bandwidth, power = parts[:6]
        else:
            values = (parts + [""] * 6)[:6]
            idx, name, mem, pcie, bandwidth, power = values
        gpus.append(
            {
                "index": idx,
                "name": name,
                "memory": mem,
                "pcie_width": pcie,
                "memory_bandwidth": bandwidth,
                "power_limit": power,
            }
        )
    return gpus


def register_worker() -> str:
    """Register this worker with the server and return the worker id."""
    if WORKER_ID_FILE.exists():
        return WORKER_ID_FILE.read_text().strip()

    gpu_info = collect_gpu_info()
    try:
        pubkey = PUBLIC_KEY_FILE.read_text()
    except FileNotFoundError:
        pubkey = ""
    payload = {"gpus": gpu_info, "public_key": pubkey}
    resp = requests.post(f"{SERVER_URL}/register_worker", json=payload, timeout=30)
    resp.raise_for_status()
    worker_id = resp.json().get("waifu_name", "")
    if worker_id:
        WORKER_ID_FILE.write_text(worker_id)
    return worker_id


def main() -> None:
    print("Hashmancer-Agent setup and registration")
    global SERVER_URL
    server = prompt("SERVER_URL", SERVER_URL)
    redis_host = prompt("REDIS_HOST", os.environ.get("REDIS_HOST", "localhost"))
    redis_port = prompt("REDIS_PORT", os.environ.get("REDIS_PORT", "6379"))

    write_config(server, redis_host, redis_port)

    install_python_requirements()
    install_system_packages()

    # update runtime configuration for immediate registration
    SERVER_URL = server
    os.environ["SERVER_URL"] = server

    worker = register_worker()
    if worker:
        print(f"Registered worker id: {worker}")
    else:
        print("Worker registration failed")


if __name__ == "__main__":
    main()

