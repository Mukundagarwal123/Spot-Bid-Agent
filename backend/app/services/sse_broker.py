from __future__ import annotations

import json
import queue
import threading
from collections.abc import Generator


class SseBroker:
    """Thread-safe pub/sub broker for Server-Sent Events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[queue.Queue[dict]] = []

    def subscribe(self) -> queue.Queue[dict]:
        q: queue.Queue[dict] = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[dict]) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def publish(self, event: dict) -> None:
        with self._lock:
            dead: list[queue.Queue[dict]] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                try:
                    self._subscribers.remove(q)
                except ValueError:
                    pass

    def stream(self, q: queue.Queue[dict], heartbeat_secs: int = 20) -> Generator[str, None, None]:
        try:
            yield 'data: {"type":"connected"}\n\n'
            while True:
                try:
                    event = q.get(timeout=heartbeat_secs)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    yield 'data: {"type":"ping"}\n\n'
        except GeneratorExit:
            pass
        finally:
            self.unsubscribe(q)


# Module-level singleton — import this wherever you need to publish or stream
whatsapp_sse = SseBroker()
