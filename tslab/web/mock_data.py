"""Mock-Daten fuer die UI (spaeter durch DB/Services ersetzt)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

PROTECTED_CATEGORY = "Reporting"

# In-Memory-Kategorien fuer Mock-Modus (bleibt waehrend Server-Lauf erhalten)
_mock_categories: list[dict] = [{"id": 1, "name": PROTECTED_CATEGORY}]
_mock_next_category_id = 2
_mock_series_categories: dict[str, list[int]] = {}  # slug -> category_ids
_mock_run_categories: dict[tuple[str, int], list[int]] = {}  # (entity_type, id) -> ids


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
    id: int | None = None
    tags: tuple[str, ...] = ()
    category_id: int | None = None
    category_name: str | None = None
    category_ids: tuple[int, ...] = ()
    category_names: tuple[str, ...] = ()
    created_at: datetime | None = None


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
    output_dir: str | None = None


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
    output_dir: str | None = None


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
        output_dir="output/correlation_thesis_pdax_vs_erwerbslose_1991-01-01_to_2007-01-01",
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
        output_dir="output/correlation_thesis_dax_vs_erwerbslose_1991-01-01_to_2007-06-30",
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
        output_dir="output/tsa_thesis_1987-12-01_to_2006-07-01",
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
        output_dir="output/tsa_thesis_1987-12-01_to_2007-07-01",
    ),
]


def suggest_run_name(slug_a: str, slug_b: str) -> str:
    """z. B. dax + bip -> DAXvsBIP"""
    a = slug_a.upper().replace("_", "")
    b = slug_b.upper().replace("_", "")
    return f"{a}vs{b}"

TSA_MODELS = [
    {
        "id": "decomp-additive",
        "label": "Additive Zerlegung",
        "description": "Trend, Saison, Rest (statsmodels seasonal_decompose)",
    },
    {
        "id": "decomp-multiplicative",
        "label": "Multiplikative Zerlegung",
        "description": "Multiplikative Saisonzerlegung (nur positive Werte)",
    },
    {
        "id": "arma",
        "label": "ARMA",
        "description": "Mittelwertmodell (statsmodels), Ordung per Auto/User-Order",
    },
    {
        "id": "garch",
        "label": "GARCH",
        "description": "Volatilitaet mit Quantilbaendern (arch)",
    },
    {
        "id": "arma-garch",
        "label": "ARMA-GARCH",
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


def _mock_category_names(ids: list[int]) -> tuple[str, ...]:
    names: list[str] = []
    for cid in ids:
        cat = mock_category_by_id(cid)
        if cat:
            names.append(cat["name"])
    return tuple(names)


def series_by_slug(slug: str) -> SeriesMeta | None:
    base = next((s for s in MOCK_SERIES if s.slug == slug), None)
    if base is None:
        return None
    cat_ids = list(_mock_series_categories.get(slug, []))
    if not cat_ids:
        return base
    names = _mock_category_names(cat_ids)
    return replace(
        base,
        category_ids=tuple(cat_ids),
        category_names=names,
        category_id=cat_ids[0],
        category_name=", ".join(names) if names else None,
    )


def mock_category_by_id(category_id: int) -> dict | None:
    return next((c for c in _mock_categories if c["id"] == category_id), None)


def mock_list_categories() -> list[dict]:
    counts: dict[int, int] = {c["id"]: 0 for c in _mock_categories}
    for slug, cids in _mock_series_categories.items():
        if not series_by_slug(slug):
            continue
        for cid in cids:
            if cid in counts:
                counts[cid] += 1
    return [
        {"id": c["id"], "name": c["name"], "series_count": counts.get(c["id"], 0)}
        for c in sorted(_mock_categories, key=lambda x: x["name"].lower())
    ]


def mock_create_category(name: str) -> dict:
    global _mock_next_category_id
    clean = name.strip()
    if not clean:
        raise ValueError("Kategoriename darf nicht leer sein.")
    if clean.lower() == PROTECTED_CATEGORY.lower():
        raise ValueError(f"Kategorie '{PROTECTED_CATEGORY}' ist reserviert.")
    if any(c["name"].lower() == clean.lower() for c in _mock_categories):
        raise ValueError(f"Kategorie '{clean}' existiert bereits.")
    row = {"id": _mock_next_category_id, "name": clean}
    _mock_next_category_id += 1
    _mock_categories.append(row)
    return {"ok": True, "id": row["id"], "name": row["name"]}


def mock_update_category(category_id: int, name: str) -> dict:
    row = mock_category_by_id(category_id)
    if row is None:
        raise ValueError("Kategorie nicht gefunden.")
    if row["name"] == PROTECTED_CATEGORY:
        raise ValueError(f"Kategorie '{PROTECTED_CATEGORY}' darf nicht umbenannt werden.")
    clean = name.strip()
    if not clean:
        raise ValueError("Kategoriename darf nicht leer sein.")
    other = next(
        (c for c in _mock_categories if c["name"].lower() == clean.lower() and c["id"] != category_id),
        None,
    )
    if other:
        raise ValueError(f"Kategorie '{clean}' existiert bereits.")
    row["name"] = clean
    return {"ok": True, "id": category_id, "name": clean}


def mock_delete_category(category_id: int) -> dict:
    row = mock_category_by_id(category_id)
    if row is None:
        raise ValueError("Kategorie nicht gefunden.")
    if row["name"] == PROTECTED_CATEGORY:
        raise ValueError(f"Kategorie '{PROTECTED_CATEGORY}' darf nicht gelöscht werden.")
    _mock_categories[:] = [c for c in _mock_categories if c["id"] != category_id]
    for slug, cids in list(_mock_series_categories.items()):
        _mock_series_categories[slug] = [c for c in cids if c != category_id]
        if not _mock_series_categories[slug]:
            del _mock_series_categories[slug]
    return {"ok": True}


def mock_update_series_meta(
    slug: str,
    *,
    name: str,
    category_id: int | None = None,
    category_ids: list[int] | None = None,
) -> dict:
    base = next((s for s in MOCK_SERIES if s.slug == slug), None)
    if base is None:
        raise ValueError(f"Zeitreihe '{slug}' nicht gefunden.")
    ids = list(category_ids if category_ids is not None else ([] if category_id is None else [category_id]))
    for cid in ids:
        if mock_category_by_id(cid) is None:
            raise ValueError("Kategorie nicht gefunden.")
    if ids:
        _mock_series_categories[slug] = ids
    else:
        _mock_series_categories.pop(slug, None)
    updated = series_by_slug(slug)
    assert updated is not None
    d = series_to_dict(replace(updated, name=name.strip(), label_de=name.strip()))
    return {"ok": True, "series": d}


def mock_assign_run_categories(entity_type: str, entity_id: int, series_slugs: list[str]) -> list[int]:
    merged: list[int] = []
    seen: set[int] = set()
    for slug in series_slugs:
        for cid in _mock_series_categories.get(slug, []):
            if cid not in seen:
                seen.add(cid)
                merged.append(cid)
    if merged:
        _mock_run_categories[(entity_type, entity_id)] = merged
    return merged


def mock_run_category_names(entity_type: str, entity_id: int) -> tuple[str, ...]:
    return _mock_category_names(_mock_run_categories.get((entity_type, entity_id), []))


def mock_run_matches_category(
    entity_type: str, entity_id: int, series_slugs: list[str], category_id: int
) -> bool:
    if category_id in _mock_run_categories.get((entity_type, entity_id), []):
        return True
    for slug in series_slugs:
        s = series_by_slug(slug)
        if s is None:
            continue
        ids = set(s.category_ids or (() if s.category_id is None else (s.category_id,)))
        if category_id in ids:
            return True
    return False


def mock_list_series(
    *,
    tag: str | None = None,
    category_id: int | None = None,
    category_ids: list[int] | None = None,
) -> list[SeriesMeta]:
    series = [series_by_slug(s.slug) for s in MOCK_SERIES]
    series = [s for s in series if s is not None]
    if tag:
        series = [s for s in series if tag in s.tags]
    ids_filter = list(category_ids or [])
    if category_id is not None and not ids_filter:
        ids_filter = [category_id]
    if ids_filter:
        id_set = set(ids_filter)
        series = [
            s
            for s in series
            if id_set.intersection(set(s.category_ids or (() if s.category_id is None else (s.category_id,))))
        ]
    return series


def series_to_dict(s: SeriesMeta) -> dict:
    d = asdict(s)
    d["first_date"] = s.first_date.isoformat()
    d["last_date"] = s.last_date.isoformat()
    d["tags"] = list(s.tags)
    d["category_ids"] = list(s.category_ids)
    d["category_names"] = list(s.category_names)
    if s.created_at is not None:
        d["created_at"] = s.created_at.isoformat()
    if s.category_names and not s.category_name:
        d["category_name"] = ", ".join(s.category_names)
    d["has_reporting"] = "Reporting" in s.tags or s.category_name == "Reporting"
    return d


def mock_series_pandas(slug: str) -> pd.Series:
    """Synthetische Monatsreihe fuer Mock-Modus (deterministisch pro Slug)."""
    meta = series_by_slug(slug)
    if meta is None:
        raise LookupError(f"Unbekannte Mock-Serie: {slug}")

    dates = pd.date_range(meta.first_date, meta.last_date, freq="MS")
    bases = {"pdax": 120.0, "dax": 1500.0, "erwerbslose": 8.5, "dowjones": 3200.0}
    growth = {"pdax": 0.004, "dax": 0.003, "erwerbslose": 0.001, "dowjones": 0.0025}
    base = bases.get(slug, 100.0)
    g = growth.get(slug, 0.002)
    seed = sum(ord(c) for c in slug) % (2**31)
    rng = np.random.default_rng(seed)
    t = np.arange(len(dates), dtype=float)
    trend = base * np.exp(g * t / 12.0)
    noise = rng.normal(0, base * 0.015, len(dates))
    values = np.maximum(trend + noise, base * 0.05)
    return pd.Series(values, index=dates, name=slug)


def _mock_observation_dates(meta: SeriesMeta) -> list[date]:
    if meta.frequency == "D":
        return [d.date() for d in pd.date_range(meta.first_date, meta.last_date, freq="D")]
    return [d.date() for d in pd.date_range(meta.first_date, meta.last_date, freq="MS")]


def pair_overlap(slug_a: str, slug_b: str) -> dict | None:
    a = series_by_slug(slug_a)
    b = series_by_slug(slug_b)
    if a is None or b is None:
        return None

    from tslab.services.month_align import compute_pair_overlap

    dates_a = _mock_observation_dates(a)
    dates_b = _mock_observation_dates(b)
    ctx = compute_pair_overlap(
        dates_a,
        dates_b,
        first_a=a.first_date,
        last_a=a.last_date,
        count_a=a.observation_count,
        first_b=b.first_date,
        last_b=b.last_date,
        count_b=b.observation_count,
        slug_a=slug_a,
        slug_b=slug_b,
        label_a=a.label_de,
        label_b=b.label_de,
    )
    if ctx is None:
        return None

    return {
        "series_a": series_to_dict(a),
        "series_b": series_to_dict(b),
        "suggested_run_name": suggest_run_name(slug_a, slug_b),
        "frequencies": FREQUENCY_OPTIONS,
        **ctx,
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
