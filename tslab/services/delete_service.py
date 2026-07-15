"""Einheitliches Loeschen fuer Zeitreihen, Korrelation und TSA."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from tslab.db.models import CorrelationHistory, Observation, TimeSeries, TsaHistory, UploadHistory
from tslab.services.tag_service import PROTECTED_TAG, series_has_protected_tag
from tslab.services.entity_tags import (
    ENTITY_CORRELATION,
    ENTITY_SERIES,
    ENTITY_TSA,
    has_protected_tag,
    list_tag_names,
)
from tslab.services.output_paths import resolve_output_dir_arg

DeleteScope = Literal["ui", "storage", "both"]


@dataclass(frozen=True)
class DeletePreview:
    entity_type: str
    entity_id: int | str
    label: str
    tags: list[str]
    actions: list[str]
    warnings: list[str]
    blocked: bool
    block_reason: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def preview_delete_series(session: Session, slug: str, scope: DeleteScope) -> DeletePreview:
    ts = session.scalar(select(TimeSeries).where(TimeSeries.slug == slug))
    if ts is None:
        raise LookupError(f"Zeitreihe '{slug}' nicht gefunden.")
    tags = list_tag_names(session, ENTITY_SERIES, ts.id)
    blocked = has_protected_tag(session, ENTITY_SERIES, ts.id) or series_has_protected_tag(
        session, ts.id
    )
    actions: list[str] = []
    if scope == "ui":
        actions.append("Aus Listen ausblenden (hidden_at)")
    elif scope == "storage":
        actions.append("Zeitreihe und Beobachtungen aus DB loeschen")
    else:
        actions.extend(["Aus Listen entfernen", "Zeitreihe und Beobachtungen aus DB loeschen"])
    corr_refs = session.scalars(
        select(CorrelationHistory.id).where(
            or_(
                CorrelationHistory.series_a_slug == slug,
                CorrelationHistory.series_b_slug == slug,
            ),
            CorrelationHistory.hidden_at.is_(None),
        )
    ).all()
    tsa_refs = session.scalars(
        select(TsaHistory.id).where(
            TsaHistory.series_slug == slug,
            TsaHistory.hidden_at.is_(None),
        )
    ).all()
    warnings: list[str] = []
    if corr_refs:
        warnings.append(f"{len(corr_refs)} Korrelationslauf/Laeufe referenzieren diese Serie.")
    if tsa_refs:
        warnings.append(f"{len(tsa_refs)} TSA-Lauf/Laeufe referenzieren diese Serie.")
    return DeletePreview(
        entity_type=ENTITY_SERIES,
        entity_id=slug,
        label=ts.name,
        tags=tags,
        actions=actions,
        warnings=warnings,
        blocked=blocked,
        block_reason=f"Tag '{PROTECTED_TAG}' ist gesetzt — bitte zuerst entfernen." if blocked else None,
    )


def preview_delete_correlation(session: Session, run_id: int, scope: DeleteScope) -> DeletePreview:
    row = session.get(CorrelationHistory, run_id)
    if row is None:
        raise LookupError(f"Korrelationslauf {run_id} nicht gefunden.")
    tags = list_tag_names(session, ENTITY_CORRELATION, run_id)
    blocked = has_protected_tag(session, ENTITY_CORRELATION, run_id)
    actions: list[str] = []
    if scope == "ui":
        actions.append("Aus Historie ausblenden")
    elif scope == "storage":
        if row.output_dir:
            actions.append(f"Ausgabeordner loeschen: {row.output_dir}")
        actions.append("DB-Eintrag loeschen")
    else:
        if row.output_dir:
            actions.append(f"Ausgabeordner loeschen: {row.output_dir}")
        actions.append("DB-Eintrag loeschen")
    label = row.run_name or f"{row.series_a_slug} vs {row.series_b_slug}"
    return DeletePreview(
        entity_type=ENTITY_CORRELATION,
        entity_id=run_id,
        label=label,
        tags=tags,
        actions=actions,
        warnings=[],
        blocked=blocked,
        block_reason=f"Tag '{PROTECTED_TAG}' ist gesetzt — bitte zuerst entfernen." if blocked else None,
    )


def preview_delete_tsa(session: Session, run_id: int, scope: DeleteScope) -> DeletePreview:
    row = session.get(TsaHistory, run_id)
    if row is None:
        raise LookupError(f"TSA-Lauf {run_id} nicht gefunden.")
    tags = list_tag_names(session, ENTITY_TSA, run_id)
    blocked = has_protected_tag(session, ENTITY_TSA, run_id)
    actions: list[str] = []
    if scope == "ui":
        actions.append("Aus Historie ausblenden")
    elif scope == "storage":
        if row.output_dir:
            actions.append(f"Ausgabeordner loeschen: {row.output_dir}")
        actions.append("DB-Eintrag loeschen")
    else:
        if row.output_dir:
            actions.append(f"Ausgabeordner loeschen: {row.output_dir}")
        actions.append("DB-Eintrag loeschen")
    return DeletePreview(
        entity_type=ENTITY_TSA,
        entity_id=run_id,
        label=f"{row.series_slug} ({row.analysis_mode})",
        tags=tags,
        actions=actions,
        warnings=[],
        blocked=blocked,
        block_reason=f"Tag '{PROTECTED_TAG}' ist gesetzt — bitte zuerst entfernen." if blocked else None,
    )


def _remove_output_dir(path_str: str | None) -> None:
    if not path_str:
        return
    try:
        p = resolve_output_dir_arg(path_str)
    except ValueError:
        return
    if p.is_dir():
        shutil.rmtree(p, ignore_errors=True)


def delete_series(session: Session, slug: str, scope: DeleteScope) -> None:
    preview = preview_delete_series(session, slug, scope)
    if preview.blocked:
        raise ValueError(preview.block_reason or "Loeschen blockiert.")
    ts = session.scalar(select(TimeSeries).where(TimeSeries.slug == slug))
    if ts is None:
        return
    if scope == "ui":
        ts.hidden_at = _now()
        session.commit()
        return
    session.execute(delete(Observation).where(Observation.series_id == ts.id))
    session.execute(delete(UploadHistory).where(UploadHistory.series_id == ts.id))
    session.delete(ts)
    session.commit()


def delete_correlation(session: Session, run_id: int, scope: DeleteScope) -> None:
    preview = preview_delete_correlation(session, run_id, scope)
    if preview.blocked:
        raise ValueError(preview.block_reason or "Loeschen blockiert.")
    row = session.get(CorrelationHistory, run_id)
    if row is None:
        return
    if scope == "ui":
        row.hidden_at = _now()
        session.commit()
        return
    out = row.output_dir
    session.delete(row)
    session.commit()
    if scope in ("storage", "both"):
        _remove_output_dir(out)


def delete_tsa(session: Session, run_id: int, scope: DeleteScope) -> None:
    preview = preview_delete_tsa(session, run_id, scope)
    if preview.blocked:
        raise ValueError(preview.block_reason or "Loeschen blockiert.")
    row = session.get(TsaHistory, run_id)
    if row is None:
        return
    if scope == "ui":
        row.hidden_at = _now()
        session.commit()
        return
    out = row.output_dir
    session.delete(row)
    session.commit()
    if scope in ("storage", "both"):
        _remove_output_dir(out)
