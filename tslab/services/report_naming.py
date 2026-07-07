"""Dateinamen fuer KI-Berichte (TSA, CORR, Modellvergleich)."""

from __future__ import annotations

import re


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
    return (
        lower.startswith("tsa_modell_bericht_")
        or lower.startswith("tsa_bericht_")
        or lower.startswith("corr_ai_bericht_")
        or lower.startswith("corr_bericht_")
        or lower.startswith("modellvergleich_")
    )


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
