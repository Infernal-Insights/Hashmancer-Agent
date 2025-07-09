import json
import os
from pathlib import Path
from typing import Dict

import requests

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives import serialization
except Exception:  # pragma: no cover
    hashes = padding = rsa = serialization = None  # type: ignore

SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:8000")
PRIVATE_KEY_FILE = Path(os.environ.get("PRIVATE_KEY_FILE", "worker_private.pem"))


def _load_private_key():
    if not PRIVATE_KEY_FILE.exists() or not serialization:
        return None
    data = PRIVATE_KEY_FILE.read_bytes()
    return serialization.load_pem_private_key(data, password=None)


def _sign_payload(data: bytes) -> str | None:
    key = _load_private_key()
    if not key:
        return None
    signature = key.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return signature.hex()


def _post(endpoint: str, payload: Dict[str, str]):
    body = json.dumps(payload).encode()
    sig = _sign_payload(body)
    headers = {"Content-Type": "application/json"}
    if sig:
        headers["X-Worker-Signature"] = sig
    resp = requests.post(f"{SERVER_URL}{endpoint}", data=body, headers=headers, timeout=30)
    resp.raise_for_status()


def submit_founds(worker_id: str, founds: str):
    payload = {"worker_id": worker_id, "founds": founds}
    _post("/submit_founds", payload)


def submit_no_founds(worker_id: str):
    payload = {"worker_id": worker_id}
    _post("/submit_no_founds", payload)
