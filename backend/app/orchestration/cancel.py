"""Cooperative cancellation: the executor checks this between steps.

A step that is already running (for example a remote GPU call) finishes first; the run then
stops before the next step. The UI labels Stop accordingly.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_requested: set[str] = set()


def request_cancel(job_id: str) -> None:
    with _lock:
        _requested.add(job_id)


def is_cancel_requested(job_id: str) -> bool:
    with _lock:
        return job_id in _requested


def clear(job_id: str) -> None:
    with _lock:
        _requested.discard(job_id)
