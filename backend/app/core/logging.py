import base64
import contextvars
import json
import logging
import queue
import threading
from typing import Any

import httpx
import structlog

from app.core.settings import settings

correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


class LokiLogHandler(logging.Handler):
    """Lightweight async-safe handler that pushes JSON logs to Grafana Loki."""

    def __init__(self, url: str, username: str, api_key: str, service: str) -> None:
        super().__init__()
        self.url = url
        self.service = service
        token = base64.b64encode(f"{username}:{api_key}".encode("utf-8")).decode("utf-8")
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }
        self.q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=10000)
        self._stop = threading.Event()
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "ts": str(int(record.created * 1_000_000_000)),
                "line": self.format(record),
                "level": record.levelname.lower(),
                "logger": record.name,
            }
            self.q.put_nowait(entry)
        except Exception:
            self.handleError(record)

    def _worker(self) -> None:
        client = httpx.Client(timeout=5.0)
        while not self._stop.is_set():
            batch: list[dict[str, Any]] = []
            try:
                batch.append(self.q.get(timeout=0.5))
                while len(batch) < 200:
                    batch.append(self.q.get_nowait())
            except queue.Empty:
                if not batch:
                    continue

            values = [[row["ts"], row["line"]] for row in batch]
            payload = {
                "streams": [
                    {
                        "stream": {
                            "service": self.service,
                            "env": settings.app_env,
                            "logger": "app",
                        },
                        "values": values,
                    }
                ]
            }
            try:
                client.post(self.url, headers=self.headers, content=json.dumps(payload))
            except Exception:
                # Do not crash app if log sink is temporarily unavailable.
                pass

    def close(self) -> None:
        self._stop.set()
        super().close()


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(message)s",
    )

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.contextvars.merge_contextvars,
            _inject_correlation_id,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    if (
        settings.grafana_cloud_loki_url
        and settings.grafana_cloud_loki_username
        and settings.grafana_cloud_loki_api_key
    ):
        handler = LokiLogHandler(
            url=settings.grafana_cloud_loki_url,
            username=settings.grafana_cloud_loki_username,
            api_key=settings.grafana_cloud_loki_api_key,
            service=settings.app_name,
        )
        handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
        handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(handler)


def _inject_correlation_id(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    cid = correlation_id_var.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict
