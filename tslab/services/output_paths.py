"""Output-Pfad-Hilfen ohne Flask-Abhaengigkeit (fuer Services & Web)."""

from __future__ import annotations

from pathlib import Path

from tslab.config_loader import resolve_output_dir


def output_root() -> Path:
    return resolve_output_dir().resolve()


def safe_resolve_output(rel_path: str) -> Path:
    """rel_path relativ zu output/ — Path-Traversal verhindern."""
    root = output_root()
    clean = rel_path.replace("\\", "/").strip("/")
    target = (root / clean).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError(f"Ungueltiger Output-Pfad: {rel_path!r}")
    return target


def resolve_output_dir_arg(output_dir: str | Path) -> Path:
    """Absoluten Ordner oder relativen output/-Pfad aufloesen."""
    path = Path(output_dir)
    if path.is_dir():
        return path.resolve()
    return safe_resolve_output(str(output_dir))


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


def browse_url_for(rel_path: str | None) -> str | None:
    if not rel_path:
        return None
    rel = relative_output_path(rel_path)
    if rel is None:
        if not rel_path.replace("\\", "/").startswith(".."):
            rel = rel_path.replace("\\", "/").lstrip("/")
        else:
            return None
    return f"/output/browse/{rel}"
