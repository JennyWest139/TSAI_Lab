#!/usr/bin/env python
"""Benutzerhandbuch-PDF erzeugen: python scripts/build_user_manual.py"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from tslab.docs.user_manual_content import (
    GLOSSARY,
    MANUAL_SUBTITLE,
    MANUAL_TITLE,
    MANUAL_VERSION,
    SECTIONS,
)

_DEFAULT_OUT = (
    ROOT / "tslab" / "web" / "static" / "docs" / "tslab_benutzerhandbuch.pdf"
)


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ManualTitle",
            parent=base["Title"],
            fontSize=22,
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0f1c2e"),
        ),
        "subtitle": ParagraphStyle(
            "ManualSubtitle",
            parent=base["Normal"],
            fontSize=11,
            spaceAfter=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#5c6b7f"),
        ),
        "h1": ParagraphStyle(
            "ManualH1",
            parent=base["Heading1"],
            fontSize=14,
            spaceBefore=18,
            spaceAfter=8,
            textColor=colors.HexColor("#1f6feb"),
        ),
        "h2": ParagraphStyle(
            "ManualH2",
            parent=base["Heading2"],
            fontSize=11,
            spaceBefore=10,
            spaceAfter=4,
            textColor=colors.HexColor("#1a2332"),
        ),
        "body": ParagraphStyle(
            "ManualBody",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            spaceAfter=8,
        ),
        "mono": ParagraphStyle(
            "ManualMono",
            parent=base["Code"],
            fontSize=9,
            leading=12,
            leftIndent=12,
        ),
    }


def _para(text: str, style) -> Paragraph:
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
    return Paragraph(escaped, style)


def build_user_manual_pdf(output_path: Path | None = None) -> Path:
    out = output_path or _DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=MANUAL_TITLE,
        author="TSLab",
    )
    styles = _styles()
    story: list = []

    story.append(_para(MANUAL_TITLE, styles["title"]))
    story.append(_para(MANUAL_SUBTITLE, styles["subtitle"]))
    story.append(_para(f"Stand: {MANUAL_VERSION}", styles["subtitle"]))
    story.append(Spacer(1, 0.5 * cm))

    for section in SECTIONS:
        story.append(_para(section.title, styles["h1"]))
        for block in section.body.split("\n\n"):
            block = block.strip()
            if not block:
                continue
            if block.startswith("  •") or block.startswith("Schritt"):
                story.append(_para(block, styles["mono"]))
            else:
                story.append(_para(block, styles["body"]))
        story.append(Spacer(1, 0.2 * cm))

    story.append(PageBreak())
    story.append(_para("8. Wörterbuch — Finanz- und Ökonometrie-Begriffe", styles["h1"]))
    story.append(
        _para(
            "Kurzdefinitionen für die Arbeit mit TSLab. Das Kapitel wird "
            "mit weiteren Begriffen ergänzt.",
            styles["body"],
        )
    )

    for entry in GLOSSARY:
        story.append(_para(entry.title, styles["h2"]))
        story.append(_para(entry.body, styles["body"]))

    doc.build(story)
    return out


def main() -> None:
    path = build_user_manual_pdf()
    print(f"Benutzerhandbuch: {path}")


if __name__ == "__main__":
    main()
