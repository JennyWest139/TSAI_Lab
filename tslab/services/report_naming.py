"""Dateinamen fuer KI-Berichte (TSA, CORR, Modellvergleich)."""

from __future__ import annotations

import re
from pathlib import Path


def ai_model_filename_suffix(*, model_label: str = "", model_id: str = "") -> str:
    """z. B. GPT-5-nano, GPT-4o-mini, OhneKI."""
    if not str(model_label or "").strip() and not str(model_id or "").strip():
        return "OhneKI"
    label = str(model_label or "").strip()
    if not label and model_id:
        label = str(model_id).split(":")[-1]
    return label.replace(" ", "-")


def tsa_model_folder_tag(folder_name: str) -> str:
    """arma11_garch11 -> ARMA11GARCH11."""
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", folder_name)
    return cleaned.upper() or "MODELL"


def tsa_model_report_basename(folder_name: str, ai_suffix: str) -> str:
    tag = tsa_model_folder_tag(folder_name)
    return f"TSA_Modell_Bericht_{tag}_{ai_suffix}.docx"


def corr_report_basename(ai_suffix: str) -> str:
    return f"CORR_AI_Bericht_{ai_suffix}.docx"


def modellvergleich_basename(ai_suffix: str) -> str:
    return f"Modellvergleich_{ai_suffix}.docx"


_AI_REPORT_PREFIXES = (
    "tsa_modell_bericht_",
    "tsa_bericht_",
    "corr_ai_bericht_",
    "corr_bericht_",
    "modellvergleich_",
)


def is_generated_report_artifact(name: str) -> bool:
    """TXT-Scan: bereits erzeugte Berichte nicht erneut einlesen."""
    lower = name.lower()
    legacy = (
        "ai_bericht.docx",
        "ai_bericht.pdf",
        "modellvergleich.docx",
        "modellvergleich.pdf",
    )
    if lower in legacy:
        return True
    if not lower.endswith((".docx", ".pdf")):
        return False
    return any(lower.startswith(prefix) for prefix in _AI_REPORT_PREFIXES)


def _ai_report_suffix_from_name(name: str) -> str | None:
    """Dateiname -> KI-Suffix (z. B. GPT-4o-mini), falls erkennbar."""
    lower = name.lower()
    for prefix in _AI_REPORT_PREFIXES:
        if not lower.startswith(prefix):
            continue
        stem = Path(name).stem
        return stem[len(prefix) :]
    return None


def purge_ai_reports_for_other_models(
    run_root,
    *,
    keep_suffix: str,
    include_reports_subdir: bool = True,
) -> list[str]:
    """Entfernt KI-Berichte anderer Modelle im Lauf-Ordner (und optional Reports/)."""
    root = Path(run_root)
    if not root.is_dir():
        return []
    keep = str(keep_suffix or "").strip()
    removed: list[str] = []
    search_dirs = [root]
    reports = root / "Reports"
    if include_reports_subdir and reports.is_dir():
        search_dirs.append(reports)
    for directory in search_dirs:
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            if not is_generated_report_artifact(path.name):
                continue
            suffix = _ai_report_suffix_from_name(path.name)
            if suffix is None or suffix == keep:
                continue
            path.unlink(missing_ok=True)
            removed.append(str(path.relative_to(root)))
    return removed


def image_report_section(filename: str) -> str:
    """Ordnet PNG-Dateien einem TSA-Berichtskapitel zu."""
    n = filename.lower()
    if any(
        x in n
        for x in (
            "residual",
            "_acf",
            "acf_",
            "pacf",
            "_qq",
            "histogram",
            "std_residual",
            "sq_acf",
        )
    ):
        return "5. Residuals"
    if any(x in n for x in ("series_train", "train", "decomposition")):
        return "2. Introduction of the TSA"
    if any(
        x in n
        for x in ("forecast", "conditional_vol", "levels", "forward", "vol")
    ):
        return "4. Main outcome and components of this TSA"
    return "4. Main outcome and components of this TSA"
