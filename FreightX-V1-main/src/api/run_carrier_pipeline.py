import os
import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
_SUBPROCESS_ENV = {**os.environ, "PYTHONUTF8": "1"}


def run_step(script: str) -> None:
    script_path = (API_DIR / script).resolve()
    print(f"Running {script_path}...")
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(script_path.parent),
        capture_output=True,
        text=True,
        env=_SUBPROCESS_ENV,
    )

    if result.returncode != 0:
        print(f"Error in {script_path}")
        print(result.stderr)
        if result.stdout:
            print(result.stdout)
        raise SystemExit(1)
    print(f"Finished {script_path}")
    if result.stdout:
        print(result.stdout)

# Step 1
run_step("../../data/Dataset_download_script.py")

run_step("../../scripts/main.py")

# Step 2
run_step("../../scripts/basics_ud.py")
run_step("../../scripts/basics_hos.py")
run_step("../../scripts/basics_vm.py")
run_step("../../scripts/basics_csa.py")
run_step("../../scripts/basics_df.py")

# Step 3
run_step("../../scripts/merge.py")

print("Pipeline completed successfully.")