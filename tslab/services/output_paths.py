"""Output-Pfad-Hilfen ohne Flask-Abhaengigkeit (fuer Services & Web)."""

from __future__ import annotations

from pathlib import Path

from tslab.config_loader import resolve_output_dir


def output_root() -> Path:
    return resolve_output_dir().resolve()


def _strip_output_prefix(ref: str) -> str:
    clean = ref.replace("\\", "/").strip("/")
    if clean.startswith("output/"):
        return clean[7:]
    return clean


def output_ref(path: str | Path) -> str:
    """Relativer Speicherpfad unter output/ (DB, API, UI)."""
    if path is None or (isinstance(path, str) and not str(path).strip()):
        raise ValueError("output_dir fehlt.")
    root = output_root()
    p = Path(path)
    if p.is_absolute():
        try:
            resolved = p.resolve()
        except OSError as exc:
            raise ValueError(f"Output-Pfad ungueltig: {path!r}") from exc
        if not str(resolved).startswith(str(root)):
            raise ValueError(f"Output-Pfad liegt nicht unter {root}: {path!r}")
        return resolved.relative_to(root).as_posix()
    ref = _strip_output_prefix(str(path))
    if not ref or ref.startswith(".."):
        raise ValueError(f"Ungueltiger Output-Pfad: {path!r}")
    safe_resolve_output(ref)
    return ref


def safe_resolve_output(rel_path: str) -> Path:
    """rel_path relativ zu output/ — Path-Traversal verhindern."""
    root = output_root()
    clean = _strip_output_prefix(rel_path)
    target = (root / clean).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError(f"Ungueltiger Output-Pfad: {rel_path!r}")
    return target


def resolve_output_dir_arg(output_dir: str | Path) -> Path:
    """Gespeicherten oder uebergebenen Output-Verweis aufloesen."""
    return safe_resolve_output(output_ref(output_dir))


def relative_output_path(abs_path: str | Path) -> str | None:
    """Pfad in relativen output/-Verweis umwandeln."""
    try:
        return output_ref(abs_path)
    except ValueError:
        return None


def browse_url_for(rel_path: str | None) -> str | None:
    if not rel_path:
        return None
    try:
        ref = output_ref(rel_path)
    except ValueError:
        return None
    return f"/output/browse/{ref}"
