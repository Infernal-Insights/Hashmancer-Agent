import multiprocessing as mp
import os
from typing import Dict

from . import setup_agent, task_fetcher, hashcat_runner, watchdog_agent


class WorkerProcess(mp.Process):
    def __init__(self, gpu: Dict[str, str], worker_id: str):
        super().__init__()
        self.gpu = gpu
        self.worker_id = worker_id

    def run(self):
        width = int(self.gpu.get("pcie_width", "0"))
        device = self.gpu.get("index", "")
        fetcher = task_fetcher.TaskFetcher(width)
        if device:
            os.environ["CUDA_VISIBLE_DEVICES"] = str(device)
        while True:
            task = fetcher.fetch()
            if task:
                hashcat_runner.run_task(task, self.worker_id, device)


def main():
    worker_id = setup_agent.register_worker()
    gpu_info = setup_agent.collect_gpu_info()

    procs = [WorkerProcess(gpu, worker_id) for gpu in gpu_info]
    for p in procs:
        p.start()

    watchdog_agent.run_watchdog(worker_id)

    for p in procs:
        p.join()


if __name__ == "__main__":
    main()
