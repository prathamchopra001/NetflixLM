"""EXP-017, container side: hold the `vlm` slot's Serve app up until a stop file appears.

    HF_HUB_OFFLINE=1 docker compose -f compose.yaml -f compose.dev.yaml up -d --wait ray-head
    MSYS_NO_PATHCONV=1 docker compose -f compose.yaml -f compose.dev.yaml exec -d ray-head \
        sh -c "NIP_VRAM_MARGIN_GB=0.25 python3 -m eval.exp.exp017_serve > /tmp/exp017.log 2>&1"

The host reads keyframes through Serve's port (`NIP_SERVE_URL=http://127.0.0.1:8001`), then
`touch /tmp/exp017.stop` in the container tears the app down (`serving.group` checks the VRAM is
back to idle). The log has one `UP {...}` line (idle VRAM, load seconds) and one `DOWN {...}`.
"""

import json
import sys
import time
from pathlib import Path

from nip import pipeline
from nip.contracts import Slot
from nip.runtime import serving
from nip.runtime.catalog import load_catalog

STOP = Path("/tmp/exp017.stop")
MAX_HOLD_S = 4 * 3600


def main() -> None:
    plan, inv = pipeline.current_plan({Slot.VLM: 1})
    if Slot.VLM in plan.skipped_slots:
        sys.exit(f"vlm skipped: {pipeline.slot_reason(plan, Slot.VLM)}")
    apps = serving.apps(plan, load_catalog(), inv, [Slot.VLM])
    STOP.unlink(missing_ok=True)
    with serving.group(apps, serving.ray_serve()) as rec:
        print("UP", json.dumps(rec), flush=True)
        t = time.monotonic()
        while not STOP.exists() and time.monotonic() - t < MAX_HOLD_S:
            time.sleep(2)
    print("DOWN", json.dumps(rec), flush=True)


if __name__ == "__main__":
    main()
