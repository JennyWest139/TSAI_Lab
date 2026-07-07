"""Hilfen fuer oekonometrische Schaetzung (Warnungen)."""

from __future__ import annotations

import warnings
from contextlib import contextmanager


@contextmanager
def suppress_optimizer_warnings():
    """Unkritische SciPy-Line-Search-Meldungen bei MLE (Ergebnis bleibt nutzbar)."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=".*line search algorithm did not converge.*",
        )
        warnings.filterwarnings(
            "ignore",
            message=".*Maximum Likelihood optimization failed to converge.*",
        )
        yield
