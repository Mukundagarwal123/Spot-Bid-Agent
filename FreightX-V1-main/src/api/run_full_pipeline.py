"""
Run carrier (data download + merge) first; run lane precompute only if carrier succeeds.

Use this as the single cron entry point on EC2, e.g.:
  cd /path/to/main/src/api && /path/to/venv/bin/python run_full_pipeline.py >> /var/log/pipeline.log 2>&1
"""

import os
import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
_SUBPROCESS_ENV = {**os.environ, "PYTHONUTF8": "1"}


def run_pipeline_script(name: str) -> int:
    script = API_DIR / name
    print(f"\n{'=' * 60}\nStarting {name}\n{'=' * 60}\n", flush=True)
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=str(API_DIR),
        env=_SUBPROCESS_ENV,
    ).returncode


def main() -> None:
    if run_pipeline_script("run_carrier_pipeline.py") != 0:
        print("\nCarrier pipeline failed - skipping lane pipeline.", flush=True)
        sys.exit(1)
    if run_pipeline_script("run_lane_pipeline.py") != 0:
        print("\nLane pipeline failed.", flush=True)
        sys.exit(1)
    print("\nFull pipeline completed successfully.", flush=True)


if __name__ == "__main__":
    main()
