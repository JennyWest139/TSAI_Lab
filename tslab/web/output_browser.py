"""Sicherer Zugriff auf Output-Ordner (Grafiken, Berichte)."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from flask import abort, send_file

from tslab.services.output_paths import (
    browse_url_for,
    output_root,
    relative_output_path,
    safe_resolve_output,
)
from tslab.services.reporting_status import inspect_reporting_status, is_run_output_dir

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
_DOC_EXT = {".txt", ".csv", ".xlsx", ".pdf", ".html", ".json", ".docx"}


def resolve_output_path(rel_path: str) -> Path:
    try:
        return safe_resolve_output(rel_path)
    except ValueError:
        abort(403)


def list_directory(rel_path: str = "") -> dict:
    target = resolve_output_path(rel_path) if rel_path else output_root()
    if not target.is_dir():
        abort(404)

    entries = []
    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        rel = item.relative_to(output_root()).as_posix()
        entry: dict = {
            "name": item.name,
            "path": rel,
            "is_dir": item.is_dir(),
        }
        if item.is_file():
            entry["size"] = item.stat().st_size
            entry["ext"] = item.suffix.lower()
        elif is_run_output_dir(item):
            entry["reporting_status"] = inspect_reporting_status(item).to_dict()
        entries.append(entry)

    reporting_status = None
    if is_run_output_dir(target):
        reporting_status = inspect_reporting_status(target).to_dict()

    return {
        "path": rel_path or "",
        "parent": "/".join(rel_path.replace("\\", "/").strip("/").split("/")[:-1]),
        "entries": entries,
        "reporting_status": reporting_status,
    }


def serve_output_file(rel_path: str):
    target = resolve_output_path(rel_path)
    if not target.is_file():
        abort(404)
    if target.suffix.lower() not in _IMAGE_EXT | _DOC_EXT:
        abort(403)
    return send_file(target)


def zip_directory(rel_path: str = "") -> Path:
    """Erstellt temporaeres ZIP eines Output-Unterordners."""
    target = resolve_output_path(rel_path) if rel_path else output_root()
    if not target.is_dir():
        abort(404)
    tmp = Path(tempfile.mkstemp(suffix=".zip")[1])
    root_name = target.name or "output"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in target.rglob("*"):
            if item.is_file():
                arcname = f"{root_name}/{item.relative_to(target).as_posix()}"
                zf.write(item, arcname)
    return tmp


# Re-export fuer bestehende Imports
__all__ = [
    "browse_url_for",
    "list_directory",
    "output_root",
    "relative_output_path",
    "resolve_output_path",
    "serve_output_file",
    "zip_directory",
]
