"""EXP-017 in one `data/gpu.lock` hold: vlm app up in ray-head -> read the keyframes with the vision
model -> app down (VRAM back to idle) -> GPU timing of the OCR arm (seed 1, B-027 policy frames).

    GPU_LOCK_POLL_S=15 uv run python -m eval.exp.exp017_session

Container: the running ray-head (compose.dev.yaml); the host talks to Serve on 127.0.0.1:8001.
Afterwards: `exp017_vlm score` and `exp008_keyframes score` read the caches this writes.
"""

import os
import subprocess
import sys
import time

from eval.exp import exp008_keyframes as bench

CONTAINER = "netflixlm-ray-head-1"
SERVE_URL = "http://127.0.0.1:8001"
PY = sys.executable


def docker(*args: str, check: bool = True) -> str:
    r = subprocess.run(["docker", "exec", CONTAINER, *args], capture_output=True, text=True,
                       check=check)  # fmt: skip
    return r.stdout + r.stderr


def wait_for(marker: str, timeout_s: float) -> str:
    t = time.monotonic()
    while time.monotonic() - t < timeout_s:
        log = docker("sh", "-c", "cat /tmp/exp017.log 2>/dev/null", check=False)
        if marker in log or "Error" in log or "vlm skipped" in log:
            return log
        time.sleep(5)
    raise TimeoutError(f"no {marker!r} in /tmp/exp017.log after {timeout_s} s")


def main() -> None:
    with bench.gpu_lock("EXP-017 vlm arm + OCR GPU timing"):
        docker("sh", "-c", "rm -f /tmp/exp017.log /tmp/exp017.stop")
        subprocess.run(
            ["docker", "exec", "-d", CONTAINER, "sh", "-c",
             "NIP_VRAM_MARGIN_GB=0.25 python3 -m eval.exp.exp017_serve > /tmp/exp017.log 2>&1"],
            check=True,
        )  # fmt: skip
        try:
            log = wait_for("UP ", 1200)
            print(log[-600:], flush=True)
            if "UP " not in log:
                raise RuntimeError("vlm app did not come up")
            env = {**os.environ, "NIP_SERVE_URL": SERVE_URL, "PYTHONUNBUFFERED": "1"}
            subprocess.run([PY, "-m", "eval.exp.exp017_vlm", "read", "--seeds", "1,2,3"],
                           env=env, check=True)  # fmt: skip
        finally:
            docker("touch", "/tmp/exp017.stop", check=False)
            print(wait_for("DOWN ", 300)[-600:], flush=True)
        env = {**os.environ, "GPU_LOCK_HELD": "1", "PYTHONUNBUFFERED": "1"}
        subprocess.run([PY, "-m", "eval.exp.exp008_keyframes", "scan", "--seeds", "1",
                        "--arm", "1-per-shot+2s"], env=env, check=True)  # fmt: skip


if __name__ == "__main__":
    main()
