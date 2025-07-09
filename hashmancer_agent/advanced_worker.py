"""Advanced worker for high-bandwidth GPUs (PCIe x8/x16).

This script registers the worker, filters GPUs with >=8 lane width, and runs
hashcat tasks using the normal worker manager components. It is intended for
rigs that can handle dictionary and hybrid attacks in addition to mask mode.
"""

from multiprocessing import Process
from typing import Dict, List

from . import setup_agent, worker_manager, watchdog_agent


class HighBWProcess(worker_manager.WorkerProcess):
    """Worker process restricted to GPUs with x8+ PCIe width."""

    def __init__(self, gpu: Dict[str, str], worker_id: str):
        super().__init__(gpu, worker_id)


def _filter_high_bandwidth(gpus: List[Dict[str, str]]) -> List[Dict[str, str]]:
    result = []
    for gpu in gpus:
        try:
            width = int(gpu.get("pcie_width", 0))
        except ValueError:
            width = 0
        if width >= 8:
            result.append(gpu)
    return result


def main() -> None:
    worker_id = setup_agent.register_worker()
    gpu_info = _filter_high_bandwidth(setup_agent.collect_gpu_info())
    if not gpu_info:
        print("No GPUs with x8 or higher PCIe width detected.")
        return

    procs: List[Process] = [HighBWProcess(g, worker_id) for g in gpu_info]
    for p in procs:
        p.start()

    watchdog_agent.run_watchdog(worker_id)

    for p in procs:
        p.join()


if __name__ == "__main__":
    main()
