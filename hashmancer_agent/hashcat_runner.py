import os
import subprocess
from pathlib import Path
from typing import Dict

from . import results_client

HASHCAT_BIN = os.environ.get("HASHCAT_BIN", "hashcat")
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "outputs"))
OUTPUT_DIR.mkdir(exist_ok=True)


def build_command(task: Dict[str, str], device: str | None = None) -> list[str]:
    hashes = task.get("hashes")
    mask = task.get("mask")
    wordlist = task.get("wordlist")
    mode = task.get("attack_mode", "mask")

    cmd = [HASHCAT_BIN, "--potfile-disable"]
    if device:
        cmd += ["-d", str(device)]
    if mode == "mask":
        cmd += ["-a", "3", hashes, mask]
    elif mode == "dict":
        cmd += ["-a", "0", hashes, wordlist]
    elif mode == "hybrid":
        cmd += ["-a", "6", hashes, wordlist, mask]
    return cmd


def run_task(task: Dict[str, str], worker_id: str, device: str | None = None) -> None:
    cmd = build_command(task, device)
    output_file = OUTPUT_DIR / f"{worker_id}_found.txt"
    env = os.environ.copy()
    env["HC_OUTFILE"] = str(output_file)

    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if output_file.exists() and output_file.stat().st_size > 0:
        results_client.submit_founds(worker_id, output_file.read_text())
    else:
        results_client.submit_no_founds(worker_id)
    if proc.returncode != 0:
        print(proc.stderr)
