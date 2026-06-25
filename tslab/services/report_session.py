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
    get_provider,
    init_langfuse,
    is_rate_limit_error,
    langfuse_configured,
)
from tslab.services.output_paths import relative_output_path, resolve_output_dir_arg
from tslab.services.report_docx import build_run_report_docx
from tslab.services.report_ai_pdf import build_run_report_pdf
from tslab.services.report_docx import build_run_report_docx
from tslab.services.report_ai_pdf import build_run_report_pdf

CHECKPOINT_CALLS = 5
PAUSE_SECONDS = 60
SESSION_BASENAME = ".report_session.json"

_SYSTEM_DE = (
    "Du bist Analyst fuer Zeitreihen und oekonometrische Auswertungen (Diplomarbeit-Stil). "
    "Antworte auf Deutsch, sachlich und fuer Fachleser verstaendlich. "
    "Keine erfundenen Zahlen — nur was in den Daten/Grafiken sichtbar ist."
)


def _tsa_report_prompts(run_type: str, analysis_mode: str) -> dict[str, str]:
    is_tsa = run_type.upper() == "TSA"
    base_text = (
        "Analysiere die folgenden Dateiinhalte aus einem Analyse-Lauf. "
        "Nenne Kernergebnisse, Auffaelligkeiten und Einordnung (Korrelation/TSA)."
    )
    base_image = (
        "Beschreibe diese Grafik aus einem Zeitreihen-Analyse-Lauf: Achsen, Verlauf, "
        "besondere Muster, Einordnung fuer Korrelation oder TSA. Kurz und praezise."
    )
    base_summary = (
        "Fasse den gesamten Analyse-Lauf in 2–4 Absaetzen zusammen "
        "(Zweck, wichtigste Befunde aus Text/Tabellen und Grafiken)."
    )
    if not is_tsa:
        return {"text": base_text, "image": base_image, "summary": base_summary, "thesis_abgleich": ""}

    text = (
        "Analysiere die Modell-Ausgaben (insbesondere summary.txt) fuer dieses TSA-Modell. "
        "Gehe ein auf: Parameterschaetzung und Modellordnung, Signifikanz der Koeffizienten, "
        "Residuen-Diagnostik, Prognosehorizont, Prognose-Quantile (falls in den Daten), "
        "und den Verlauf der Zeitreihe. Ordne bekannte Marktereignisse ein "
        "(z. B. Crash 1987, Dotcom 2000, Finanzkrise 2008, COVID-2020), soweit im "
        "Beobachtungszeitraum sichtbar. Nur Fakten aus den Dateien — keine erfundenen Werte."
    )
    image = (
        "Beschreibe diese TSA-Grafik: Achsen, Einheiten, Trainings- vs. Prognosebereich, "
        "Konfidenzbaender/Quantile falls vorhanden, Auffaelligkeiten in Residuen, Volatilitaet "
        "oder Zerlegung. Ordne Muster oekonomisch ein (Trend, Volatilitaetscluster, Ereignisse)."
    )
    summary = (
        "Fasse dieses TSA-Modell in 3–5 Absaetzen zusammen: Modellwahl, Schaetzergebnisse, "
        "Diagnostik, Prognose und Einordnung des Zeitreihenverlaufs inkl. relevanter Ereignisse."
    )
    thesis_abgleich = (
        "Vergleiche die R-Koeffizienten der Diplomarbeit mit den geschaetzten Werten dieses Laufs "
        "(coefficient_abgleich.txt). Nenne uebereinstimmende und abweichende Parameter, "
        "moegliche Gruende (Stichprobe, Software, Optimierung) und ob die Abweichungen "
        "oekonomisch relevant sind."
    )
    if analysis_mode.lower() != "thesis":
        thesis_abgleich = ""
    return {"text": text, "image": image, "summary": summary, "thesis_abgleich": thesis_abgleich}


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
    kind: Literal["text_bundle", "image", "summary", "thesis_abgleich"]
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


def session_path_for(output_root: Path) -> Path:
    reports = output_root / "Reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports / SESSION_BASENAME


def load_session(output_root: Path) -> ReportSessionState | None:
    path = session_path_for(output_root)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ReportSessionState.from_dict(data)


def save_session(state: ReportSessionState, output_root: Path) -> Path:
    path = session_path_for(output_root)
    path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def delete_session(output_root: Path) -> None:
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


def _build_tasks_for_dir(
    target_dir: Path,
    *,
    run_type: str,
    analysis_mode: str,
    run_root: Path,
    output_basename: str,
) -> tuple[list[ReportTask], list[tuple[str, str]], int, int]:
    from tslab.services.report_service import _read_table_preview, _read_text_file, _scan_run_dir

    pngs, txts, tables = _scan_run_dir(target_dir)
    prompts = _tsa_report_prompts(run_type, analysis_mode)
    text_sections: list[tuple[str, str]] = []
    text_bundle_parts: list[str] = []
    skip_names = {output_basename, "ai_bericht.pdf"}

    for tf in txts:
        if tf.name in skip_names:
            continue
        content = _read_text_file(tf)
        text_bundle_parts.append(f"### {tf.name}\n{content}")
        text_sections.append((tf.name, content))

    for table_path in tables:
        preview = _read_table_preview(table_path)
        text_bundle_parts.append(f"### {table_path.name}\n{preview}")
        text_sections.append((table_path.name, preview))

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
            label="Zusammenfassung",
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
    from tslab.services.report_service import _model_spec_for_id, load_report_config

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

    init_langfuse(config)
    spec = _model_spec_for_id(config, model_id)
    if not spec.enabled:
        return {"ok": False, "status": "error", "message": f"Modell {spec.id} ist deaktiviert."}

    targets_data: list[ReportTargetState] = []
    for target_dir, title in discover_report_targets(
        run_path, run_type=run_type, analysis_mode=analysis_mode
    ):
        tasks, text_sections, png_n, txt_n = _build_tasks_for_dir(
            target_dir,
            run_type=run_type,
            analysis_mode=analysis_mode,
            run_root=run_path,
            output_basename=config.output_basename,
        )
        if not tasks:
            continue
        rel = (
            "."
            if target_dir.resolve() == run_path.resolve()
            else target_dir.relative_to(run_path).as_posix()
        )
        targets_data.append(
            ReportTargetState(
                rel_path=rel,
                title=title,
                tasks=tasks,
                text_sections=[[h, b] for h, b in text_sections],
                png_count=png_n,
                text_count=txt_n,
            )
        )

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
    target_dir = run_path if target.rel_path == "." else run_path / target.rel_path
    doc_text_sections = [(h, b) for h, b in target.text_sections]
    for heading, body in target.ai_text_notes:
        doc_text_sections.append((heading, body))

    image_sections: list[tuple[str, str, Path]] = []
    for row in target.image_sections:
        if len(row) >= 3:
            image_sections.append((row[0], row[1], Path(row[2])))

    if not target.summary:
        if state.finish_early:
            target.summary = (
                "Bericht vorzeitig abgeschlossen (Rate-Limit / Nutzerwahl). "
                "Einige KI-Abschnitte fehlen."
            )
        else:
            target.summary = "Keine Zusammenfassung erzeugt."

    subtitle = f"Ordner: {target_dir.name} · {state.run_type}"
    report_name = config.output_basename
    out_path = target_dir / report_name

    build_run_report_docx(
        out_path,
        title=target.title,
        subtitle=subtitle,
        summary=target.summary,
        text_sections=doc_text_sections,
        image_sections=image_sections,
        model_label=state.model_label,
    )

    pdf_path = target_dir / Path(config.output_basename).with_suffix(".pdf").name
    build_run_report_pdf(
        pdf_path,
        title=target.title,
        subtitle=subtitle,
        summary=target.summary,
        text_sections=doc_text_sections,
        image_sections=image_sections,
        model_label=state.model_label,
    )

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
        max_tok = config.max_tokens
        image_tok = min(600, max_tok)
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
            target.ai_text_notes.append(["KI-Auswertung Text/Tabellen", resp.text])
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
                            target.ai_errors.append("KI-Auswertung Text: abgebrochen (Rate-Limit)")
                            target.ai_text_notes.append(
                                ["KI-Auswertung Text/Tabellen", "(Fehler: abgebrochen)"]
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
                    msg = f"{task.label}: {exc}"
                    target.ai_errors.append(msg)
                    if task.kind == "text_bundle":
                        target.ai_text_notes.append(["KI-Auswertung Text/Tabellen", f"(Fehler: {exc})"])
                    elif task.kind == "image":
                        img_path = Path(str(task.payload.get("path") or ""))
                        target.image_sections.append(
                            [img_path.name, f"(Fehler bei Bildanalyse: {exc})", str(img_path)]
                        )
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
