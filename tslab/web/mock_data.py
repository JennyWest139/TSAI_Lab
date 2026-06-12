"""Mock-Daten fuer die UI (spaeter durch DB/Services ersetzt)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class SeriesMeta:
    slug: str
    name: str
    label_de: str
    first_date: date
    last_date: date
    observation_count: int
    frequency: str
    frequency_label: str
    source_file: str | None = None


@dataclass(frozen=True)
class CorrelationRun:
    id: int
    series_a: str
    series_b: str
    start_date: date
    end_date: date
    analysis_mode: str
    max_lag: int
    best_lag: int | None
    best_r: float | None
    created_at: datetime


@dataclass(frozen=True)
class TsaRun:
    id: int
    series_slug: str
    models: list[str]
    analysis_mode: str
    train_start: date
    train_end: date
    forecast_end: date
    status: str
    created_at: datetime


MOCK_SERIES: list[SeriesMeta] = [
    SeriesMeta(
        slug="pdax",
        name="PDAX",
        label_de="PDAX (Performanceindex)",
        first_date=date(1959, 12, 1),
        last_date=date(2007, 12, 1),
        observation_count=576,
        frequency="MS",
        frequency_label="Monatlich",
        source_file="Werte.csv",
    ),
    SeriesMeta(
        slug="dax",
        name="DAX",
        label_de="DAX",
        first_date=date(1987, 12, 1),
        last_date=date(2007, 12, 1),
        observation_count=241,
        frequency="MS",
        frequency_label="Monatlich",
        source_file="Werte.csv",
    ),
    SeriesMeta(
        slug="erwerbslose",
        name="Erwerbslose",
        label_de="Erwerbslosenquote",
        first_date=date(1991, 1, 1),
        last_date=date(2007, 1, 1),
        observation_count=193,
        frequency="MS",
        frequency_label="Monatlich",
        source_file="Erwerbslose.csv",
    ),
    SeriesMeta(
        slug="dowjones",
        name="Dow Jones",
        label_de="Dow Jones Industrial",
        first_date=date(1990, 1, 1),
        last_date=date(2007, 6, 1),
        observation_count=210,
        frequency="MS",
        frequency_label="Monatlich",
    ),
]

MOCK_CORRELATION_HISTORY: list[CorrelationRun] = [
    CorrelationRun(
        id=1,
        series_a="pdax",
        series_b="erwerbslose",
        start_date=date(1991, 1, 1),
        end_date=date(2007, 1, 1),
        analysis_mode="thesis",
        max_lag=24,
        best_lag=3,
        best_r=0.412,
        created_at=datetime(2026, 6, 10, 14, 22),
    ),
    CorrelationRun(
        id=2,
        series_a="dax",
        series_b="erwerbslose",
        start_date=date(1991, 1, 1),
        end_date=date(2007, 6, 30),
        analysis_mode="thesis",
        max_lag=12,
        best_lag=-2,
        best_r=-0.287,
        created_at=datetime(2026, 6, 8, 9, 15),
    ),
]

MOCK_TSA_HISTORY: list[TsaRun] = [
    TsaRun(
        id=1,
        series_slug="pdax",
        models=["arma-garch"],
        analysis_mode="thesis",
        train_start=date(1987, 12, 1),
        train_end=date(2006, 7, 1),
        forecast_end=date(2008, 7, 1),
        status="fertig",
        created_at=datetime(2026, 6, 11, 15, 28),
    ),
    TsaRun(
        id=2,
        series_slug="pdax",
        models=["arma", "garch", "arma-garch"],
        analysis_mode="thesis",
        train_start=date(1987, 12, 1),
        train_end=date(2007, 7, 1),
        forecast_end=date(2008, 7, 1),
        status="fertig",
        created_at=datetime(2026, 6, 9, 11, 5),
    ),
]

TSA_MODELS = [
    {
        "id": "arma",
        "label": "ARMA(1,1)",
        "description": "Mittelwertmodell (statsmodels), Residuen-Diagnostik",
    },
    {
        "id": "garch",
        "label": "GARCH(1,1)",
        "description": "Volatilitaet mit Quantilbaendern (arch)",
    },
    {
        "id": "arma-garch",
        "label": "ARMA(1,1)-GARCH(1,1)",
        "description": "Kombiniertes Modell (Diplomarbeit-Stil)",
    },
]

FREQUENCY_OPTIONS = [
    {"id": "MS", "label": "Monatlich", "days": 30},
    {"id": "W", "label": "Woechentlich", "days": 7},
    {"id": "D", "label": "Taeglich", "days": 1},
    {"id": "Y", "label": "Jaehrlich", "days": 365},
    {"id": "H", "label": "Stuendlich", "days": 0},
]


def series_by_slug(slug: str) -> SeriesMeta | None:
    return next((s for s in MOCK_SERIES if s.slug == slug), None)


def series_to_dict(s: SeriesMeta) -> dict:
    d = asdict(s)
    d["first_date"] = s.first_date.isoformat()
    d["last_date"] = s.last_date.isoformat()
    return d


def pair_overlap(slug_a: str, slug_b: str) -> dict | None:
    a = series_by_slug(slug_a)
    b = series_by_slug(slug_b)
    if a is None or b is None:
        return None
    overlap_start = max(a.first_date, b.first_date)
    overlap_end = min(a.last_date, b.last_date)
    if overlap_start > overlap_end:
        return None
    freq = a.frequency if a.frequency == b.frequency else "MS"
    freq_label = a.frequency_label if a.frequency == b.frequency else "Gemischt (Vorschlag: Monatlich)"
    months = (overlap_end.year - overlap_start.year) * 12 + overlap_end.month - overlap_start.month + 1
    return {
        "series_a": series_to_dict(a),
        "series_b": series_to_dict(b),
        "overlap_start": overlap_start.isoformat(),
        "overlap_end": overlap_end.isoformat(),
        "suggested_start": overlap_start.isoformat(),
        "suggested_end": overlap_end.isoformat(),
        "overlap_observations": months,
        "suggested_frequency": freq,
        "suggested_frequency_label": freq_label,
        "frequencies": FREQUENCY_OPTIONS,
    }


def mock_upload_result(filename: str) -> dict:
    slug = filename.rsplit(".", 1)[0].lower().replace(" ", "_")[:40] or "upload"
    today = date.today()
    return {
        "ok": True,
        "message": f"Upload simuliert: {filename}",
        "series": {
            "slug": slug,
            "name": slug.upper(),
            "first_date": (today - timedelta(days=365 * 5)).isoformat(),
            "last_date": today.isoformat(),
            "observation_count": 60,
            "frequency": "MS",
            "frequency_label": "Monatlich",
        },
    }
