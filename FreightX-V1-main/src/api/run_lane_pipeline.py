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


run_step("./models/mapping_equip.py")
run_step("./models/data_handling.py")
run_step("./models/precompute_enrichment.py")

run_step("./models/precompute_model1.py")
run_step("./models/precompute_model2.py")
run_step("./models/precompute_model3.py")
run_step("./models/precompute_model4.py")
run_step("./models/precompute_model5.py")
run_step("./models/precompute_model6.py")

print("Pipeline completed successfully.")
