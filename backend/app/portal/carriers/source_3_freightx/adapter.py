from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


class FreightXModelError(Exception):
    """Raised when the FreightX combine_model call fails."""


def run_freightx_model(
    origin_zip: str,
    dest_zip: str,
    equipment_type: str,
    freightx_src_api_path: str,
) -> "pd.DataFrame":
    """
    Inject FreightX-V1/src/api onto sys.path and call run_my_model().

    The FreightX package uses bare imports (e.g. `from models.helpers import ...`)
    so it must be on sys.path rather than installed as a package.
    This is the only file in the portal that touches combine_model.
    """
    src_path = str(Path(freightx_src_api_path).resolve())
    project_root = str(Path(freightx_src_api_path).resolve().parents[1])  # FreightX-V1/
    for p in (src_path, project_root):
        if p not in sys.path:
            sys.path.insert(0, p)

    try:
        from models.combine_model import run_my_model  # type: ignore[import]
    except ImportError as exc:
        raise FreightXModelError(f"FreightX model not importable: {exc}") from exc

    try:
        return run_my_model(
            source_zip=origin_zip,
            dest_zip=dest_zip,
            equipment_list=[equipment_type],
        )
    except ValueError as exc:
        # clean_zip() raises ValueError for invalid ZIP formats — surface as validation signal
        raise FreightXModelError(str(exc)) from exc
    except Exception as exc:
        raise FreightXModelError(f"model_execution_failed: {type(exc).__name__}: {exc}") from exc
