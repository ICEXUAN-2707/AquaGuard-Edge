import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process handle evidence")
def test_parent_crash_signals_child_exit():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(root))
    parent = subprocess.Popen([sys.executable, "-m", "experiments.parent_death_harness"],
                              cwd=root, env=env, stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    handle = None
    try:
        # communicate has a bounded timeout; output is emitted before abrupt exit.
        output, errors = parent.communicate("crash\n", timeout=15)
        assert parent.returncode == 23, errors
        pid = int(output.strip())
        handle = kernel.OpenProcess(0x00100000 | 0x0001, False, pid)
        if handle:
            assert kernel.WaitForSingleObject(handle, 5000) == 0
        else:
            # ERROR_INVALID_PARAMETER means this PID already ceased to exist.
            assert ctypes.get_last_error() == 87
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.communicate(timeout=5)
        if handle:
            if kernel.WaitForSingleObject(handle, 0) != 0:
                kernel.TerminateProcess(handle, 99)
                kernel.WaitForSingleObject(handle, 5000)
            kernel.CloseHandle(handle)
