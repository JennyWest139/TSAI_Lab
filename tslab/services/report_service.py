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
    get_provider,
    init_langfuse,
    langfuse_configured,
    parse_model_id,
)
from tslab.services.report_docx import build_run_report_docx
from tslab.services.report_ai_pdf import build_run_report_pdf
from tslab.web.output_browser import relative_output_path, resolve_output_path

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
    enabled = env_enabled if env_enabled is not None else bool(cfg.get("enabled"))
    models_raw = cfg.get("models") or [
        {
            "id": "openai:gpt-4o-mini",
            "provider": "openai",
            "label": "OpenAI GPT-4o mini",
            "model": "gpt-4o-mini",
            "vision": True,
            "enabled": True,
        },
        {
            "id": "openai:gpt-4o",
            "provider": "openai",
            "label": "OpenAI GPT-4o",
            "model": "gpt-4o",
            "vision": True,
            "enabled": True,
        },
        {
            "id": "gemini:gemini-2.0-flash",
            "provider": "gemini",
            "label": "Google Gemini 2.0 Flash",
            "model": "gemini-2.0-flash",
            "vision": True,
            "enabled": False,
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


def list_report_models(*, include_disabled: bool = False) -> list[dict[str, Any]]:
    cfg = load_report_config()
    has_openai = bool(_env("OPENAI_API_KEY") or cfg.openai_api_key)
    has_gemini = bool(_env("GEMINI_API_KEY") or cfg.gemini_api_key)
    out: list[dict[str, Any]] = []
    for m in cfg.models:
        if not m.enabled and not include_disabled:
            continue
        available = (m.provider == "openai" and has_openai) or (
            m.provider == "gemini" and has_gemini
        )
        if not available and not include_disabled:
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
    return bool(_env("OPENAI_API_KEY") or cfg.openai_api_key)


def _resolve_output_dir(output_dir: str | Path) -> Path:
    path = Path(output_dir)
    if path.is_dir():
        return path.resolve()
    rel = str(output_dir).replace("\\", "/").strip("/")
    return resolve_output_path(rel)


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


def _model_spec_for_id(config: ReportConfig, model_id: str | None) -> ModelSpec:
    mid = (model_id or config.default_model).strip()
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
) -> dict[str, Any]:
    """Erstellt Word-Bericht fuer einen Output-Ordner."""
    config = load_report_config()
    if not config.enabled:
        return {
            "ok": False,
            "status": "disabled",
            "message": "AI-Berichte sind deaktiviert (ai_reports.enabled oder TSLAB_AI_REPORTS_ENABLED).",
        }

    init_langfuse(config)
    langfuse_active = langfuse_configured(config)
    spec = _model_spec_for_id(config, model_id)
    if not spec.enabled:
        return {"ok": False, "status": "error", "message": f"Modell {spec.id} ist deaktiviert."}

    try:
        run_path = _resolve_output_dir(output_dir)
    except Exception as exc:
        return {"ok": False, "status": "error", "message": str(exc)}

    if not run_path.is_dir():
        return {"ok": False, "status": "error", "message": f"Ordner nicht gefunden: {output_dir}"}

    pngs, txts, tables = _scan_run_dir(run_path)
    if not pngs and not txts and not tables:
        return {
            "ok": False,
            "status": "error",
            "message": "Keine PNG-, TXT- oder Tabellendateien im Lauf-Ordner.",
        }

    provider = get_provider(spec.provider, config)
    max_tok = config.max_tokens
    image_tok = min(600, max_tok)

    text_sections: list[tuple[str, str]] = []
    text_bundle_parts: list[str] = []

    for tf in txts:
        if tf.name in (config.output_basename, "ai_bericht.pdf"):
            continue
        content = _read_text_file(tf)
        text_bundle_parts.append(f"### {tf.name}\n{content}")
        text_sections.append((tf.name, content))

    for table_path in tables:
        preview = _read_table_preview(table_path)
        text_bundle_parts.append(f"### {table_path.name}\n{preview}")
        text_sections.append((table_path.name, preview))

    ai_text_notes: list[tuple[str, str]] = []
    ai_errors: list[str] = []
    ai_warnings: list[str] = []
    token_usage = LLMUsage()
    llm_calls = 0

    if text_bundle_parts:
        try:
            resp = provider.complete_text(
                system=_SYSTEM_DE,
                user=_TEXT_PROMPT + "\n\n" + "\n\n".join(text_bundle_parts),
                model=spec.model_name,
                max_tokens=max_tok,
                trace_name="tslab-report-text",
            )
            ai_text_notes.append(("KI-Auswertung Text/Tabellen", resp.text))
            _accumulate_usage(token_usage, resp.usage)
            llm_calls += 1
        except Exception as exc:
            msg = f"KI-Auswertung Text/Tabellen: {exc}"
            ai_errors.append(msg)
            ai_text_notes.append(("KI-Auswertung Text/Tabellen", f"(Fehler: {exc})"))

    image_sections: list[tuple[str, str, Path]] = []
    image_notes_for_summary: list[str] = []
    for img in pngs:
        try:
            if spec.vision:
                resp = provider.describe_image(
                    image_path=img,
                    prompt=_IMAGE_PROMPT,
                    model=spec.model_name,
                    max_tokens=image_tok,
                    trace_name=f"tslab-report-image-{img.stem}",
                )
                expl = resp.text
                _accumulate_usage(token_usage, resp.usage)
                llm_calls += 1
            else:
                expl = "(Vision fuer dieses Modell nicht verfuegbar.)"
                ai_warnings.append(f"Vision nicht verfuegbar fuer {spec.label}.")
            image_sections.append((img.name, expl, img))
            image_notes_for_summary.append(f"{img.name}: {expl}")
        except Exception as exc:
            msg = f"Bildanalyse {img.name}: {exc}"
            ai_errors.append(msg)
            image_sections.append((img.name, f"(Fehler bei Bildanalyse: {exc})", img))

    summary_input = "\n\n".join(
        [t for _, t in ai_text_notes] + image_notes_for_summary
    ) or "Keine automatische Voranalyse."
    try:
        resp = provider.complete_text(
            system=_SYSTEM_DE,
            user=_SUMMARY_PROMPT + "\n\n" + summary_input,
            model=spec.model_name,
            max_tokens=max_tok,
            trace_name="tslab-report-summary",
        )
        summary = resp.text
        _accumulate_usage(token_usage, resp.usage)
        llm_calls += 1
    except Exception as exc:
        ai_errors.append(f"Zusammenfassung: {exc}")
        summary = f"Zusammenfassung konnte nicht erzeugt werden: {exc}"

    if langfuse_active:
        flush_langfuse()
    elif llm_calls:
        ai_warnings.append("Langfuse nicht konfiguriert — Traces werden nicht extern protokolliert.")

    doc_text_sections = list(text_sections)
    for heading, body in ai_text_notes:
        doc_text_sections.append((heading, body))

    report_name = config.output_basename
    out_path = run_path / report_name
    doc_title = title or f"TSLab {run_type}-Bericht"
    subtitle = f"Ordner: {run_path.name}"

    build_run_report_docx(
        out_path,
        title=doc_title,
        subtitle=subtitle,
        summary=summary,
        text_sections=doc_text_sections,
        image_sections=image_sections,
        model_label=spec.label,
    )

    pdf_name = Path(config.output_basename).with_suffix(".pdf").name
    pdf_path = run_path / pdf_name
    build_run_report_pdf(
        pdf_path,
        title=doc_title,
        subtitle=subtitle,
        summary=summary,
        text_sections=doc_text_sections,
        image_sections=image_sections,
        model_label=spec.label,
    )

    rel = relative_output_path(out_path)
    file_url = f"/output/file/{rel}" if rel else None
    pdf_rel = relative_output_path(pdf_path)
    pdf_url = f"/output/file/{pdf_rel}" if pdf_rel else None

    ai_ok = llm_calls > 0 and not ai_errors
    status_msg = f"KI-Bericht erstellt: {report_name}"
    if ai_errors:
        status_msg += f" ({len(ai_errors)} KI-Fehler — siehe Word-Bericht)"
    elif llm_calls == 0:
        status_msg += " (ohne KI-Auswertung)"

    return {
        "ok": True,
        "ai_ok": ai_ok,
        "status": "done",
        "message": status_msg,
        "report_path": str(out_path),
        "report_rel": rel,
        "report_url": file_url,
        "report_pdf_path": str(pdf_path),
        "report_pdf_rel": pdf_rel,
        "report_pdf_url": pdf_url,
        "model": spec.id,
        "png_count": len(pngs),
        "text_count": len(txts) + len(tables),
        "llm_calls": llm_calls,
        "ai_errors": ai_errors,
        "ai_warnings": ai_warnings,
        "token_usage": {
            "prompt_tokens": token_usage.prompt_tokens,
            "completion_tokens": token_usage.completion_tokens,
            "total_tokens": token_usage.total_tokens,
            "model": spec.model_name,
            "calls": llm_calls,
        },
        "langfuse_active": langfuse_active,
    }


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
