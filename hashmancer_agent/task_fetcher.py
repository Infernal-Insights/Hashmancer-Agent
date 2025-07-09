import os
from typing import Any, Dict
import json
import redis

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
HIGH_QUEUE = os.environ.get("HIGH_QUEUE", "task:high")
LOW_QUEUE = os.environ.get("LOW_QUEUE", "task:low")


class TaskFetcher:
    def __init__(self, pcie_width: int):
        self.queue = HIGH_QUEUE if pcie_width >= 8 else LOW_QUEUE
        self.r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    def fetch(self) -> Dict[str, Any]:
        _, task_id = self.r.blpop(self.queue)
        task_key = f"task:{task_id}"
        data = self.r.get(task_key)
        if not data:
            return {}
        return json.loads(data)
