"""Gemeinsame Output-Pfad-Fixtures fuer Tests (relativ zu output/)."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator
from unittest.mock import patch


@contextmanager
def temp_output_run(name: str = "test_run") -> Iterator[Path]:
    """Temporaeres Laufverzeichnis unter einer gemockten output/-Wurzel."""
    with TemporaryDirectory() as tmp:
        out_root = Path(tmp) / "output"
        out_root.mkdir()
        run = out_root / name
        run.mkdir()
        with patch(
            "tslab.services.output_paths.resolve_output_dir",
            lambda cfg=None: out_root,
        ):
            yield run
