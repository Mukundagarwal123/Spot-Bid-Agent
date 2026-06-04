"""
Precompute for Model 2 — Pure HQ proximity.
No county centroids needed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_fmcsa_precompute


def run():
    run_fmcsa_precompute(
        output_dir="precomputed_model2",
        include_centroids=False,
    )


if __name__ == "__main__":
    run()
