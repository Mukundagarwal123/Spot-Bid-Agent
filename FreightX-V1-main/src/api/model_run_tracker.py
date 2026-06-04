"""Track run_my_model invocations and refresh Trimble API key every N runs."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

RUNS_BEFORE_KEY_REFRESH = 450

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COUNTER_FILE = _REPO_ROOT / "data" / "combined_model_run_count.json"
_ENV_FILE = _REPO_ROOT / ".env"


_last_run_count = 0
_last_key_refreshed = False


def get_combined_model_run_count() -> int:
    """Return how many times run_my_model has completed successfully."""
    return _read_count()


def get_last_run_stats() -> tuple[int, bool]:
    """Return (run_count, key_was_refreshed) from the most recent record_combined_model_run."""
    return _last_run_count, _last_key_refreshed


def _read_count() -> int:
    if not _COUNTER_FILE.is_file():
        return 0
    try:
        data = json.loads(_COUNTER_FILE.read_text(encoding="utf-8"))
        return int(data.get("count", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0


def _write_count(count: int) -> None:
    _COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    _COUNTER_FILE.write_text(
        json.dumps({"count": count}, indent=2),
        encoding="utf-8",
    )


def reload_trimble_api_key() -> None:
    """Reload TRIMBLE_API_KEY into config and lane_context after .env update."""
    load_dotenv(_ENV_FILE, override=True)
    key = os.environ.get("TRIMBLE_API_KEY")
    import config.config as cfg
    import models.lane_context as lc

    cfg.TRIMBLE_API_KEY = key
    lc.TRIMBLE_API_KEY = key


def increment_combined_model_run_count() -> int:
    """Increment and persist the successful run_my_model counter."""
    count = _read_count() + 1
    _write_count(count)
    return count


def refresh_trimble_key_if_due(count: int) -> bool:
    """Refresh Trimble API key when count hits RUNS_BEFORE_KEY_REFRESH."""
    if count % RUNS_BEFORE_KEY_REFRESH != 0:
        return False

    from web_agent import refresh_trimble_api_key

    if refresh_trimble_api_key():
        reload_trimble_api_key()
        return True
    return False


def record_combined_model_run() -> tuple[int, bool]:
    """
    Increment the run counter. Every RUNS_BEFORE_KEY_REFRESH successful runs,
    refresh the Trimble API key via web_agent.

    Returns (new_count, key_was_refreshed).
    """
    global _last_run_count, _last_key_refreshed
    count = increment_combined_model_run_count()
    refreshed = refresh_trimble_key_if_due(count)
    _last_run_count = count
    _last_key_refreshed = refreshed
    return count, refreshed
