"""Word-Bericht (.docx) aus KI-Analyseabschnitten."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from docx import Document
from docx.shared import Inches, Pt


def build_run_report_docx(
    path: Path,
    *,
    title: str,
    subtitle: str,
    summary: str,
    text_sections: list[tuple[str, str]],
    image_sections: list[tuple[str, str, Path]],
    model_label: str,
) -> Path:
    """Erstellt ai_bericht.docx im Zielordner."""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()

    doc.add_heading(title, level=0)
    doc.add_paragraph(subtitle)
    meta = doc.add_paragraph()
    meta.add_run(f"Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Modell: {model_label}").italic = True
    doc.add_paragraph("")

    doc.add_heading("Zusammenfassung", level=1)
    doc.add_paragraph(summary)
    doc.add_paragraph("")

    if text_sections:
        doc.add_heading("Text- und Tabellendateien", level=1)
        for heading, body in text_sections:
            doc.add_heading(heading, level=2)
            for para in body.split("\n"):
                if para.strip():
                    doc.add_paragraph(para.strip())
            doc.add_paragraph("")

    if image_sections:
        doc.add_heading("Grafiken", level=1)
        for heading, explanation, img_path in image_sections:
            doc.add_heading(heading, level=2)
            if img_path.is_file():
                try:
                    doc.add_picture(str(img_path), width=Inches(5.8))
                except Exception:
                    doc.add_paragraph(f"(Grafik konnte nicht eingebettet werden: {img_path.name})")
            doc.add_paragraph(explanation)
            doc.add_paragraph("")

    doc.save(path)
    return path
