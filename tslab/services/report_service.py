"""KI-Berichte fuer Output-Laeufe (PNG, TXT, Excel) als Word- und PDF-Dokument."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from tslab.config_loader import load_defaults
from tslab.services.ai_providers import (
    ModelSpec,
    LLMUsage,
    flush_langfuse,
    gemini_sdk_available,
    get_provider,
    init_langfuse,
    langfuse_configured,
    parse_model_id,
)
from tslab.services.report_docx import build_run_report_docx
from tslab.services.report_ai_pdf import build_run_report_pdf
from tslab.services.output_paths import relative_output_path, resolve_output_dir_arg

_SYSTEM_DE = (
    "Du bist Analyst fuer Zeitreihen und oekonometrische Auswertungen (Diplomarbeit-Stil). "
    "Antworte auf Deutsch, sachlich und fuer Fachleser verstaendlich. "
    "Keine erfundenen Zahlen — nur was in den Daten/Grafiken sichtbar ist."
)

_TEXT_PROMPT = (
    "Analysiere die folgenden Dateiinhalte aus einem Analyse-Lauf. "
    "Nenne Kernergebnisse, Auffaelligkeiten und Einordnung (Korrelation/TSA)."
)

_IMAGE_PROMPT = (
    "Beschreibe diese Grafik aus einem Zeitreihen-Analyse-Lauf: Achsen, Verlauf, "
    "besondere Muster, Einordnung fuer Korrelation oder TSA. Kurz und praezise."
)

_SUMMARY_PROMPT = (
    "Fasse den gesamten Analyse-Lauf in 2–4 Absaetzen zusammen "
    "(Zweck, wichtigste Befunde aus Text/Tabellen und Grafiken)."
)


@dataclass(frozen=True)
class ReportConfig:
    enabled: bool
    max_tokens: int
    default_model: str
    output_basename: str
    openai_api_key: str | None
    gemini_api_key: str | None
    langfuse_public_key: str | None
    langfuse_secret_key: str | None
    langfuse_host: str | None
    models: tuple[ModelSpec, ...]


def _env_bool(key: str) -> bool | None:
    raw = os.environ.get(key, "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return None


def _env(key: str) -> str | None:
    val = os.environ.get(key, "").strip()
    return val or None


def load_report_config() -> ReportConfig:
    cfg = load_defaults().get("ai_reports", {})
    env_enabled = _env_bool("TSLAB_AI_REPORTS_ENABLED")
    has_openai = bool(_env("OPENAI_API_KEY") or cfg.get("openai_api_key"))
    has_gemini = bool(_env("GEMINI_API_KEY") or cfg.get("gemini_api_key")) and gemini_sdk_available()
    if env_enabled is not None:
        enabled = env_enabled
    elif bool(cfg.get("enabled")):
        enabled = True
    else:
        # Auto-aktivieren wenn mindestens ein Provider-Key gesetzt ist
        enabled = has_openai or has_gemini
    models_raw = cfg.get("models") or [
        {
            "id": "openai:gpt-4o-mini",
            "provider": "openai",
            "label": "GPT-4o mini",
            "model": "gpt-4o-mini",
            "vision": True,
            "enabled": True,
        },
        {
            "id": "openai:gpt-5-mini",
            "provider": "openai",
            "label": "GPT-5 mini",
            "model": "gpt-5-mini",
            "vision": True,
            "enabled": True,
        },
        {
            "id": "openai:gpt-5-nano",
            "provider": "openai",
            "label": "GPT-5 nano",
            "model": "gpt-5-nano",
            "vision": True,
            "enabled": True,
        },
        {
            "id": "gemini:gemini-3.1-flash-lite",
            "provider": "gemini",
            "label": "Gemini 3.1 Flash Lite",
            "model": "gemini-3.1-flash-lite",
            "vision": True,
            "enabled": True,
        },
        {
            "id": "gemini:gemini-2.5-flash-lite",
            "provider": "gemini",
            "label": "Gemini 2.5 Flash Lite",
            "model": "gemini-2.5-flash-lite",
            "vision": True,
            "enabled": True,
        },
        {
            "id": "gemini:gemini-2.5-flash",
            "provider": "gemini",
            "label": "Gemini 2.5 Flash",
            "model": "gemini-2.5-flash",
            "vision": True,
            "enabled": True,
        },
    ]
    models: list[ModelSpec] = []
    for m in models_raw:
        mid = str(m.get("id", ""))
        provider = str(m.get("provider", parse_model_id(mid)[0]))
        model_name = str(m.get("model") or parse_model_id(mid)[1])
        models.append(
            ModelSpec(
                id=mid,
                provider=provider,
                label=str(m.get("label", mid)),
                model_name=model_name,
                vision=bool(m.get("vision", True)),
                enabled=bool(m.get("enabled", True)),
            )
        )
    return ReportConfig(
        enabled=enabled,
        max_tokens=int(cfg.get("max_tokens", 1000)),
        default_model=str(cfg.get("default_model", "openai:gpt-4o-mini")),
        output_basename=str(cfg.get("output_basename", "ai_bericht.docx")),
        openai_api_key=_env("OPENAI_API_KEY") or cfg.get("openai_api_key"),
        gemini_api_key=_env("GEMINI_API_KEY") or cfg.get("gemini_api_key"),
        langfuse_public_key=_env("LANGFUSE_PUBLIC_KEY") or cfg.get("langfuse_public_key"),
        langfuse_secret_key=_env("LANGFUSE_SECRET_KEY") or cfg.get("langfuse_secret_key"),
        langfuse_host=_env("LANGFUSE_HOST") or cfg.get("langfuse_host"),
        models=tuple(models),
    )


def _model_unavailable_hint(*, provider: str, cfg: ReportConfig) -> str:
    if provider == "openai":
        return "API-Key fehlt"
    if provider == "gemini":
        if not (_env("GEMINI_API_KEY") or cfg.gemini_api_key):
            return "API-Key fehlt"
        if not gemini_sdk_available():
            return "Paket google-genai fehlt (pip install)"
    return "nicht verfügbar"


def list_report_models(*, include_disabled: bool = False) -> list[dict[str, Any]]:
    cfg = load_report_config()
    has_openai = bool(_env("OPENAI_API_KEY") or cfg.openai_api_key)
    has_gemini = bool(_env("GEMINI_API_KEY") or cfg.gemini_api_key) and gemini_sdk_available()
    out: list[dict[str, Any]] = []
    for m in cfg.models:
        if not m.enabled and not include_disabled:
            continue
        available = (m.provider == "openai" and has_openai) or (
            m.provider == "gemini" and has_gemini
        )
        if not available and not include_disabled:
            out.append(
                {
                    "id": m.id,
                    "label": m.label,
                    "provider": m.provider,
                    "vision": m.vision,
                    "available": False,
                    "unavailable_hint": _model_unavailable_hint(
                        provider=m.provider, cfg=cfg
                    ),
                }
            )
            continue
        out.append(
            {
                "id": m.id,
                "label": m.label,
                "provider": m.provider,
                "vision": m.vision,
                "available": available,
            }
        )
    return out


def ai_reports_available() -> bool:
    cfg = load_report_config()
    if not cfg.enabled:
        return False
    has_openai = bool(_env("OPENAI_API_KEY") or cfg.openai_api_key)
    has_gemini = bool(_env("GEMINI_API_KEY") or cfg.gemini_api_key) and gemini_sdk_available()
    return has_openai or has_gemini


def _resolve_output_dir(output_dir: str | Path) -> Path:
    try:
        return resolve_output_dir_arg(output_dir)
    except (ValueError, OSError) as exc:
        raise ValueError(str(exc)) from exc


def _read_text_file(path: Path, *, max_chars: int = 12000) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[… gekürzt …]"
    return text


def _read_csv_preview(path: Path, *, max_rows: int = 25) -> str:
    df = pd.read_csv(path)
    return _dataframe_preview(df, max_rows=max_rows)


def _read_xlsx_preview(path: Path, *, max_rows: int = 25) -> str:
    df = pd.read_excel(path, engine="openpyxl")
    return _dataframe_preview(df, max_rows=max_rows)


def _dataframe_preview(df: pd.DataFrame, *, max_rows: int = 25) -> str:
    head = df.head(max_rows).to_string(index=False)
    stats = df.describe(include="all").transpose().head(12).to_string()
    return f"Spalten: {list(df.columns)}\nZeilen: {len(df)}\n\nKopf:\n{head}\n\nStatistik (Auszug):\n{stats}"


def _read_table_preview(path: Path, *, max_rows: int = 25) -> str:
    if path.suffix.lower() == ".xlsx":
        return _read_xlsx_preview(path, max_rows=max_rows)
    return _read_csv_preview(path, max_rows=max_rows)


def _scan_run_dir(run_dir: Path) -> tuple[list[Path], list[Path], list[Path]]:
    """PNG/TXT/Tabellen (Excel, legacy CSV) im Lauf-Ordner."""
    pngs = sorted(run_dir.glob("*.png"))
    txts = sorted(run_dir.glob("*.txt"))
    tables = sorted(run_dir.glob("*.xlsx")) + sorted(run_dir.glob("*.csv"))
    if pngs or txts or tables:
        return pngs, txts, tables
    pngs = sorted(run_dir.rglob("*.png"))[:24]
    txts = sorted(run_dir.rglob("*.txt"))[:12]
    tables = sorted(run_dir.rglob("*.xlsx"))[:12] + sorted(run_dir.rglob("*.csv"))[:12]
    return pngs, txts, tables


def _accumulate_usage(total: LLMUsage, part: LLMUsage) -> None:
    total.prompt_tokens += part.prompt_tokens
    total.completion_tokens += part.completion_tokens
    total.total_tokens += part.total_tokens


def resolve_run_report_model_id(
    output_dir: str | Path | None,
    model_id: str | None,
    *,
    config: ReportConfig | None = None,
) -> str | None:
    """Modell fuer einen Lauf: explizite UI-Wahl oder in .pending_run.json gespeichertes Modell."""
    mid = str(model_id or "").strip()
    if mid and mid not in ("none", "off", "0"):
        return mid
    if not output_dir:
        return None
    try:
        from tslab.services.run_telemetry import load_pending_collector

        collector = load_pending_collector(output_dir)
        if collector is not None:
            stored = str(collector.data.extra.get("report_model_id") or "").strip()
            if stored:
                return stored
    except Exception:
        pass
    return None


def _model_spec_for_id(
    config: ReportConfig,
    model_id: str | None,
    *,
    output_dir: str | Path | None = None,
) -> ModelSpec:
    if output_dir is not None:
        mid = resolve_run_report_model_id(output_dir, model_id, config=config) or ""
    else:
        mid = (model_id or config.default_model).strip()
    if not mid:
        if output_dir is not None:
            raise ValueError("Kein KI-Modell fuer diesen Lauf angegeben.")
        mid = config.default_model
    for m in config.models:
        if m.id == mid:
            return m
    provider, name = parse_model_id(mid)
    return ModelSpec(
        id=mid,
        provider=provider,
        label=mid,
        model_name=name,
        vision=True,
        enabled=True,
    )


def generate_run_report(
    output_dir: str | Path,
    *,
    model_id: str | None = None,
    run_type: str = "Analyse",
    title: str | None = None,
    analysis_mode: str = "extended",
    interactive: bool = False,
) -> dict[str, Any]:
    """Erstellt Word-Bericht(e) fuer einen Output-Ordner (ggf. je TSA-Modell)."""
    from tslab.services.report_session import run_report_session_to_completion

    _ = title  # Titel je Zielordner in report_session
    return run_report_session_to_completion(
        output_dir,
        model_id=model_id,
        run_type=run_type,
        analysis_mode=analysis_mode,
        interactive=interactive,
    )


def generate_object_report(
    entity_type: str,
    entity_id: str | int,
    *,
    context: dict[str, Any] | None = None,
    model_id: str | None = None,
) -> dict[str, Any]:
    """Bericht fuer Historie-Eintrag wenn output_dir im Kontext."""
    ctx = context or {}
    output_dir = ctx.get("output_dir")
    if not output_dir:
        return {
            "ok": False,
            "status": "error",
            "message": "Kein output_dir im Kontext.",
        }
    run_type = "Korrelation" if entity_type == "correlation" else "TSA"
    return generate_run_report(
        output_dir,
        model_id=model_id,
        run_type=run_type,
        title=f"TSLab {run_type}-Bericht ({entity_type} {entity_id})",
    )
