import os
import json
import time
import subprocess
from pathlib import Path

import redis
from multiprocessing import Process

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
WORK_QUEUE = os.environ.get("WORK_QUEUE", "work_queue")
RESULT_QUEUE = os.environ.get("RESULT_QUEUE", "results")
HASH_MODE = os.environ.get("HASH_MODE", "0")  # MD5 by default
MASK = os.environ.get("MASK", "?l?l?l?l?d?d")
HASHCAT_BIN = os.environ.get("HASHCAT_BIN", "hashcat")
HASH_FILE = Path("hashes.txt")


def _redis_conn():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

def get_pcie_info():
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,pci.bus_id,pci.link_width,pci.link_gen",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        )
        info = []
        for line in out.strip().splitlines():
            info.append(tuple(p.strip() for p in line.split(',')))
        return info
    except Exception:
        return []


def fetch_task(r):
    data = r.lpop(WORK_QUEUE)
    if not data:
        return None
    return json.loads(data)


def run_hashcat(task_id, hashes, device):
    HASH_FILE.write_text("\n".join(hashes))
    output_file = f"cracked_{task_id}.txt"
    cmd = [
        HASHCAT_BIN, "-a", "3",
        "-m", HASH_MODE,
        str(HASH_FILE),
        MASK,
        "-d", str(device),
        "--outfile", output_file,
        "--quiet",
        "--hwmon-temp-abort", "90",
        "--gpu-temp-retain", "70",
        "--force",
    ]
    subprocess.run(cmd)
    if Path(output_file).exists():
        results = Path(output_file).read_text().splitlines()
        r = _redis_conn()
        r.rpush(RESULT_QUEUE, json.dumps({"task_id": task_id, "results": results}))


def worker_loop(device: str) -> None:
    r = _redis_conn()
    while True:
        task = fetch_task(r)
        if not task:
            time.sleep(10)
            continue
        run_hashcat(task["id"], task["hashes"], device)


def main():
    pcie = get_pcie_info()
    low_gpus = [(idx, bus, width, gen) for idx, bus, width, gen in pcie if int(width) <= 4]
    if not low_gpus:
        print("No low-bandwidth GPUs detected.")
        return
    procs = []
    for idx, bus, width, gen in low_gpus:
        print(f"GPU {bus} (index {idx}): x{width} Gen{gen}")
        p = Process(target=worker_loop, args=(idx,))
        p.start()
        procs.append(p)
    for p in procs:
        p.join()


if __name__ == "__main__":
    main()
