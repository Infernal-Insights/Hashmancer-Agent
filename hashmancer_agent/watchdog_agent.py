import os
import subprocess
import time
from typing import Dict

import requests

SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:8000")


def get_gpu_metrics() -> Dict[str, str]:
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=temperature.gpu,fan.speed,power.draw",
                "--format=csv,noheader,nounits",
            ],
            text=True,
        )
        temps, fan, power = out.strip().split(',')
        return {
            "temperature": temps.strip(),
            "fan_speed": fan.strip(),
            "power_draw": power.strip(),
        }
    except Exception:
        return {}


def send_metrics(worker_id: str):
    metrics = get_gpu_metrics()
    if not metrics:
        return
    payload = {"worker_id": worker_id, "metrics": metrics}
    try:
        requests.post(f"{SERVER_URL}/log_watchdog_event", json=payload, timeout=15)
    except requests.RequestException:
        pass


def run_watchdog(worker_id: str, interval: int = 60):
    while True:
        send_metrics(worker_id)
        time.sleep(interval)
