"""Zeilenumbrueche fuer Plot-Beschriftungen (Matplotlib)."""

from __future__ import annotations

import textwrap


def wrap_plot_text(text: str, *, width: int = 52) -> str:
    """Fuegt Zeilenumbrueche fuer mehrzeilige Titel und Fussnoten ein."""
    if not text:
        return ""
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        lines.extend(textwrap.wrap(paragraph, width=width, break_long_words=False))
    return "\n".join(lines)


def wrap_axis_label(text: str, *, width: int = 28) -> str:
    return wrap_plot_text(text, width=width)
