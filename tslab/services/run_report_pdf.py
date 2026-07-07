"""Kompakter PDF-Laufbericht je Analyse-Lauf (prep + final in Reports/)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from tslab.services.run_telemetry import RunTelemetry


def write_run_report_pdf(
    path: Path, telemetry: RunTelemetry, *, variant: str = "final"
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "RunBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        spaceAfter=6,
    )
    h1 = ParagraphStyle(
        "RunH1",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1f6feb"),
        spaceAfter=8,
    )
    mono = ParagraphStyle(
        "RunMono",
        parent=styles["Code"],
        fontSize=8,
        leading=10,
    )

    is_prep = variant == "prep"
    title = (
        f"TSLab Prep-Laufbericht — {telemetry.run_type}"
        if is_prep
        else f"TSLab Laufbericht — {telemetry.run_type}"
    )
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=title,
    )
    story: list = []

    story.append(Paragraph(title, h1))
    started = telemetry.started_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    story.append(Paragraph(f"Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Laufstart: {started}", body))
    if is_prep:
        story.append(
            Paragraph(
                "<i>Vorläufig — KI-Berichte, Token-Verbrauch und finale Links können noch ausstehen.</i>",
                body,
            )
        )
    else:
        ki_status = (telemetry.extra or {}).get("ki_report_status")
        if ki_status == "failed":
            if telemetry.extra.get("ki_user_aborted"):
                story.append(
                    Paragraph(
                        "<b>KI-Berichte vom Nutzer manuell beendet.</b> "
                        "Details im Abschnitt „Fehler“ weiter unten.",
                        body,
                    )
                )
            else:
                story.append(
                    Paragraph(
                        "<b>KI-Berichte fehlgeschlagen.</b> Details im Abschnitt „Fehler“ weiter unten.",
                        body,
                    )
                )
        elif ki_status == "partial":
            story.append(
                Paragraph(
                    "<i>KI-Berichte nur teilweise erstellt — siehe Warnungen und Fehler.</i>",
                    body,
                )
            )
    if telemetry.output_dir:
        story.append(Paragraph(f"<b>Output:</b> {telemetry.output_dir}", mono))
    story.append(Spacer(1, 0.3 * cm))

    # Zeiten je Komponente
    story.append(Paragraph("Zeiten je Komponente", h1))
    if telemetry.components:
        rows = [["Komponente", "Von", "Bis", "Dauer (ms)", "Details"]]
        cell = ParagraphStyle(
            "RunCell",
            parent=body,
            fontSize=8,
            leading=10,
            spaceAfter=0,
            wordWrap="CJK",
        )

        def _component_label(name: str) -> str:
            if name == "tsa_job":
                return "TSA (gesamt)"
            if name.startswith("tsa_model:"):
                return f"  · Modell {name.split(':', 1)[1]}"
            return name

        has_tsa_total = any(c.name == "tsa_job" for c in telemetry.components)
        total_ms = sum(
            c.duration_ms
            for c in telemetry.components
            if not (has_tsa_total and c.name.startswith("tsa_model:"))
        )

        def _wrap_detail(detail: str) -> str:
            # Lange Detailtexte in Reportlab sauber umbrechen.
            return detail.replace(", ", ",<br/>")

        for c in telemetry.components:
            detail = ", ".join(f"{k}={v}" for k, v in c.details.items() if v is not None)
            von = c.started_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            bis = c.ended_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            rows.append(
                [
                    Paragraph(_component_label(c.name), cell),
                    Paragraph(von, cell),
                    Paragraph(bis, cell),
                    Paragraph(f"{c.duration_ms:.1f}", cell),
                    Paragraph(_wrap_detail(detail or "—"), cell),
                ]
            )
        rows.append(
            [
                Paragraph("Gesamt", cell),
                Paragraph("", cell),
                Paragraph("", cell),
                Paragraph(f"{total_ms:.1f}", cell),
                Paragraph("", cell),
            ]
        )
        table = Table(rows, colWidths=[3.5 * cm, 3.2 * cm, 3.2 * cm, 2.2 * cm, 5.4 * cm])
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4fc")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        for row_idx, c in enumerate(telemetry.components, start=1):
            if c.name == "tsa_job":
                style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#f5f9ff")))
                style_cmds.append(("FONTNAME", (0, row_idx), (0, row_idx), "Helvetica-Bold"))
            elif c.name.startswith("tsa_model:"):
                style_cmds.append(("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor("#fafafa")))
        table.setStyle(TableStyle(style_cmds))
        story.append(table)
    else:
        story.append(Paragraph("Keine Komponentenzeiten erfasst.", body))
    story.append(Spacer(1, 0.4 * cm))

    # Token
    story.append(Paragraph("Token-Verbrauch (KI)", h1))
    tok = telemetry.tokens
    if tok.calls:
        story.append(
            Paragraph(
                f"Aufrufe: {tok.calls} · Prompt: {tok.prompt_tokens} · "
                f"Completion: {tok.completion_tokens} · Gesamt: {tok.total_tokens}"
                + (f" · Modelle: {', '.join(tok.models)}" if tok.models else ""),
                body,
            )
        )
    else:
        story.append(Paragraph("Keine KI-Aufrufe / keine Token erfasst.", body))
    story.append(Spacer(1, 0.4 * cm))

    # Langfuse
    story.append(Paragraph("Langfuse", h1))
    lf = telemetry.langfuse or {}
    story.append(
        Paragraph(
            f"Aktiv: {'Ja' if lf.get('configured') else 'Nein'} · "
            f"Public Key: {'gesetzt' if lf.get('public_key_set') else 'fehlt'} · "
            f"Secret Key: {'gesetzt' if lf.get('secret_key_set') else 'fehlt'}<br/>"
            f"Host: {lf.get('host', '—')}<br/>"
            f"{lf.get('note', '')}",
            body,
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    # KI Rate-Limit / Pausen
    story.append(Paragraph("KI-Bericht — Rate-Limit &amp; Pausen", h1))
    extra = telemetry.extra or {}
    pause_count = int(extra.get("rate_limit_pause_count") or 0)
    events = extra.get("rate_limit_events") or []
    if pause_count or events:
        story.append(
            Paragraph(
                f"Nutzer-Pausen (je {60}s): {pause_count} · Ereignisse gesamt: {len(events)}",
                body,
            )
        )
        for i, ev in enumerate(events, 1):
            choice = ev.get("user_choice", "—")
            choice_label = {
                "pause": "1 Min. gewartet",
                "finish": "sofort abgeschlossen",
            }.get(choice, choice)
            story.append(
                Paragraph(
                    f"{i}. Nach Aufruf {ev.get('at_call', '?')}: {choice_label} "
                    f"({ev.get('reason', '')})",
                    body,
                )
            )
    else:
        story.append(Paragraph("Keine Rate-Limit-Pausen erfasst.", body))
    story.append(Spacer(1, 0.4 * cm))

    # Warnungen / Fehler
    story.append(Paragraph("Warnungen", h1))
    if telemetry.warnings:
        for w in telemetry.warnings:
            story.append(Paragraph(f"• {w}", body))
    else:
        story.append(Paragraph("Keine Warnungen.", body))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Fehler", h1))
    if telemetry.errors:
        for e in telemetry.errors:
            story.append(Paragraph(f"• {e}", body))
    else:
        story.append(Paragraph("Keine Fehler.", body))
    story.append(Spacer(1, 0.4 * cm))

    # Links
    story.append(Paragraph("Links &amp; Pfade", h1))
    if telemetry.links:
        for label, target in telemetry.links.items():
            story.append(Paragraph(f"<b>{label}:</b> {target}", mono))
    else:
        story.append(Paragraph("Keine Links erfasst.", body))
    story.append(Spacer(1, 0.4 * cm))

    # UI-Einstellungen (am Ende)
    story.append(Paragraph("UI-Einstellungen des Laufs", h1))
    ui_settings = (telemetry.extra or {}).get("ui_settings") or []
    if ui_settings:
        rows = [["Einstellung", "Wert"]]
        for row in ui_settings:
            label = str(row.get("label") or "—")
            value = str(row.get("value") or "—")
            rows.append([Paragraph(label, body), Paragraph(value.replace("\n", "<br/>"), body)])
        table = Table(rows, colWidths=[5.5 * cm, 11.5 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4fc")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("Keine UI-Einstellungen erfasst.", body))

    doc.build(story)
    return path
