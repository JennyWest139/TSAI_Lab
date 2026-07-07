"""UI-Einstellungen eines Laufs fuer den Laufbericht (lesbare Key-Value-Zeilen)."""

from __future__ import annotations

from typing import Any

_FREQ_LABELS = {
    "D": "Taeglich",
    "W": "Woechentlich",
    "MS": "Monatlich",
    "Y": "Jaehrlich",
}

_MODE_LABELS = {
    "extended": "Extended",
    "thesis": "Thesis (Diplomarbeit)",
}


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Ja" if value else "Nein"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) if value else "—"
    text = str(value).strip()
    return text or "—"


def _analysis_mode_label(mode: str | None) -> str:
    key = str(mode or "extended").strip().lower()
    return _MODE_LABELS.get(key, key)


def _frequency_label(freq: str | None) -> str:
    key = str(freq or "").strip().upper()
    if not key:
        return "Automatisch (Overlap)"
    return _FREQ_LABELS.get(key, key)


def _ki_model_label(model_id: str | None) -> str:
    mid = str(model_id or "").strip()
    if not mid or mid in ("none", "off", "0"):
        return "Ohne KI"
    try:
        from tslab.services.report_service import list_report_models

        for spec in list_report_models():
            if spec.get("id") == mid:
                return str(spec.get("label") or mid)
    except Exception:
        pass
    return mid


def build_correlation_run_settings(
    payload: dict[str, Any],
    *,
    series_a: str,
    series_b: str,
    analysis_mode: str,
    start_date: str,
    end_date: str,
    max_lag: int,
    frequency: str | None,
    run_name: str,
) -> list[tuple[str, str]]:
    return [
        ("Lauftyp", "Korrelation"),
        ("Bezeichnung", _fmt(run_name)),
        ("Serie A", _fmt(series_a)),
        ("Serie B", _fmt(series_b)),
        ("Analysemodus", _analysis_mode_label(analysis_mode)),
        ("Zeitraum Von", _fmt(start_date)),
        ("Zeitraum Bis", _fmt(end_date)),
        ("Frequenz", _frequency_label(frequency)),
        ("Max. Lag", _fmt(max_lag)),
        ("KI-Bericht", _ki_model_label(payload.get("report_model"))),
    ]


def build_tsa_run_settings(
    payload: dict[str, Any],
    *,
    series_slug: str,
    analysis_mode: str,
    models: list[str],
    train_start: str | None,
    train_end: str | None,
    forecast_end: str | None,
    order_mode: str,
    arma_order: str | None = None,
    garch_order: str | None = None,
    quantiles: tuple[float, ...] | list[float] | None = None,
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = [
        ("Lauftyp", "TSA"),
        ("Zeitreihe", _fmt(series_slug)),
        ("Analysemodus", _analysis_mode_label(analysis_mode)),
        ("Modelle", _fmt(models)),
        ("Training Von", _fmt(train_start)),
        ("Training Bis", _fmt(train_end)),
        ("Prognose Bis", _fmt(forecast_end)),
        ("Ordungswahl", "Automatisch" if order_mode == "auto" else "Benutzerdefiniert"),
    ]
    if order_mode == "user":
        rows.append(("ARMA-Ordung (p,q)", _fmt(arma_order)))
        rows.append(("GARCH-Ordung (p,q)", _fmt(garch_order)))
    rows.extend(
        [
            ("Plot: Jahre vor Cutoff", _fmt(payload.get("plot_pre_years"))),
            ("Plot: Prognosejahre", _fmt(payload.get("plot_forecast_years"))),
            ("Plot: Jahre nach Prognose", _fmt(payload.get("plot_post_years"))),
            ("Quantile", _fmt(quantiles)),
            ("KI-Bericht", _ki_model_label(payload.get("report_model"))),
        ]
    )
    return rows
