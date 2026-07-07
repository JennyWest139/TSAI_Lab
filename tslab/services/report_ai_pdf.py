"""PDF-Bericht aus KI-Analyseabschnitten."""

from __future__ import annotations

import html
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer


def _esc(text: str) -> str:
    return html.escape(text or "").replace("\n", "<br/>")


def build_run_report_pdf(
    path: Path,
    *,
    title: str,
    subtitle: str,
    summary: str,
    text_sections: list[tuple[str, str]],
    image_sections: list[tuple[str, str, Path]],
    model_label: str,
    analysis_sections: list[tuple[str, str]] | None = None,
    appendix_sections: list[tuple[str, str]] | None = None,
    layout: str = "standard",
    numbered_sections: list[tuple[str, str]] | None = None,
    section_images: dict[str, list[tuple[str, str, Path]]] | None = None,
) -> Path:
    """Erstellt einen KI-Bericht (.pdf) im Zielordner."""
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "AiBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        spaceAfter=6,
    )
    h1 = ParagraphStyle(
        "AiH1",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1f6feb"),
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "AiH2",
        parent=styles["Heading3"],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=4,
    )
    mono = ParagraphStyle(
        "AiMono",
        parent=styles["Code"],
        fontSize=8,
        leading=10,
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

    story.append(Paragraph(_esc(title), h1))
    story.append(Paragraph(_esc(subtitle), body))
    story.append(
        Paragraph(
            _esc(
                f"Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M')} · KI-Modell: {model_label}"
            ),
            mono,
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    if layout == "tsa_model" and numbered_sections:
        images_by_section: dict[str, list[tuple[str, str, Path]]] = defaultdict(list)
        if section_images:
            for key, imgs in section_images.items():
                images_by_section[key].extend(imgs)
        for heading, content in numbered_sections:
            story.append(Paragraph(_esc(heading), h1))
            story.append(Paragraph(_esc(content), body))
            for img_heading, explanation, img_path in images_by_section.get(heading, []):
                story.append(Paragraph(_esc(img_heading), h2))
                if img_path.is_file():
                    try:
                        story.append(
                            Image(
                                str(img_path),
                                width=14 * cm,
                                height=8 * cm,
                                kind="proportional",
                            )
                        )
                        story.append(Spacer(1, 0.15 * cm))
                    except Exception:
                        story.append(
                            Paragraph(
                                _esc(f"(Grafik nicht eingebettet: {img_path.name})"),
                                body,
                            )
                        )
                story.append(Paragraph(_esc(explanation), body))
            story.append(Spacer(1, 0.2 * cm))
        if appendix_sections:
            story.append(Paragraph("Appendix — Source files", h1))
            for heading, content in appendix_sections:
                story.append(Paragraph(_esc(heading), h2))
                story.append(Paragraph(_esc(content), body))
    else:
        story.append(Paragraph("Executive Summary", h1))
        story.append(Paragraph(_esc(summary), body))
        story.append(Spacer(1, 0.2 * cm))

        analysis = analysis_sections if analysis_sections is not None else text_sections
        appendix = appendix_sections if appendix_sections is not None else []

        if analysis:
            story.append(Paragraph("Fachliche Auswertung", h1))
            for heading, content in analysis:
                story.append(Paragraph(_esc(heading), h2))
                story.append(Paragraph(_esc(content), body))

        if appendix:
            story.append(Paragraph("Anhang — Ausgabedateien", h1))
            for heading, content in appendix:
                story.append(Paragraph(_esc(heading), h2))
                story.append(Paragraph(_esc(content), body))

        if image_sections:
            story.append(Paragraph("Grafiken und Visualisierungen", h1))
            for heading, explanation, img_path in image_sections:
                story.append(Paragraph(_esc(heading), h2))
                if img_path.is_file():
                    try:
                        story.append(
                            Image(
                                str(img_path),
                                width=14 * cm,
                                height=8 * cm,
                                kind="proportional",
                            )
                        )
                        story.append(Spacer(1, 0.15 * cm))
                    except Exception:
                        story.append(
                            Paragraph(
                                _esc(f"(Grafik nicht eingebettet: {img_path.name})"),
                                body,
                            )
                        )
                story.append(Paragraph(_esc(explanation), body))

    doc.build(story)
    return path
