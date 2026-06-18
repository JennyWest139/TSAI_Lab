"""Gemeinsames Einlesen von Upload-Dateien (CSV/Excel)."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd


def read_raw_text(data: bytes, filename: str) -> tuple[str, str]:
    for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8"


def guess_sep(text: str) -> str:
    first = text.splitlines()[0] if text else ""
    if ";" in first and first.count(";") >= first.count(","):
        return ";"
    if "\t" in first:
        return "\t"
    return ","


def load_upload_dataframe(data: bytes, filename: str) -> tuple[pd.DataFrame, str, str]:
    """Liest CSV oder Excel in ein DataFrame (dtype=str)."""
    ext = Path(filename).suffix.lower()
    if ext in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(io.BytesIO(data), dtype=str)
            return df, ";", "excel"
        except ImportError as exc:
            raise ValueError(
                "Excel-Dateien benoetigen openpyxl: pip install openpyxl"
            ) from exc

    text, encoding = read_raw_text(data, filename)
    sep = guess_sep(text)
    df = pd.read_csv(io.StringIO(text), sep=sep, encoding=encoding, dtype=str)
    return df, sep, encoding


def load_upload_dataframe_from_path(path: Path) -> tuple[pd.DataFrame, str, str]:
    return load_upload_dataframe(path.read_bytes(), path.name)
