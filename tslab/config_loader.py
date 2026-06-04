from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[1]


def load_defaults() -> dict[str, Any]:
    path = _ROOT / "config" / "defaults.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def project_root() -> Path:
    return _ROOT


def resolve_output_dir(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or load_defaults()
    out = _ROOT / cfg.get("output_dir", "output")
    out.mkdir(parents=True, exist_ok=True)
    return out
