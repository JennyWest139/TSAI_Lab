"""Einfache Request-Timing-Logs fuer langsame UI-Pfade."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any

_log = logging.getLogger("tslab.perf")


def configure_perf_logging() -> None:
    if _log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
    _log.addHandler(handler)
    _log.setLevel(logging.INFO)


@contextmanager
def log_timing(label: str, **fields: Any):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000
        extra = " ".join(f"{k}={v}" for k, v in fields.items() if v is not None)
        _log.info("%s %.1f ms%s", label, ms, f" {extra}" if extra else "")
