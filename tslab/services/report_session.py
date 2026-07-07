"""Schrittweise KI-Berichtserstellung mit Rate-Limit-Checkpoints."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from tslab.services.ai_providers import (
    LLMUsage,
    flush_langfuse,
    format_llm_error,
    get_provider,
    init_langfuse,
    is_rate_limit_error,
    langfuse_configured,
)
from tslab.services.output_paths import relative_output_path, resolve_output_dir_arg
from tslab.services.report_docx import build_run_report_docx
from tslab.services.report_ai_pdf import build_run_report_pdf
from tslab.services.report_naming import (
    ai_model_filename_suffix,
    corr_report_basename,
    image_report_section,
    is_generated_report_artifact,
    modellvergleich_basename,
    purge_ai_reports_for_other_models,
    tsa_model_report_basename,
)

CHECKPOINT_CALLS = 5
PAUSE_SECONDS = 60
SESSION_BASENAME = ".report_session.json"

_TSA_MODEL_SECTIONS: list[tuple[str, str]] = [
    (
        "1. Management Summary",
        "Schreibe das Management Summary fuer Entscheider (max. eine Seite, deutsch). "
        "Kern-KPIs, Eignung fuer Prognose (**Ja** / **Nein** / **Beschraenkt**), "
        "Qualitaetsskala 1–5, Konfidenz, Empfehlung. Nur belegte Fakten.",
    ),
    (
        "2. Introduction of the TSA",
        "Beschreibe Einleitung und Kontext dieser Zeitreihenanalyse (deutsch): "
        "Ziel, Zeitreihe, Trainingsfenster, Prognosehorizont, Modelltyp, Datenbasis.",
    ),
    (
        "3. Analysis and setting parameters for the TSA",
        "Erlaeutere Modellwahl, Parameterschaetzung und Diagnostik vor Residuenpruefung "
        "(deutsch): Ordung ARMA/GARCH, Koeffizienten, AIC/BIC, Signifikanz — nur aus den Dateien.",
    ),
    (
        "4. Main outcome and components of this TSA",
        "Darstellung der Haetergebnisse (deutsch): Prognose, Quantile, Volatilitaet, "
        "Zerlegung, zentrale Grafiken — mit Bezug auf die gelieferten Kennzahlen.",
    ),
    (
        "5. Residuals",
        "Residuenanalyse (deutsch): Ljung-Box, Jarque-Bera, ARCH-LM, ACF/PACF der Residuen, "
        "Auffaelligkeiten und Modelladequatheit.",
    ),
    (
        "6. Conclusion",
        "Schlussfolgerung (deutsch): Gesamturteil, groesste Risiken, Empfehlung fuer "
        "weiteres Vorgehen, offene Punkte.",
    ),
]

_SYSTEM_DE = (
    "Du bist Aktuar und Senior Analyst fuer Zeitreihen- und Risikoberichterstattung "
    "(Diplomarbeit-Stil, deutsch). Antworte sachlich, strukturiert und nur mit "
    "belegten Kennzahlen aus den gelieferten Dateien und Grafiken — keine erfundenen Werte."
)


def _tsa_report_prompts(run_type: str, analysis_mode: str) -> dict[str, str]:
    is_tsa = run_type.upper() == "TSA"
    exec_summary = (
        "Erstelle eine Executive Summary fuer Entscheider (max. eine Seite Text). "
        "Nutze ausschliesslich die vorliegenden Analysen zu Text/Tabellen und Grafiken.\n\n"
        "Pflichtstruktur:\n"
        "1) Modell und Analysezweck (1–2 Saetze)\n"
        "2) Wichtigste Kennzahlen (Bulletpoints: Schaetzer, AIC/BIC, Diagnostik p-Werte, "
        "Prognosehorizont, Quantile — nur wenn in den Daten)\n"
        "3) Eignung fuer Zeitreihenanalyse/Prognose: genau eine Bewertung "
        "**Ja**, **Nein** oder **Beschraenkt** (fett markieren)\n"
        "4) Qualitaetsskala 1–5 (1=unbrauchbar, 5=hervorragend) mit Konfidenz "
        "(niedrig/mittel/hoch) und kurzer fachlicher Begruendung\n"
        "5) Groesste Risiken/Auffaelligkeiten und Empfehlung fuer weiteres Vorgehen\n\n"
        "Wenn Informationen fehlen, das explizit benennen."
    )
    base_text = (
        "Du erstellst die fachliche Auswertung fuer einen Aktuarsbericht. "
        "Analysiere summary.txt, diagnostics.txt und Tabellen vollstaendig: "
        "Modellordnung, Koeffizienten, Signifikanz, Residuen-Diagnostik (Ljung-Box, "
        "Jarque-Bera, ARCH-LM), Prognose und Quantile. "
        "Nenne nur belegte Zahlen."
    )
    base_image = (
        "Beschreibe diese Grafik fuer einen Aktuarsbericht: Achsen, Einheiten, "
        "Zeitraum, Trainings- vs. Prognosebereich, Auffaelligkeiten, Quantile/KBaender. "
        "Ordne oekonomisch ein (Trend, Volatilitaet, Ereignisse wie Crash 1987, "
        "Finanzkrise 2008, COVID-2020 soweit sichtbar)."
    )
    if not is_tsa:
        corr_text = (
            "Du erstellst die fachliche Auswertung fuer eine Korrelationsanalyse. "
            "Nutze nur korrelationsrelevante Inhalte aus summary/diagnostics/tabellen: "
            "Korrelationsstaerke und Vorzeichen, bestes Lag/Fuehrung, Stabilitaet ueber das Fenster, "
            "Auffaelligkeiten in den Reihen (z.B. Regimewechsel). "
            "Nenne keine TSA-/Modellfit-Themen (ARMA/GARCH-Parameter, Residuen-Tests), "
            "wenn diese nicht explizit in den CORR-Dateien enthalten sind."
        )
        corr_image = (
            "Beschreibe diese Grafik fuer einen Korrelationsbericht: Achsen, Zeitraum, "
            "Lead/Lag-Muster, Veraenderungen der Kopplung, Ausreisser und sichtbare Ereigniseinfluesse "
            "(z.B. COVID oder Volatilitaetsphasen), nur wenn im Plot erkennbar."
        )
        corr_summary = (
            "Erstelle eine Executive Summary fuer die Korrelation (max. eine Seite): "
            "Kernaussage zur Beziehung der Reihen, beste Lag-Interpretation, Stabilitaet/Unsicherheit, "
            "relevante Ereigniseinfluesse (z.B. COVID/Volatilitaet) nur bei belegbarer Evidenz. "
            "Fuehre keine nicht-relevanten Pruefungen auf."
        )
        return {
            "text": corr_text,
            "image": corr_image,
            "summary": corr_summary,
            "thesis_abgleich": "",
        }

    text = (
        base_text
        + " Kontext: TSA-Modell. Gehe auf Parameterschaetzung, Restunsicherheit, "
        "Prognoseguete und Zeitreihenverlauf inkl. bekannter Marktereignisse ein."
    )
    image = base_image + " Kontext: TSA-Modellausgabe."
    thesis_abgleich = (
        "Vergleiche coefficient_abgleich.txt (Diplomarbeit R vs. dieser Lauf). "
        "Tabellarische Gedankenfuehrung: uebereinstimmende vs. abweichende Parameter, "
        "moegliche Ursachen (Stichprobe, Software, Optimierung), Relevanz fuer die Modellguete."
    )
    if analysis_mode.lower() != "thesis":
        thesis_abgleich = ""
    return {"text": text, "image": image, "summary": exec_summary, "thesis_abgleich": thesis_abgleich}


def _resolve_output_dir(output_dir: str | Path) -> Path:
    try:
        return resolve_output_dir_arg(output_dir)
    except (ValueError, OSError) as exc:
        raise ValueError(str(exc)) from exc


@dataclass
class RateLimitEvent:
    at_call: int
    user_choice: str
    paused_seconds: int = 0
    reason: str = "checkpoint"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RateLimitEvent:
        return cls(
            at_call=int(data.get("at_call") or 0),
            user_choice=str(data.get("user_choice") or ""),
            paused_seconds=int(data.get("paused_seconds") or 0),
            reason=str(data.get("reason") or "checkpoint"),
        )


@dataclass
class ReportTask:
    kind: Literal["text_bundle", "image", "summary", "thesis_abgleich", "section"]
    label: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "label": self.label, "payload": self.payload}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReportTask:
        return cls(
            kind=data["kind"],  # type: ignore[arg-type]
            label=str(data.get("label") or ""),
            payload=dict(data.get("payload") or {}),
        )


@dataclass
class ReportTargetState:
    rel_path: str
    title: str
    tasks: list[ReportTask]
    task_index: int = 0
    done: bool = False
    text_sections: list[list[str]] = field(default_factory=list)
    ai_text_notes: list[list[str]] = field(default_factory=list)
    image_sections: list[list[str]] = field(default_factory=list)
    ai_errors: list[str] = field(default_factory=list)
    ai_warnings: list[str] = field(default_factory=list)
    summary: str = ""
    png_count: int = 0
    text_count: int = 0
    output_basename: str = ""
    report_layout: str = "standard"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rel_path": self.rel_path,
            "title": self.title,
            "tasks": [t.to_dict() for t in self.tasks],
            "task_index": self.task_index,
            "done": self.done,
            "text_sections": self.text_sections,
            "ai_text_notes": self.ai_text_notes,
            "image_sections": self.image_sections,
            "ai_errors": self.ai_errors,
            "ai_warnings": self.ai_warnings,
            "summary": self.summary,
            "png_count": self.png_count,
            "text_count": self.text_count,
            "output_basename": self.output_basename,
            "report_layout": self.report_layout,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReportTargetState:
        return cls(
            rel_path=str(data.get("rel_path") or ""),
            title=str(data.get("title") or ""),
            tasks=[ReportTask.from_dict(t) for t in data.get("tasks") or []],
            task_index=int(data.get("task_index") or 0),
            done=bool(data.get("done")),
            text_sections=[list(x) for x in data.get("text_sections") or []],
            ai_text_notes=[list(x) for x in data.get("ai_text_notes") or []],
            image_sections=[list(x) for x in data.get("image_sections") or []],
            ai_errors=[str(x) for x in data.get("ai_errors") or []],
            ai_warnings=[str(x) for x in data.get("ai_warnings") or []],
            summary=str(data.get("summary") or ""),
            png_count=int(data.get("png_count") or 0),
            text_count=int(data.get("text_count") or 0),
            output_basename=str(data.get("output_basename") or ""),
            report_layout=str(data.get("report_layout") or "standard"),
        )


@dataclass
class ReportSessionState:
    version: int = 1
    output_root: str = ""
    run_type: str = "Analyse"
    analysis_mode: str = "extended"
    model_id: str = ""
    model_label: str = ""
    targets: list[ReportTargetState] = field(default_factory=list)
    current_target: int = 0
    llm_calls_total: int = 0
    calls_since_checkpoint: int = 0
    rate_limit_events: list[RateLimitEvent] = field(default_factory=list)
    finish_early: bool = False
    token_usage: dict[str, int] = field(default_factory=dict)
    langfuse_active: bool = False
    completed_reports: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "output_root": self.output_root,
            "run_type": self.run_type,
            "analysis_mode": self.analysis_mode,
            "model_id": self.model_id,
            "model_label": self.model_label,
            "targets": [t.to_dict() for t in self.targets],
            "current_target": self.current_target,
            "llm_calls_total": self.llm_calls_total,
            "calls_since_checkpoint": self.calls_since_checkpoint,
            "rate_limit_events": [e.to_dict() for e in self.rate_limit_events],
            "finish_early": self.finish_early,
            "token_usage": self.token_usage,
            "langfuse_active": self.langfuse_active,
            "completed_reports": self.completed_reports,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReportSessionState:
        return cls(
            version=int(data.get("version") or 1),
            output_root=str(data.get("output_root") or ""),
            run_type=str(data.get("run_type") or "Analyse"),
            analysis_mode=str(data.get("analysis_mode") or "extended"),
            model_id=str(data.get("model_id") or ""),
            model_label=str(data.get("model_label") or ""),
            targets=[ReportTargetState.from_dict(t) for t in data.get("targets") or []],
            current_target=int(data.get("current_target") or 0),
            llm_calls_total=int(data.get("llm_calls_total") or 0),
            calls_since_checkpoint=int(data.get("calls_since_checkpoint") or 0),
            rate_limit_events=[
                RateLimitEvent.from_dict(e) for e in data.get("rate_limit_events") or []
            ],
            finish_early=bool(data.get("finish_early")),
            token_usage=dict(data.get("token_usage") or {}),
            langfuse_active=bool(data.get("langfuse_active")),
            completed_reports=list(data.get("completed_reports") or []),
        )


def session_path_for(output_root: str | Path) -> Path:
    root = output_root if isinstance(output_root, Path) else Path(output_root)
    reports = root / "Reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports / SESSION_BASENAME


def session_has_pending_work(state: ReportSessionState | None) -> bool:
    if state is None or state.finish_early:
        return False
    return any(not target.done for target in state.targets)


def _effective_max_tokens(config: Any, spec: Any, *, base: int | None = None) -> int:
    max_tok = int(base if base is not None else config.max_tokens)
    if str(getattr(spec, "provider", "")).lower() == "gemini":
        from tslab.services.ai_providers import _gemini_output_token_budget

        return _gemini_output_token_budget(max_tok, model=str(spec.model_name))
    return max_tok


def load_session(output_root: str | Path) -> ReportSessionState | None:
    path = session_path_for(output_root)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ReportSessionState.from_dict(data)


def save_session(state: ReportSessionState, output_root: str | Path) -> Path:
    path = session_path_for(output_root)
    path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def delete_session(output_root: str | Path) -> None:
    path = session_path_for(output_root)
    if path.is_file():
        path.unlink()


def list_tsa_model_dirs(run_path: Path) -> list[Path]:
    dirs: list[Path] = []
    for child in sorted(run_path.iterdir()):
        if not child.is_dir() or child.name == "Reports":
            continue
        if (child / "summary.txt").is_file():
            dirs.append(child)
    return dirs


def _folder_to_run_model_key(folder_name: str) -> str:
    """Ordnername -> Schluessel wie in der UI-Modellauswahl (arma, garch, …)."""
    name = folder_name.lower()
    if name.startswith("decomp_additive"):
        return "decomp-additive"
    if name.startswith("decomp_multiplicative"):
        return "decomp-multiplicative"
    if "arma" in name and "garch" in name:
        return "arma-garch"
    if name.startswith("arma"):
        return "arma"
    if name.startswith("garch"):
        return "garch"
    return name.replace("_", "-")


def _selected_model_keys_from_run(run_path: Path) -> set[str] | None:
    from tslab.services.run_telemetry import load_pending_collector

    collector = load_pending_collector(run_path)
    if collector is None:
        return None
    for row in collector.data.extra.get("ui_settings") or []:
        if str(row.get("label") or "") != "Modelle":
            continue
        raw = str(row.get("value") or "").strip()
        if not raw or raw == "—":
            return None
        keys = {
            part.strip().lower().replace("_", "-")
            for part in raw.split(",")
            if part.strip()
        }
        return keys or None
    return None


def filter_model_dirs_for_comparison(
    run_path: Path, model_dirs: list[Path]
) -> list[Path]:
    """Nur im Lauf gewaehlte TSA-Modelle (falls in ui_settings erfasst)."""
    selected = _selected_model_keys_from_run(run_path)
    if not selected:
        return model_dirs
    filtered = [
        d for d in model_dirs if _folder_to_run_model_key(d.name) in selected
    ]
    return filtered or model_dirs


_FORECAST_LEVEL_MARKERS = (
    "Prognose PDAX-Niveau",
    "Prognose Niveau",
    "Datum          Mittelwert",
)


def summary_text_for_model_comparison(content: str) -> str:
    """Fit/Diagnostik fuer Modellvergleich — ohne Niveau-Prognosetabellen."""
    lines = content.splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if any(marker in line for marker in _FORECAST_LEVEL_MARKERS):
            break
        if stripped.startswith("Datum ") and "Mittelwert" in stripped:
            break
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out).strip()


def discover_report_targets(
    run_path: Path,
    *,
    run_type: str,
    analysis_mode: str,
) -> list[tuple[Path, str]]:
    """(Ordner, Titel) je Bericht."""
    if run_type.upper() == "TSA":
        model_dirs = list_tsa_model_dirs(run_path)
        if model_dirs:
            return [(d, f"TSA Modell {d.name}") for d in model_dirs]
    return [(run_path, f"TSLab {run_type}-Bericht")]


def _build_tsa_comparison_target(
    run_path: Path,
    model_dirs: list[Path],
    *,
    ai_suffix: str,
) -> ReportTargetState | None:
    """KI-Modellvergleich fuer Reports/ (nach allen Einzelmodell-Berichten)."""
    from tslab.services.report_service import _read_text_file

    model_dirs = filter_model_dirs_for_comparison(run_path, model_dirs)
    if len(model_dirs) < 2:
        return None

    model_labels = ", ".join(d.name for d in model_dirs)
    text_bundle_parts: list[str] = []
    for model_dir in model_dirs:
        summary_path = model_dir / "summary.txt"
        if not summary_path.is_file():
            continue
        content = summary_text_for_model_comparison(_read_text_file(summary_path))
        if not content:
            continue
        text_bundle_parts.append(f"### Modell {model_dir.name}\n{content}")

    if len(text_bundle_parts) < 2:
        return None

    compare_text = (
        "Du erstellst den fachlichen Modellvergleich fuer einen TSA-Lauf. "
        f"Verglichen werden ausschliesslich diese im Lauf gewaehlten Modelle: {model_labels}. "
        "Nutze Fit-Kennzahlen (AIC, BIC, Log-Likelihood), Koeffizienten und Residuen-Diagnostik "
        "(Ljung-Box, Jarque-Bera, ARCH-LM). "
        "KEINE Prognose-Mittelwerte, Quantil-Tabellen oder Niveau-Zeitreihen — "
        "diese gehoeren nur in die jeweiligen Modellordner. "
        "Erstelle eine Rangliste vom am besten geeigneten (1.) zum am wenigsten geeigneten Modell. "
        "Pro Modell: Rang, Eignung (Ja/Nein/Beschraenkt), Qualitaet 1–5, Guete/Konfidenz "
        "(niedrig/mittel/hoch), kurze fachliche Begruendung nur mit belegten Kennzahlen."
    )
    compare_summary = (
        "Executive Summary des Modellvergleichs (max. eine Seite). "
        "Pflicht: klare Rangfolge 1., 2., 3., … (bestes zuerst), "
        "Gesamtempfehlung fuer Prognose und Risiko, groesste Unsicherheiten. "
        "Keine Auflistung von Prognose-Mittelwerten."
    )

    tasks = [
        ReportTask(
            kind="text_bundle",
            label="Modellranking",
            payload={"parts": text_bundle_parts, "prompt": compare_text},
        ),
        ReportTask(
            kind="summary",
            label="Executive Summary Modellvergleich",
            payload={"prompt": compare_summary},
        ),
    ]

    return ReportTargetState(
        rel_path="Reports",
        title="TSA Modellvergleich",
        tasks=tasks,
        text_sections=[],
        text_count=len(text_bundle_parts),
        output_basename=modellvergleich_basename(ai_suffix),
        report_layout="tsa_comparison",
    )


def _collect_dir_sources(
    target_dir: Path,
) -> tuple[list[str], list[tuple[str, str]], list[Path], list[Path], list[Path]]:
    from tslab.services.report_service import _read_table_preview, _read_text_file, _scan_run_dir

    pngs, txts, tables = _scan_run_dir(target_dir)
    text_sections: list[tuple[str, str]] = []
    text_bundle_parts: list[str] = []

    for tf in txts:
        if is_generated_report_artifact(tf.name):
            continue
        content = _read_text_file(tf)
        text_bundle_parts.append(f"### {tf.name}\n{content}")
        text_sections.append((tf.name, content))

    for table_path in tables:
        preview = _read_table_preview(table_path)
        text_bundle_parts.append(f"### {table_path.name}\n{preview}")
        text_sections.append((table_path.name, preview))

    return text_bundle_parts, text_sections, pngs, txts, tables


def _build_tsa_model_tasks(
    target_dir: Path,
    *,
    analysis_mode: str,
    run_root: Path,
    text_bundle_parts: list[str],
    pngs: list[Path],
) -> list[ReportTask]:
    prompts = _tsa_report_prompts("TSA", analysis_mode)
    tasks: list[ReportTask] = []

    for img in pngs:
        tasks.append(
            ReportTask(
                kind="image",
                label=img.name,
                payload={"path": str(img), "prompt": prompts["image"]},
            )
        )

    for heading, section_prompt in _TSA_MODEL_SECTIONS:
        tasks.append(
            ReportTask(
                kind="section",
                label=heading,
                payload={"parts": list(text_bundle_parts), "prompt": section_prompt},
            )
        )

    if analysis_mode.lower() == "thesis" and prompts["thesis_abgleich"]:
        abgleich = run_root / "coefficient_abgleich.txt"
        if abgleich.is_file():
            tasks.append(
                ReportTask(
                    kind="thesis_abgleich",
                    label="Diplomarbeit Koeffizienten-Abgleich",
                    payload={
                        "path": str(abgleich),
                        "prompt": prompts["thesis_abgleich"],
                    },
                )
            )

    return tasks


def _build_tasks_for_dir(
    target_dir: Path,
    *,
    run_type: str,
    analysis_mode: str,
    run_root: Path,
    tsa_model: bool = False,
) -> tuple[list[ReportTask], list[tuple[str, str]], int, int]:
    text_bundle_parts, text_sections, pngs, txts, tables = _collect_dir_sources(target_dir)
    prompts = _tsa_report_prompts(run_type, analysis_mode)

    if tsa_model:
        tasks = _build_tsa_model_tasks(
            target_dir,
            analysis_mode=analysis_mode,
            run_root=run_root,
            text_bundle_parts=text_bundle_parts,
            pngs=pngs,
        )
        if not tasks:
            return [], text_sections, len(pngs), len(txts) + len(tables)
        return tasks, text_sections, len(pngs), len(txts) + len(tables)

    tasks: list[ReportTask] = []
    if text_bundle_parts:
        tasks.append(
            ReportTask(
                kind="text_bundle",
                label="Text/Tabellen",
                payload={"parts": text_bundle_parts, "prompt": prompts["text"]},
            )
        )
    for img in pngs:
        tasks.append(
            ReportTask(
                kind="image",
                label=img.name,
                payload={"path": str(img), "prompt": prompts["image"]},
            )
        )
    if not text_bundle_parts and not pngs:
        return [], text_sections, len(pngs), len(txts) + len(tables)

    tasks.append(
        ReportTask(
            kind="summary",
            label="Executive Summary",
            payload={"prompt": prompts["summary"]},
        )
    )

    if (
        run_type.upper() == "TSA"
        and analysis_mode.lower() == "thesis"
        and prompts["thesis_abgleich"]
    ):
        abgleich = run_root / "coefficient_abgleich.txt"
        if abgleich.is_file():
            tasks.append(
                ReportTask(
                    kind="thesis_abgleich",
                    label="Diplomarbeit Koeffizienten-Abgleich",
                    payload={
                        "path": str(abgleich),
                        "prompt": prompts["thesis_abgleich"],
                    },
                )
            )

    return tasks, text_sections, len(pngs), len(txts) + len(tables)


def prepare_report_session(
    output_dir: str | Path,
    *,
    model_id: str | None = None,
    run_type: str = "Analyse",
    analysis_mode: str = "extended",
) -> dict[str, Any]:
    from tslab.services.report_service import _model_spec_for_id, load_report_config, resolve_run_report_model_id

    config = load_report_config()
    if not config.enabled:
        return {
            "ok": False,
            "status": "disabled",
            "message": "AI-Berichte sind deaktiviert.",
        }

    from tslab.services.report_service import _resolve_output_dir

    run_path = _resolve_output_dir(output_dir)
    if not run_path.is_dir():
        return {"ok": False, "status": "error", "message": f"Ordner nicht gefunden: {output_dir}"}

    try:
        from tslab.services.report_runner import ai_report_in_progress, is_current_background_worker

        if ai_report_in_progress(run_path) and not is_current_background_worker(run_path):
            requested = str(model_id or "").strip() or (
                resolve_run_report_model_id(run_path, None, config=config) or ""
            )
            from tslab.services.report_runner import background_model_matches

            if background_model_matches(run_path, requested):
                return {
                    "ok": True,
                    "status": "in_progress",
                    "message": "KI-Berichte werden bereits erstellt.",
                    "output_dir": str(run_path),
                }
            active_session = load_session(run_path)
            active_model = active_session.model_id if active_session else (
                resolve_run_report_model_id(run_path, None, config=config) or ""
            )
            if requested and active_model and active_model != requested:
                return {
                    "ok": False,
                    "status": "busy",
                    "message": (
                        "KI-Berichte fuer ein anderes Modell laufen bereits. "
                        "Bitte warten oder den Lauf neu starten."
                    ),
                }
            return {
                "ok": True,
                "status": "in_progress",
                "message": "KI-Berichte werden bereits erstellt.",
                "output_dir": str(run_path),
            }
    except ImportError:
        pass

    init_langfuse(config)
    try:
        spec = _model_spec_for_id(config, model_id, output_dir=run_path)
    except ValueError as exc:
        return {"ok": False, "status": "error", "message": str(exc)}
    if not spec.enabled:
        return {"ok": False, "status": "error", "message": f"Modell {spec.id} ist deaktiviert."}

    from tslab.services.report_service import _env

    if spec.provider == "openai" and not (_env("OPENAI_API_KEY") or config.openai_api_key):
        return {"ok": False, "status": "error", "message": "OpenAI API-Key fehlt."}
    if spec.provider == "gemini" and not (_env("GEMINI_API_KEY") or config.gemini_api_key):
        return {"ok": False, "status": "error", "message": "Gemini API-Key fehlt."}

    existing = load_session(run_path)
    if (
        existing
        and existing.model_id == spec.id
        and existing.run_type == run_type
        and existing.analysis_mode == analysis_mode
        and session_has_pending_work(existing)
    ):
        total_tasks = sum(len(t.tasks) for t in existing.targets)
        done_targets = sum(1 for t in existing.targets if t.done)
        return {
            "ok": True,
            "status": "ready",
            "message": (
                f"Berichtssession wird fortgesetzt "
                f"({done_targets}/{len(existing.targets)} Ziele, {total_tasks} KI-Schritte)."
            ),
            "output_dir": str(run_path),
            "target_count": len(existing.targets),
            "total_tasks": total_tasks,
            "targets": [{"rel_path": t.rel_path, "title": t.title} for t in existing.targets],
            "checkpoint_calls": CHECKPOINT_CALLS,
            "resumed": True,
        }

    if existing and (
        existing.model_id != spec.id
        or existing.run_type != run_type
        or existing.analysis_mode != analysis_mode
    ):
        delete_session(run_path)

    ai_suffix = ai_model_filename_suffix(model_label=spec.label, model_id=spec.id)
    purge_ai_reports_for_other_models(run_path, keep_suffix=ai_suffix)
    is_tsa = run_type.upper() == "TSA"

    targets_data: list[ReportTargetState] = []
    model_dirs: list[Path] = []
    if is_tsa:
        model_dirs = list_tsa_model_dirs(run_path)

    for target_dir, title in discover_report_targets(
        run_path, run_type=run_type, analysis_mode=analysis_mode
    ):
        tasks, text_sections, png_n, txt_n = _build_tasks_for_dir(
            target_dir,
            run_type=run_type,
            analysis_mode=analysis_mode,
            run_root=run_path,
            tsa_model=is_tsa and target_dir.resolve() != run_path.resolve(),
        )
        if not tasks:
            continue
        rel = (
            "."
            if target_dir.resolve() == run_path.resolve()
            else target_dir.relative_to(run_path).as_posix()
        )
        output_basename = ""
        report_layout = "standard"
        if is_tsa and target_dir.resolve() != run_path.resolve():
            output_basename = tsa_model_report_basename(target_dir.name, ai_suffix)
            report_layout = "tsa_model"
        elif not is_tsa:
            output_basename = corr_report_basename(ai_suffix)
        targets_data.append(
            ReportTargetState(
                rel_path=rel,
                title=title,
                tasks=tasks,
                text_sections=[[h, b] for h, b in text_sections],
                png_count=png_n,
                text_count=txt_n,
                output_basename=output_basename,
                report_layout=report_layout,
            )
        )

    if model_dirs:
        comparison = _build_tsa_comparison_target(run_path, model_dirs, ai_suffix=ai_suffix)
        if comparison:
            targets_data.append(comparison)

    if not targets_data:
        return {
            "ok": False,
            "status": "error",
            "message": "Keine Berichtsziele (PNG/TXT) im Lauf-Ordner.",
        }

    state = ReportSessionState(
        output_root=str(run_path.resolve()),
        run_type=run_type,
        analysis_mode=analysis_mode,
        model_id=spec.id,
        model_label=spec.label,
        targets=targets_data,
        langfuse_active=langfuse_configured(config),
        token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    )
    save_session(state, run_path)

    total_tasks = sum(len(t.tasks) for t in targets_data)
    return {
        "ok": True,
        "status": "ready",
        "message": f"Berichtssession vorbereitet ({len(targets_data)} Ordner, {total_tasks} KI-Schritte).",
        "output_dir": str(run_path),
        "target_count": len(targets_data),
        "total_tasks": total_tasks,
        "targets": [{"rel_path": t.rel_path, "title": t.title} for t in targets_data],
        "checkpoint_calls": CHECKPOINT_CALLS,
    }


def _usage_dict_add(state: ReportSessionState, usage: LLMUsage) -> None:
    state.token_usage["prompt_tokens"] = int(state.token_usage.get("prompt_tokens", 0)) + usage.prompt_tokens
    state.token_usage["completion_tokens"] = int(
        state.token_usage.get("completion_tokens", 0)
    ) + usage.completion_tokens
    state.token_usage["total_tokens"] = int(state.token_usage.get("total_tokens", 0)) + usage.total_tokens


def _image_notes(target: ReportTargetState) -> list[str]:
    notes: list[str] = []
    for row in target.image_sections:
        if len(row) >= 2:
            notes.append(f"{row[0]}: {row[1]}")
    return notes


def _finalize_target_documents(
    state: ReportSessionState,
    target: ReportTargetState,
    *,
    config: Any,
    run_path: Path,
) -> dict[str, Any]:
    from collections import defaultdict

    target_dir = run_path if target.rel_path == "." else run_path / target.rel_path
    appendix_sections = [(h, b) for h, b in target.text_sections]

    image_sections: list[tuple[str, str, Path]] = []
    section_images: dict[str, list[tuple[str, str, Path]]] = defaultdict(list)
    for row in target.image_sections:
        if len(row) >= 3:
            item = (row[0], row[1], Path(row[2]))
            image_sections.append(item)
            if target.report_layout == "tsa_model":
                section_images[image_report_section(row[0])].append(item)

    numbered_sections: list[tuple[str, str]] = []
    analysis_sections: list[tuple[str, str]] = []
    summary = target.summary

    if target.report_layout == "tsa_model":
        section_order = [h for h, _ in _TSA_MODEL_SECTIONS]
        notes_by_heading = {h: b for h, b in target.ai_text_notes}
        for heading in section_order:
            body = notes_by_heading.get(heading, "")
            if not body and state.finish_early:
                body = "(Abschnitt wegen Rate-Limit / Abbruch nicht erzeugt.)"
            numbered_sections.append((heading, body))
        summary = notes_by_heading.get("1. Management Summary", summary or "")
        extra_notes = [
            (h, b)
            for h, b in target.ai_text_notes
            if h not in section_order
        ]
        if extra_notes:
            appendix_sections = extra_notes + appendix_sections
    elif target.report_layout == "tsa_comparison":
        analysis_sections = [(h, b) for h, b in target.ai_text_notes]
        appendix_sections = []
    else:
        analysis_sections = [(h, b) for h, b in target.ai_text_notes]
        if not summary:
            if state.finish_early:
                summary = (
                    "Bericht vorzeitig abgeschlossen (Rate-Limit / Nutzerwahl). "
                    "Einige KI-Abschnitte fehlen."
                )
            else:
                summary = "Executive Summary konnte nicht erzeugt werden."

    subtitle = f"Ordner: {target_dir.name} · {state.run_type}"
    report_name = target.output_basename
    if not report_name:
        ai_suffix = ai_model_filename_suffix(
            model_label=state.model_label, model_id=state.model_id
        )
        if state.run_type.upper() == "TSA":
            report_name = f"TSA_Modell_Bericht_{target_dir.name}_{ai_suffix}.docx"
        else:
            report_name = corr_report_basename(ai_suffix)
    out_path = target_dir / report_name

    docx_kwargs: dict[str, Any] = {
        "title": target.title,
        "subtitle": subtitle,
        "summary": summary,
        "text_sections": [],
        "analysis_sections": analysis_sections,
        "appendix_sections": appendix_sections,
        "image_sections": image_sections if target.report_layout != "tsa_model" else [],
        "model_label": state.model_label,
        "layout": target.report_layout,
        "numbered_sections": numbered_sections or None,
        "section_images": dict(section_images) if section_images else None,
    }

    build_run_report_docx(out_path, **docx_kwargs)

    pdf_path = target_dir / Path(report_name).with_suffix(".pdf").name
    build_run_report_pdf(pdf_path, **docx_kwargs)

    rel = relative_output_path(out_path)
    pdf_rel = relative_output_path(pdf_path)
    llm_calls = state.llm_calls_total
    return {
        "ok": True,
        "ai_ok": llm_calls > 0 and not target.ai_errors,
        "status": "done",
        "message": f"KI-Bericht: {target.rel_path}/{report_name}",
        "report_path": str(out_path),
        "report_rel": rel,
        "report_url": f"/output/file/{rel}" if rel else None,
        "report_pdf_path": str(pdf_path),
        "report_pdf_rel": pdf_rel,
        "report_pdf_url": f"/output/file/{pdf_rel}" if pdf_rel else None,
        "model": state.model_id,
        "target": target.rel_path,
        "png_count": target.png_count,
        "text_count": target.text_count,
        "llm_calls": llm_calls,
        "ai_errors": list(target.ai_errors),
        "ai_warnings": list(target.ai_warnings),
        "rate_limit_events": [e.to_dict() for e in state.rate_limit_events],
        "rate_limit_pause_count": sum(
            1 for e in state.rate_limit_events if e.user_choice == "pause"
        ),
        "token_usage": {
            **state.token_usage,
            "model": state.model_label,
            "calls": state.llm_calls_total,
        },
        "langfuse_active": state.langfuse_active,
    }


def step_report_session(
    output_dir: str | Path,
    *,
    action: str | None = None,
    auto_pause: bool = False,
) -> dict[str, Any]:
    """Verarbeitet KI-Berichtsschritte bis Checkpoint, Fertig oder Fehler."""
    from tslab.services.report_service import _model_spec_for_id, load_report_config

    config = load_report_config()
    run_path = _resolve_output_dir(output_dir)
    state = load_session(run_path)
    if state is None:
        return {
            "ok": False,
            "status": "error",
            "message": "Keine Berichtssession — zuerst prepare aufrufen.",
        }

    if action == "pause":
        time.sleep(PAUSE_SECONDS)
        state.rate_limit_events.append(
            RateLimitEvent(
                at_call=state.llm_calls_total,
                user_choice="pause",
                paused_seconds=PAUSE_SECONDS,
                reason="user_pause",
            )
        )
        state.calls_since_checkpoint = 0
    elif action == "finish":
        state.finish_early = True
        state.rate_limit_events.append(
            RateLimitEvent(
                at_call=state.llm_calls_total,
                user_choice="finish",
                paused_seconds=0,
                reason="user_finish",
            )
        )

    init_langfuse(config)
    spec = _model_spec_for_id(config, state.model_id)
    provider = get_provider(spec.provider, config)

    def record_usage(usage: LLMUsage) -> None:
        _usage_dict_add(state, usage)
        state.llm_calls_total += 1
        state.calls_since_checkpoint += 1

    def run_one_task(target: ReportTargetState, task: ReportTask) -> None:
        nonlocal state
        max_tok = _effective_max_tokens(config, spec)
        image_tok = _effective_max_tokens(config, spec, base=min(600, int(config.max_tokens)))
        system = _SYSTEM_DE

        if task.kind == "text_bundle":
            parts = task.payload.get("parts") or []
            if not parts:
                return
            prompt = str(task.payload.get("prompt") or "")
            resp = provider.complete_text(
                system=system,
                user=prompt + "\n\n" + "\n\n".join(parts),
                model=spec.model_name,
                max_tokens=max_tok,
                trace_name="tslab-report-text",
            )
            target.ai_text_notes.append(["Technische Auswertung (Text/Tabellen)", resp.text])
            record_usage(resp.usage)
            return

        if task.kind == "section":
            parts = task.payload.get("parts") or []
            prompt = str(task.payload.get("prompt") or "")
            image_ctx = "\n\n".join(
                f"Figure {row[0]}: {row[1]}" for row in target.image_sections if len(row) > 1
            )
            user_parts = []
            if parts:
                user_parts.append("--- Source files ---\n" + "\n\n".join(parts))
            if image_ctx:
                user_parts.append("--- Figure descriptions ---\n" + image_ctx)
            resp = provider.complete_text(
                system=system,
                user=prompt + "\n\n" + "\n\n".join(user_parts),
                model=spec.model_name,
                max_tokens=max_tok,
                trace_name=f"tslab-report-section-{task.label[:20]}",
            )
            target.ai_text_notes.append([task.label, resp.text])
            record_usage(resp.usage)
            return

        if task.kind == "image":
            img_path = Path(str(task.payload.get("path") or ""))
            prompt = str(task.payload.get("prompt") or "")
            if spec.vision:
                resp = provider.describe_image(
                    image_path=img_path,
                    prompt=prompt,
                    model=spec.model_name,
                    max_tokens=image_tok,
                    trace_name=f"tslab-report-image-{img_path.stem}",
                )
                expl = resp.text
                record_usage(resp.usage)
            else:
                expl = "(Vision fuer dieses Modell nicht verfuegbar.)"
                target.ai_warnings.append(f"Vision nicht verfuegbar fuer {spec.label}.")
            target.image_sections.append([img_path.name, expl, str(img_path)])
            return

        if task.kind == "summary":
            prompt = str(task.payload.get("prompt") or "")
            summary_input = "\n\n".join(
                [row[1] for row in target.ai_text_notes if len(row) > 1] + _image_notes(target)
            ) or "Keine automatische Voranalyse."
            resp = provider.complete_text(
                system=system,
                user=prompt + "\n\n" + summary_input,
                model=spec.model_name,
                max_tokens=max_tok,
                trace_name="tslab-report-summary",
            )
            target.summary = resp.text
            record_usage(resp.usage)
            return

        if task.kind == "thesis_abgleich":
            from tslab.services.report_service import _read_text_file

            abgleich_path = Path(str(task.payload.get("path") or ""))
            prompt = str(task.payload.get("prompt") or "")
            content = _read_text_file(abgleich_path, max_chars=16000)
            target.text_sections.append([abgleich_path.name, content])
            resp = provider.complete_text(
                system=system,
                user=prompt + "\n\n" + content,
                model=spec.model_name,
                max_tokens=max_tok,
                trace_name="tslab-report-thesis-abgleich",
            )
            target.ai_text_notes.append(["Vergleich Diplomarbeit vs. Lauf", resp.text])
            record_usage(resp.usage)

    awaiting_reason = "checkpoint"
    try:
        while state.current_target < len(state.targets):
            target = state.targets[state.current_target]
            if target.done:
                state.current_target += 1
                continue

            while target.task_index < len(target.tasks):
                if state.finish_early:
                    while target.task_index < len(target.tasks):
                        task = target.tasks[target.task_index]
                        if task.kind == "image" and len(target.image_sections) < target.png_count:
                            img_path = Path(str(task.payload.get("path") or ""))
                            msg = f"Bildanalyse {img_path.name}: abgebrochen (Rate-Limit)"
                            target.ai_errors.append(msg)
                            target.image_sections.append(
                                [img_path.name, f"(Fehler: abgebrochen)", str(img_path)]
                            )
                        elif task.kind == "text_bundle" and not target.ai_text_notes:
                            target.ai_errors.append("Textauswertung: abgebrochen (Rate-Limit)")
                            target.ai_text_notes.append(
                                ["Technische Auswertung (Text/Tabellen)", "(Fehler: abgebrochen)"]
                            )
                        elif task.kind == "section":
                            target.ai_errors.append(
                                f"{task.label}: abgebrochen (Rate-Limit)"
                            )
                            target.ai_text_notes.append(
                                [task.label, "(Fehler: abgebrochen)"]
                            )
                        target.task_index += 1
                    break

                if state.calls_since_checkpoint >= CHECKPOINT_CALLS and not auto_pause:
                    save_session(state, run_path)
                    return _awaiting_response(state, reason=awaiting_reason)

                if auto_pause and state.calls_since_checkpoint >= CHECKPOINT_CALLS:
                    time.sleep(PAUSE_SECONDS)
                    state.rate_limit_events.append(
                        RateLimitEvent(
                            at_call=state.llm_calls_total,
                            user_choice="pause",
                            paused_seconds=PAUSE_SECONDS,
                            reason="auto_pause",
                        )
                    )
                    state.calls_since_checkpoint = 0

                task = target.tasks[target.task_index]
                try:
                    run_one_task(target, task)
                except Exception as exc:
                    if is_rate_limit_error(exc):
                        awaiting_reason = "rate_limit"
                        save_session(state, run_path)
                        if auto_pause:
                            time.sleep(PAUSE_SECONDS)
                            state.rate_limit_events.append(
                                RateLimitEvent(
                                    at_call=state.llm_calls_total,
                                    user_choice="pause",
                                    paused_seconds=PAUSE_SECONDS,
                                    reason="rate_limit",
                                )
                            )
                            state.calls_since_checkpoint = 0
                            continue
                        return _awaiting_response(state, reason="rate_limit", error=str(exc))
                    msg = f"{task.label}: {format_llm_error(exc)}"
                    target.ai_errors.append(msg)
                    if task.kind == "text_bundle":
                        target.ai_text_notes.append(
                            ["Technische Auswertung (Text/Tabellen)", f"(Fehler: {exc})"]
                        )
                    elif task.kind == "image":
                        img_path = Path(str(task.payload.get("path") or ""))
                        target.image_sections.append(
                            [img_path.name, f"(Fehler bei Bildanalyse: {exc})", str(img_path)]
                        )
                    elif task.kind == "section":
                        target.ai_text_notes.append([task.label, f"(Fehler: {exc})"])
                    elif task.kind == "summary":
                        target.summary = f"Zusammenfassung konnte nicht erzeugt werden: {exc}"

                target.task_index += 1

                if state.calls_since_checkpoint >= CHECKPOINT_CALLS and not auto_pause:
                    save_session(state, run_path)
                    return _awaiting_response(state, reason=awaiting_reason)

            report = _finalize_target_documents(state, target, config=config, run_path=run_path)
            state.completed_reports.append(report)
            target.done = True
            state.current_target += 1
            state.calls_since_checkpoint = 0

    finally:
        save_session(state, run_path)

    if state.langfuse_active:
        flush_langfuse()

    delete_session(run_path)
    reports = state.completed_reports
    combined_errors: list[str] = []
    for r in reports:
        combined_errors.extend(r.get("ai_errors") or [])

    return {
        "ok": True,
        "status": "done",
        "message": f"{len(reports)} KI-Bericht(e) erstellt.",
        "reports": reports,
        "report": reports[0] if len(reports) == 1 else None,
        "llm_calls": state.llm_calls_total,
        "rate_limit_events": [e.to_dict() for e in state.rate_limit_events],
        "rate_limit_pause_count": sum(
            1 for e in state.rate_limit_events if e.user_choice == "pause"
        ),
        "ai_errors": combined_errors,
        "token_usage": {
            **state.token_usage,
            "model": state.model_label,
            "calls": state.llm_calls_total,
        },
        "langfuse_active": state.langfuse_active,
    }


def _awaiting_response(
    state: ReportSessionState,
    *,
    reason: str,
    error: str | None = None,
) -> dict[str, Any]:
    done_targets = sum(1 for t in state.targets if t.done)
    total_targets = len(state.targets)
    progress_tasks = sum(t.task_index for t in state.targets)
    total_tasks = sum(len(t.tasks) for t in state.targets)
    msg = (
        f"Nach {CHECKPOINT_CALLS} KI-Anfragen Pause empfohlen "
        f"({state.llm_calls_total} Aufrufe gesamt)."
    )
    if reason == "rate_limit":
        msg = "API-Rate-Limit erreicht. Eine Minute warten und fortfahren?"
    return {
        "ok": True,
        "status": "awaiting_user",
        "message": msg,
        "reason": reason,
        "error": error,
        "llm_calls": state.llm_calls_total,
        "calls_since_checkpoint": state.calls_since_checkpoint,
        "checkpoint_calls": CHECKPOINT_CALLS,
        "pause_seconds": PAUSE_SECONDS,
        "progress": {
            "targets_done": done_targets,
            "targets_total": total_targets,
            "tasks_done": progress_tasks,
            "tasks_total": total_tasks,
        },
        "rate_limit_events": [e.to_dict() for e in state.rate_limit_events],
        "rate_limit_pause_count": sum(
            1 for e in state.rate_limit_events if e.user_choice == "pause"
        ),
    }


def run_report_session_to_completion(
    output_dir: str | Path,
    *,
    model_id: str | None = None,
    run_type: str = "Analyse",
    analysis_mode: str = "extended",
    interactive: bool = False,
) -> dict[str, Any]:
    """Synchroner Lauf (auto_pause wenn nicht interaktiv)."""
    prep = prepare_report_session(
        output_dir,
        model_id=model_id,
        run_type=run_type,
        analysis_mode=analysis_mode,
    )
    if not prep.get("ok"):
        return prep

    while True:
        result = step_report_session(output_dir, auto_pause=not interactive)
        if result.get("status") == "awaiting_user":
            if interactive:
                return result
            step_report_session(output_dir, action="pause", auto_pause=True)
            continue
        return result
