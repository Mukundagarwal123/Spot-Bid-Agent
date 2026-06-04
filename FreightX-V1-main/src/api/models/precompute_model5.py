"""
Precompute for Model 5 — Full mix model (best model so far).
Includes county centroids (needed for MAX_DIST on 101-200 mi lanes).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_fmcsa_precompute


def run():
    run_fmcsa_precompute(
        output_dir="precomputed_model5",
        include_centroids=True,
    )


if __name__ == "__main__":
    run()
