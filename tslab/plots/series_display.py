"""Einheitliche Beschriftung: Original vs. transformierte / Modellwerte."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeriesDisplay:
    """Beschreibt, welche Werte in einer Grafik dargestellt werden."""

    short_name: str
    value_axis: str
    data_basis: str

    def footnote(self) -> str:
        return f"Datengrundlage: {self.data_basis}"

    def title(self, plot_kind: str) -> str:
        return f"{plot_kind} - {self.short_name}"

    def ar_residuals(self, order: int) -> SeriesDisplay:
        model = f"AR({order})" if order > 0 else "AR(0) / Konstante"
        return SeriesDisplay(
            short_name=f"Residuen nach {model}",
            value_axis=f"Residuen ({model})",
            data_basis=(
                f"Modelloutput: Residuen aus {model}, "
                f"angepasst an: {self.data_basis}"
            ),
        )


PDAX_ORIGINAL = SeriesDisplay(
    short_name="PDAX (Niveau)",
    value_axis="Original: PDAX-Kursniveau",
    data_basis="Originalwerte (Werte.csv, Spalte PDAX), ohne Transformation",
)

PDAX_LOG = SeriesDisplay(
    short_name="log(PDAX)",
    value_axis="Transformiert: ln(PDAX)",
    data_basis="Bearbeitet: ln(PDAX) auf Originalniveau, nur positive Kurse",
)

PDAX_LOG_RETURNS = SeriesDisplay(
    short_name="kont. Renditen (trendbereinigt)",
    value_axis="Transformiert: diff(ln(PDAX)), linear trendbereinigt",
    data_basis=(
        "Bearbeitet: erste Differenz von ln(PDAX), "
        "danach lineare Trendentfernung (Residuum)"
    ),
)
