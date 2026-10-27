"""Exercise the actual service process and common startup failures."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request


def _env(**updates: str) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("AQUAGUARD_DEVICE_ID", None)
    env.update(updates)
    return env


def test_missing_device_id_has_clear_error() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "edge"], env=_env(), capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 2
    assert "AQUAGUARD_DEVICE_ID is required" in result.stderr


def test_occupied_port_has_clear_error() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen()
        port = holder.getsockname()[1]
        result = subprocess.run(
            [sys.executable, "-m", "edge"],
            env=_env(AQUAGUARD_DEVICE_ID="home01", AQUAGUARD_PORT=str(port)),
            capture_output=True,
            text=True,
            timeout=10,
        )
    assert result.returncode == 2
    assert f"Cannot listen on 127.0.0.1:{port}" in result.stderr


def test_start_health_and_stop() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind(("127.0.0.1", 0))
        port = holder.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "edge"],
        env=_env(AQUAGUARD_DEVICE_ID="home01", AQUAGUARD_PORT=str(port)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise AssertionError(f"service exited early: {process.communicate()}")
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5) as response:
                    assert response.status == 200
                    assert json.load(response) == {"status": "ok", "device_id": "home01"}
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.1)
        else:
            raise AssertionError("service did not answer /health within 10 seconds")
    finally:
        process.terminate()
        process.communicate(timeout=10)
    assert process.returncode is not None
