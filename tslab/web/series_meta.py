"""Gemeinsame Metadaten und Konstanten fuer die Web-UI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime

PROTECTED_TAG = "Reporting"


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
    tag_ids: tuple[int, ...] = ()
    created_at: datetime | None = None

    @property
    def category_ids(self) -> tuple[int, ...]:
        """Legacy-Alias fuer Templates bis zur Tags-Schema-Migration."""
        return self.tag_ids

    @property
    def category_names(self) -> tuple[str, ...]:
        return self.tags

    @property
    def category_id(self) -> int | None:
        return self.tag_ids[0] if self.tag_ids else None

    @property
    def category_name(self) -> str | None:
        return ", ".join(self.tags) if self.tags else None


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


def series_to_dict(s: SeriesMeta) -> dict:
    d = asdict(s)
    d["first_date"] = s.first_date.isoformat()
    d["last_date"] = s.last_date.isoformat()
    d["tags"] = list(s.tags)
    d["tag_ids"] = list(s.tag_ids)
    # Legacy-Aliase fuer Templates/JS bis zur Tags-Schema-Migration
    d["category_ids"] = list(s.tag_ids)
    d["category_names"] = list(s.tags)
    d["category_id"] = s.tag_ids[0] if s.tag_ids else None
    d["category_name"] = ", ".join(s.tags) if s.tags else None
    if s.created_at is not None:
        d["created_at"] = s.created_at.isoformat()
    d["has_reporting"] = PROTECTED_TAG in s.tags
    return d
