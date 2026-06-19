"""Logging fuer unterdrueckte Exceptions (pass ohne Programmfluss-Aenderung)."""

from __future__ import annotations

import logging
import sys

_log = logging.getLogger(__name__)


def log_suppressed_exception() -> None:
    """Protokolliert Datei und Zeilennummer des except-Blocks plus Fehler."""
    exc_type, exc, tb = sys.exc_info()
    if tb is not None:
        while tb.tb_next is not None:
            tb = tb.tb_next
        frame = tb.tb_frame
        _log.warning(
            "Unterdrueckter Fehler in %s:%s — %s: %s",
            frame.f_code.co_filename,
            tb.tb_lineno,
            exc_type.__name__ if exc_type else "Exception",
            exc,
        )
