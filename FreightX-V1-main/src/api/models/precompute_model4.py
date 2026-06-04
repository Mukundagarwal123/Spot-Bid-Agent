"""
Precompute for Model 4 — Pure inspection count sorting + lane-specific tail.
Includes county centroids (needed for MAX_DIST on 101-200 mi lanes).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_fmcsa_precompute


def run():
    run_fmcsa_precompute(
        output_dir="precomputed_model4",
        include_centroids=True,
    )


if __name__ == "__main__":
    run()
