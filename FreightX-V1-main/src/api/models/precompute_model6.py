"""
Precompute for Model 6.

Model 6 needs:
- standard FMCSA precomputed parquet files (carrier_base, insp_per_dot, etc.)
- centroids (used for MAX_DIST on some lane sizes)
- last_insp.parquet (for DAYS_SINCE_LAST_INSP filtering/sorting)

This follows the same wrapper style as precompute_model4.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import run_fmcsa_precompute, run_last_insp_precompute



def run():
    # baseline precompute outputs
    run_fmcsa_precompute(
        output_dir="precomputed_model6",
        include_centroids=True,
    )

    # Create last_insp.parquet for DAYS_SINCE_LAST_INSP.
    run_last_insp_precompute(output_dir="precomputed_model6")



if __name__ == "__main__":
    run()
