"""Sicherer Zugriff auf Output-Ordner (Grafiken, Berichte)."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from flask import abort, send_file

from tslab.config_loader import resolve_output_dir

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
_DOC_EXT = {".txt", ".csv", ".xlsx", ".pdf", ".html", ".json", ".docx"}


def output_root() -> Path:
    return resolve_output_dir().resolve()


def resolve_output_path(rel_path: str) -> Path:
    """rel_path relativ zu output/ — Path-Traversal verhindern."""
    root = output_root()
    clean = rel_path.replace("\\", "/").strip("/")
    target = (root / clean).resolve()
    if not str(target).startswith(str(root)):
        abort(403)
    return target


def relative_output_path(abs_path: str | Path) -> str | None:
    """Absoluten Pfad in relativen output/-Pfad umwandeln."""
    root = output_root()
    try:
        target = Path(abs_path).resolve()
    except OSError:
        return None
    if not str(target).startswith(str(root)):
        return None
    return target.relative_to(root).as_posix()


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
        entries.append(entry)

    return {
        "path": rel_path or "",
        "parent": "/".join(rel_path.replace("\\", "/").strip("/").split("/")[:-1]),
        "entries": entries,
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


def browse_url_for(rel_path: str | None) -> str | None:
    if not rel_path:
        return None
    rel = relative_output_path(rel_path)
    if rel is None:
        # bereits relativ?
        if not rel_path.replace("\\", "/").startswith(".."):
            rel = rel_path.replace("\\", "/").lstrip("/")
        else:
            return None
    return f"/output/browse/{rel}"
