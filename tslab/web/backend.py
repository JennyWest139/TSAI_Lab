"""Web-Backend: DB-Services mit Mock-Fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func, select

from tslab.db.engine import (
    DatabaseConnectionError,
    check_connection,
    get_database_display_name,
    get_database_kind,
    get_database_url,
    get_session,
    get_sqlite_file_path,
    reset_engine_cache,
)
from tslab.db.models import Category, CorrelationHistory, Observation, TimeSeries, TsaHistory
from tslab.services.analysis_mode import (
    AnalysisMode,
    get_analysis_mode_config,
    resolve_study_dates_for_mode,
)
from tslab.services.category_service import (
    create_category,
    delete_category,
    get_category,
    list_categories,
    update_category,
)
from tslab.services.correlation import resolve_correlation_study_dates
from tslab.services.correlation_job import run_correlation_job
from tslab.services.delete_service import (
    DeletePreview,
    delete_correlation,
    delete_series,
    delete_tsa,
    preview_delete_correlation,
    preview_delete_series,
    preview_delete_tsa,
)
from tslab.services.entity_tags import (
    ENTITY_CORRELATION,
    ENTITY_SERIES,
    ENTITY_TSA,
    PROTECTED_TAG,
    add_tag,
    entity_ids_with_tag,
    list_tags,
    remove_tag,
    set_tags,
    suggest_tags,
)
from tslab.services.tsa_job import forecast_plot_window_from_payload, run_tsa_job
from tslab.services.order_selection import parse_order_list
from tslab.services.report_service import (
    ai_reports_available,
    generate_run_report,
    list_report_models,
    load_report_config,
)
from tslab.services.run_telemetry import RunTelemetryCollector, langfuse_status_from_config
from tslab.services.frequency_detect import detect_frequency_from_dates
from tslab.services.month_align import (
    compute_pair_overlap,
    snap_to_overlap_stamp_for_frequency,
)
from tslab.services.timeseries_store import (
    available_dates_for_series,
    get_series_by_slug,
    import_series_from_upload,
    list_series,
    load_series_full_pandas,
)
from tslab.web import mock_data as mock
from tslab.web.csv_preview import (
    date_detection_for_column,
    decimal_detection_for_column,
    load_upload_dataframe,
    preview_upload_bytes,
)
from tslab.web.mock_data import FREQUENCY_OPTIONS, SeriesMeta, suggest_run_name
from tslab.web.output_browser import browse_url_for, output_root, relative_output_path, zip_directory
from tslab.web.perf import log_timing
from tslab.web.series_chart import build_pair_chart_payload, build_series_chart_payload
from tslab.web.tsa_window_preview import build_tsa_window_preview


@dataclass(frozen=True)
class CorrelationRunView:
    id: int
    series_a: str
    series_b: str
    start_date: date
    end_date: date
    analysis_mode: str | None
    max_lag: int
    best_lag: int | None
    best_r: float | None
    created_at: datetime
    output_dir: str | None = None
    run_name: str | None = None
    tags: tuple[str, ...] = ()

    @property
    def display_name(self) -> str:
        return self.run_name or suggest_run_name(self.series_a, self.series_b)

    @property
    def has_reporting(self) -> bool:
        return PROTECTED_TAG in self.tags

    @property
    def browse_url(self) -> str | None:
        return browse_url_for(self.output_dir)

    @property
    def zip_url(self) -> str | None:
        rel = relative_output_path(self.output_dir) if self.output_dir else None
        return f"/output/zip/{rel}" if rel else None


@dataclass(frozen=True)
class TsaRunView:
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
    tags: tuple[str, ...] = ()

    @property
    def display_name(self) -> str:
        return f"{self.series_slug.upper()}_{'-'.join(self.models)}"

    @property
    def has_reporting(self) -> bool:
        return PROTECTED_TAG in self.tags

    @property
    def browse_url(self) -> str | None:
        return browse_url_for(self.output_dir)

    @property
    def zip_url(self) -> str | None:
        rel = relative_output_path(self.output_dir) if self.output_dir else None
        return f"/output/zip/{rel}" if rel else None


def _ts_to_meta(session, ts: TimeSeries, *, dates: list[date] | None = None) -> SeriesMeta:
    if dates is None:
        dates = available_dates_for_series(session, ts.id)
    freq_id, freq_label = detect_frequency_from_dates(dates) if dates else ("MS", "Monatlich")
    tags = tuple(list_tags(session, ENTITY_SERIES, ts.id))
    cat_name = ts.category.name if ts.category else None
    return SeriesMeta(
        slug=ts.slug,
        name=ts.name,
        label_de=ts.name,
        first_date=ts.first_date or date.today(),
        last_date=ts.last_date or date.today(),
        observation_count=ts.observation_count,
        frequency=freq_id,
        frequency_label=freq_label,
        source_file=ts.source_file,
        id=ts.id,
        tags=tags,
        category_id=ts.category_id,
        category_name=cat_name,
    )


def _mode_config_from_payload(payload: dict):
    analysis_mode = str(payload.get("analysis_mode", "thesis")).strip().lower()
    try:
        mode = AnalysisMode(analysis_mode)
    except ValueError as exc:
        raise ValueError("analysis_mode muss 'thesis' oder 'extended' sein.") from exc
    return analysis_mode, get_analysis_mode_config(mode)


def _parse_date_field(value: object, *, field: str) -> str | None:
    if value is None or value == "":
        return None
    text = str(value).strip()
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} muss YYYY-MM-DD sein.") from exc
    return text


def _validate_date_range(
    dates: list[str],
    start: str | None,
    end: str | None,
    *,
    start_label: str = "Von-Datum",
    end_label: str = "Bis-Datum",
    frequency: str = "D",
) -> tuple[str | None, str | None]:
    if dates:
        if start:
            start = snap_to_overlap_stamp_for_frequency(dates, start, frequency)
        if end:
            end = snap_to_overlap_stamp_for_frequency(dates, end, frequency)
    if start and end and start >= end:
        raise ValueError(f"{start_label} muss vor {end_label} liegen.")
    return start, end


def _overlap_observation_count(session, series_a_id: int, series_b_id: int, start: date, end: date) -> int:
    a_sub = (
        select(Observation.obs_date)
        .where(
            Observation.series_id == series_a_id,
            Observation.obs_date >= start,
            Observation.obs_date <= end,
        )
        .subquery()
    )
    b_sub = (
        select(Observation.obs_date)
        .where(
            Observation.series_id == series_b_id,
            Observation.obs_date >= start,
            Observation.obs_date <= end,
        )
        .subquery()
    )
    count = session.scalar(
        select(func.count()).select_from(
            a_sub.join(b_sub, a_sub.c.obs_date == b_sub.c.obs_date)
        )
    )
    return int(count or 0)


class WebBackend:
    """Liest Serien/Historie aus der DB; optional Mock-Fallback."""

    def __init__(self, *, use_mock: bool = False) -> None:
        self._force_mock = use_mock
        self._db_ok: bool | None = None if not use_mock else False

    def _probe_db(self) -> bool:
        if self._force_mock:
            return False
        if self._db_ok is True:
            return True
        # Bei Fehlschlag nicht dauerhaft cachen — DB kann spaeter hochfahren
        try:
            check_connection()
            from tslab.db.migrate import migrate_schema

            migrate_schema()
            self._db_ok = True
            return True
        except (DatabaseConnectionError, OSError):
            if self._try_sqlite_fallback():
                self._db_ok = True
                return True
            return False

    def _try_sqlite_fallback(self) -> bool:
        """PostgreSQL nicht erreichbar — vor Mock-Fallback lokale SQLite versuchen."""
        import os

        url = get_database_url()
        if url.startswith("sqlite"):
            return False
        sqlite_path = get_sqlite_file_path()
        if sqlite_path is None:
            from tslab.config_loader import project_root

            sqlite_path = (project_root() / "data" / "tslab.db").resolve()
        if not sqlite_path.is_file():
            return False
        os.environ["TSLAB_DATABASE_URL"] = f"sqlite:///{sqlite_path.as_posix()}"
        reset_engine_cache()
        try:
            check_connection()
            from tslab.db.migrate import migrate_schema

            migrate_schema()
            return True
        except (DatabaseConnectionError, OSError):
            return False

    @property
    def uses_mock(self) -> bool:
        return not self._probe_db()

    @property
    def mode_label(self) -> str:
        if self._force_mock:
            return "Mock-Daten (erzwungen)"
        if self.uses_mock:
            expected = get_database_display_name()
            return f"Mock-Daten ({expected} nicht erreichbar)"
        kind = get_database_kind()
        if kind == "sqlite":
            return "SQLite (lokale Datei)"
        return get_database_display_name()

    @property
    def database_url(self) -> str | None:
        if self.uses_mock:
            return None
        return get_database_url()

    @property
    def database_kind(self) -> str | None:
        if self.uses_mock:
            return None
        return get_database_kind()

    def list_series(
        self,
        *,
        tag: str | None = None,
        category_id: int | None = None,
        category_ids: list[int] | None = None,
        include_hidden: bool = False,
    ) -> list[SeriesMeta]:
        ids_filter = list(category_ids or [])
        if category_id is not None and not ids_filter:
            ids_filter = [category_id]
        if self.uses_mock:
            return mock.mock_list_series(tag=tag, category_ids=ids_filter or None)
        with get_session() as session:
            rows = list_series(session)
            if not include_hidden:
                rows = [ts for ts in rows if ts.hidden_at is None]
            if tag:
                ids = set(entity_ids_with_tag(session, ENTITY_SERIES, tag))
                rows = [ts for ts in rows if ts.id in ids]
            if ids_filter:
                id_set = set(ids_filter)
                rows = [ts for ts in rows if ts.category_id in id_set]
            return [_ts_to_meta(session, ts) for ts in rows]

    def list_used_categories(self) -> list[dict]:
        """Kategorien, die mindestens einer Zeitreihe zugeordnet sind."""
        used_ids = {
            s.category_id
            for s in self.list_series(include_hidden=True)
            if s.category_id is not None
        }
        return [c for c in self.list_categories() if c["id"] in used_ids]

    def series_by_slug(self, slug: str) -> SeriesMeta | None:
        if self.uses_mock:
            return mock.series_by_slug(slug)
        with get_session() as session:
            ts = get_series_by_slug(session, slug)
            return _ts_to_meta(session, ts) if ts else None

    def series_dates(self, slug: str) -> list[str]:
        with log_timing("series.dates", slug=slug):
            if self.uses_mock:
                s = mock.series_by_slug(slug)
                if s is None:
                    return []
                dates: list[date] = []
                d = s.first_date
                while d <= s.last_date:
                    dates.append(d)
                    if d.month == 12:
                        d = date(d.year + 1, 1, 1)
                    else:
                        d = date(d.year, d.month + 1, 1)
                return [x.isoformat() for x in dates]

            with get_session() as session:
                ts = get_series_by_slug(session, slug)
                if ts is None:
                    return []
                return [d.isoformat() for d in available_dates_for_series(session, ts.id)]

    def series_meta(self, slug: str) -> dict | None:
        """Leichtgewichtige Serie ohne Datumsliste."""
        s = self.series_by_slug(slug)
        if s is None:
            return None
        return mock.series_to_dict(s)

    def _overlap_context(
        self, slug_a: str, slug_b: str, *, frequency: str | None = None
    ) -> dict | None:
        with log_timing("overlap.context", a=slug_a, b=slug_b, frequency=frequency):
            if self.uses_mock:
                return mock.pair_overlap(slug_a, slug_b)

            with get_session() as session:
                ts_a = get_series_by_slug(session, slug_a)
                ts_b = get_series_by_slug(session, slug_b)
                if (
                    ts_a is None
                    or ts_b is None
                    or not ts_a.first_date
                    or not ts_b.first_date
                    or not ts_b.last_date
                ):
                    return None

                with log_timing("overlap.dates", a=slug_a, b=slug_b):
                    dates_a = available_dates_for_series(session, ts_a.id)
                    dates_b = available_dates_for_series(session, ts_b.id)
                ctx = compute_pair_overlap(
                    dates_a,
                    dates_b,
                    first_a=ts_a.first_date,
                    last_a=ts_a.last_date or ts_a.first_date,
                    count_a=ts_a.observation_count or len(dates_a),
                    first_b=ts_b.first_date,
                    last_b=ts_b.last_date or ts_b.first_date,
                    count_b=ts_b.observation_count or len(dates_b),
                    slug_a=slug_a,
                    slug_b=slug_b,
                    label_a=ts_a.name,
                    label_b=ts_b.name,
                    frequency=frequency,
                )
                if ctx is None:
                    return None

                a_dict = mock.series_to_dict(_ts_to_meta(session, ts_a, dates=dates_a))
                b_dict = mock.series_to_dict(_ts_to_meta(session, ts_b, dates=dates_b))
                return {
                    "series_a": a_dict,
                    "series_b": b_dict,
                    "suggested_run_name": suggest_run_name(slug_a, slug_b),
                    "frequencies": FREQUENCY_OPTIONS,
                    **ctx,
                }

    def overlap_dates(
        self, slug_a: str, slug_b: str, *, frequency: str | None = None
    ) -> list[str]:
        ctx = self._overlap_context(slug_a, slug_b, frequency=frequency)
        return ctx.get("dates", []) if ctx else []

    def pair_overlap(
        self, slug_a: str, slug_b: str, *, frequency: str | None = None
    ) -> dict | None:
        return self._overlap_context(slug_a, slug_b, frequency=frequency)

    def preview_upload(self, data: bytes, filename: str) -> dict:
        return preview_upload_bytes(data, filename)

    def validate_upload_dates(
        self,
        data: bytes,
        filename: str,
        *,
        date_column: str,
        date_parse_mode: str = "auto",
        date_format: str | None = None,
        dayfirst: bool | None = None,
    ) -> dict:
        df, _, _ = load_upload_dataframe(data, filename)
        return date_detection_for_column(
            df,
            date_column,
            mode=date_parse_mode,
            strftime_format=date_format or None,
            dayfirst=dayfirst,
        )

    def validate_upload_decimals(
        self,
        data: bytes,
        filename: str,
        *,
        value_column: str,
        decimal_mode: str = "auto",
    ) -> dict:
        df, _, _ = load_upload_dataframe(data, filename)
        return decimal_detection_for_column(df, value_column, mode=decimal_mode)

    def import_upload(
        self,
        data: bytes,
        filename: str,
        *,
        date_column: str,
        value_column: str,
        series_name: str | None = None,
        date_parse_mode: str = "auto",
        date_format: str | None = None,
        dayfirst: bool | None = None,
        sep: str = ";",
        encoding: str = "utf-8-sig",
        decimal_mode: str = "auto",
    ) -> dict:
        if self.uses_mock:
            return mock.mock_upload_result(filename)

        name = (series_name or value_column).strip()
        with get_session() as session:
            ts = import_series_from_upload(
                session,
                name=name,
                data=data,
                filename=filename,
                date_column=date_column,
                value_column=value_column,
                date_parse_mode=date_parse_mode,
                date_format=date_format or None,
                dayfirst=dayfirst,
                sep=sep,
                encoding=encoding,
                decimal_mode=decimal_mode,
            )
            meta = _ts_to_meta(session, ts)

        return {
            "ok": True,
            "message": f"Importiert: {meta.label_de} ({meta.observation_count} Werte)",
            "series": mock.series_to_dict(meta),
            "redirect_url": f"/series/{meta.slug}",
        }

    @property
    def ai_reports_enabled(self) -> bool:
        return ai_reports_available()

    def list_report_models(self) -> list[dict]:
        return list_report_models()

    def _want_ai_report(self, payload: dict) -> bool:
        model_id = str(payload.get("report_model") or "").strip()
        return bool(model_id) and model_id not in ("none", "off", "0")

    def _maybe_generate_ai_report(
        self, payload: dict, output_dir: str, *, run_type: str
    ) -> dict | None:
        if not self._want_ai_report(payload):
            return None
        model_id = str(payload.get("report_model") or "").strip() or None
        return generate_run_report(output_dir, model_id=model_id, run_type=run_type)

    def generate_output_report(
        self, output_dir: str, *, model_id: str | None = None, run_type: str = "Analyse"
    ) -> dict:
        return generate_run_report(output_dir, model_id=model_id, run_type=run_type)

    def _finalize_run(
        self,
        result: dict,
        *,
        collector: RunTelemetryCollector,
        output_dir: str,
        browse_url: str | None,
        ai_report: dict | None,
    ) -> dict:
        collector.set_output(output_dir, browse_url=browse_url)
        collector.set_langfuse_status(langfuse_status_from_config(load_report_config()))
        collector.merge_ai_report(ai_report)
        run_pdf = collector.write_pdf()
        result["run_report"] = run_pdf
        if run_pdf.get("ok") and run_pdf.get("url"):
            job = result.get("job") or {}
            job["run_report_url"] = run_pdf["url"]
            result["job"] = job
            result["message"] = str(result.get("message", "")) + f" · {run_pdf.get('message', 'Laufbericht')}"
        return result

    def list_categories(self) -> list[dict]:
        if self.uses_mock:
            return mock.mock_list_categories()
        with get_session() as session:
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "series_count": session.scalar(
                        select(func.count(TimeSeries.id)).where(TimeSeries.category_id == c.id)
                    )
                    or 0,
                }
                for c in list_categories(session)
            ]

    def create_category_entry(self, name: str) -> dict:
        clean = name.strip()
        if not clean:
            raise ValueError("Kategoriename fehlt.")
        if self.uses_mock:
            return mock.mock_create_category(clean)
        with get_session() as session:
            row = create_category(session, clean)
            return {"ok": True, "id": row.id, "name": row.name}

    def update_category_entry(self, category_id: int, name: str) -> dict:
        if self.uses_mock:
            return mock.mock_update_category(category_id, name)
        with get_session() as session:
            row = update_category(session, category_id, name)
            return {"ok": True, "id": row.id, "name": row.name}

    def delete_category_entry(self, category_id: int) -> dict:
        if self.uses_mock:
            return mock.mock_delete_category(category_id)
        with get_session() as session:
            delete_category(session, category_id)
            return {"ok": True}

    def update_series_meta(
        self, slug: str, *, name: str, category_id: int | None = None
    ) -> dict:
        clean = name.strip()
        if not clean:
            raise ValueError("Name darf nicht leer sein.")
        if self.uses_mock:
            return mock.mock_update_series_meta(slug, name=clean, category_id=category_id)
        with get_session() as session:
            ts = get_series_by_slug(session, slug)
            if ts is None:
                raise ValueError(f"Zeitreihe '{slug}' nicht gefunden.")
            if category_id is not None and get_category(session, category_id) is None:
                raise ValueError("Kategorie nicht gefunden.")
            ts.name = clean
            ts.category_id = category_id
            session.commit()
            session.refresh(ts)
            return {"ok": True, "series": mock.series_to_dict(_ts_to_meta(session, ts))}

    def list_correlation_history(
        self,
        *,
        tag: str | None = None,
        category_id: int | None = None,
        include_hidden: bool = False,
    ) -> list[CorrelationRunView]:
        if self.uses_mock:
            runs = [
                CorrelationRunView(
                    id=r.id,
                    series_a=r.series_a,
                    series_b=r.series_b,
                    start_date=r.start_date,
                    end_date=r.end_date,
                    analysis_mode=r.analysis_mode,
                    max_lag=r.max_lag,
                    best_lag=r.best_lag,
                    best_r=r.best_r,
                    created_at=r.created_at,
                    output_dir=r.output_dir,
                    run_name=suggest_run_name(r.series_a, r.series_b),
                )
                for r in mock.MOCK_CORRELATION_HISTORY
            ]
            if tag:
                runs = [r for r in runs if tag in r.tags]
            return runs

        with get_session() as session:
            q = select(CorrelationHistory).order_by(CorrelationHistory.created_at.desc())
            rows = list(session.scalars(q).all())
            if not include_hidden:
                rows = [r for r in rows if r.hidden_at is None]
            views: list[CorrelationRunView] = []
            for r in rows:
                tags = tuple(list_tags(session, ENTITY_CORRELATION, r.id))
                if tag and tag not in tags:
                    continue
                if category_id is not None:
                    ts_a = get_series_by_slug(session, r.series_a_slug)
                    if ts_a is None or ts_a.category_id != category_id:
                        continue
                views.append(
                    CorrelationRunView(
                        id=r.id,
                        series_a=r.series_a_slug,
                        series_b=r.series_b_slug,
                        start_date=r.start_date or date.today(),
                        end_date=r.end_date or date.today(),
                        analysis_mode=r.analysis_mode,
                        max_lag=r.max_lag,
                        best_lag=r.best_lag,
                        best_r=r.best_correlation,
                        created_at=r.created_at,
                        output_dir=r.output_dir,
                        run_name=r.run_name or suggest_run_name(r.series_a_slug, r.series_b_slug),
                        tags=tags,
                    )
                )
            return views

    def list_tsa_history(
        self,
        *,
        tag: str | None = None,
        category_id: int | None = None,
        include_hidden: bool = False,
    ) -> list[TsaRunView]:
        if self.uses_mock:
            views = [
                TsaRunView(
                    id=r.id,
                    series_slug=r.series_slug,
                    models=list(r.models),
                    analysis_mode=r.analysis_mode,
                    train_start=r.train_start,
                    train_end=r.train_end,
                    forecast_end=r.forecast_end,
                    status=r.status,
                    created_at=r.created_at,
                    output_dir=r.output_dir,
                )
                for r in mock.MOCK_TSA_HISTORY
            ]
            if tag:
                views = [v for v in views if tag in v.tags]
            return views

        with get_session() as session:
            rows = list(
                session.scalars(
                    select(TsaHistory).order_by(TsaHistory.created_at.desc())
                ).all()
            )
            if not include_hidden:
                rows = [r for r in rows if r.hidden_at is None]
            views: list[TsaRunView] = []
            for r in rows:
                tags = tuple(list_tags(session, ENTITY_TSA, r.id))
                if tag and tag not in tags:
                    continue
                if category_id is not None:
                    ts = get_series_by_slug(session, r.series_slug)
                    if ts is None or ts.category_id != category_id:
                        continue
                try:
                    models = json.loads(r.models)
                except json.JSONDecodeError:
                    models = ["arma-garch"]
                views.append(
                    TsaRunView(
                        id=r.id,
                        series_slug=r.series_slug,
                        models=models if isinstance(models, list) else [str(models)],
                        analysis_mode=r.analysis_mode,
                        train_start=r.train_start or date.today(),
                        train_end=r.train_end or date.today(),
                        forecast_end=r.forecast_end or date.today(),
                        status=r.status,
                        created_at=r.created_at,
                        output_dir=r.output_dir,
                        tags=tags,
                    )
                )
            if views:
                return views

        views = []
        for r in mock.MOCK_TSA_HISTORY:
            views.append(
                TsaRunView(
                    id=r.id,
                    series_slug=r.series_slug,
                    models=list(r.models),
                    analysis_mode=r.analysis_mode,
                    train_start=r.train_start,
                    train_end=r.train_end,
                    forecast_end=r.forecast_end,
                    status=r.status,
                    created_at=r.created_at,
                    output_dir=r.output_dir,
                )
            )
        return views

    def _load_series_pandas(self, slug: str):
        if self.uses_mock:
            return mock.mock_series_pandas(slug)
        with get_session() as session:
            return load_series_full_pandas(session, slug)

    def series_chart_data(
        self,
        slug: str,
        *,
        start: str | None = None,
        end: str | None = None,
        include_returns: bool = False,
        analysis_mode: str | None = None,
    ) -> dict:
        meta = self.series_by_slug(slug)
        if meta is None:
            raise ValueError(f"Zeitreihe '{slug}' wurde nicht gefunden.")
        series = self._load_series_pandas(slug)
        if start or end:
            dates = self.series_dates(slug)
            _validate_date_range(dates, start, end)
        return build_series_chart_payload(
            series,
            slug=slug,
            label=meta.label_de,
            start=start,
            end=end,
            include_returns=include_returns,
            analysis_mode=analysis_mode,
        )

    def correlation_preview(
        self,
        slug_a: str,
        slug_b: str,
        *,
        start: str | None = None,
        end: str | None = None,
        include_returns: bool = False,
        analysis_mode: str | None = None,
        frequency: str | None = None,
    ) -> dict:
        if not slug_a or not slug_b or slug_a == slug_b:
            raise ValueError("Bitte zwei verschiedene Zeitreihen waehlen.")
        meta_a = self.series_by_slug(slug_a)
        meta_b = self.series_by_slug(slug_b)
        if meta_a is None or meta_b is None:
            raise ValueError("Eine oder beide Zeitreihen wurden nicht gefunden.")

        ctx = self._overlap_context(slug_a, slug_b, frequency=frequency)
        if not ctx or not ctx.get("dates"):
            raise ValueError("Keine gemeinsame Datenbasis fuer diese Paarung.")

        overlap_dates = ctx["dates"]
        eff_freq = ctx.get("suggested_frequency", "MS")

        eff_start = start or overlap_dates[0]
        eff_end = end or overlap_dates[-1]
        eff_start, eff_end = _validate_date_range(
            overlap_dates, eff_start, eff_end, frequency=eff_freq
        )

        series_a = self._load_series_pandas(slug_a)
        series_b = self._load_series_pandas(slug_b)
        return build_pair_chart_payload(
            series_a,
            series_b,
            slug_a=slug_a,
            slug_b=slug_b,
            label_a=meta_a.label_de,
            label_b=meta_b.label_de,
            start=eff_start,
            end=eff_end,
            include_returns=include_returns,
            analysis_mode=analysis_mode,
            frequency=eff_freq,
        )

    def run_correlation(self, payload: dict) -> dict:
        if self.uses_mock:
            return {
                "ok": True,
                "status": "simulated",
                "message": "Korrelation simuliert (Mock-Modus)",
                "job": {
                    **payload,
                    "started_at": datetime.now().isoformat(),
                    "output_preview": "output/correlation_thesis_.../",
                },
            }

        series_a = str(payload.get("series_a", "")).strip()
        series_b = str(payload.get("series_b", "")).strip()
        if not series_a or not series_b:
            raise ValueError("series_a und series_b sind erforderlich.")
        if series_a == series_b:
            raise ValueError("Bitte zwei verschiedene Zeitreihen waehlen.")

        analysis_mode, mode_config = _mode_config_from_payload(payload)
        start_date = _parse_date_field(payload.get("start_date"), field="start_date")
        end_date = _parse_date_field(payload.get("end_date"), field="end_date")
        frequency = str(payload.get("frequency") or "").strip() or None
        if frequency not in ("D", "W", "MS", "Y"):
            frequency = None

        try:
            max_lag = int(payload.get("max_lag", 24))
        except (TypeError, ValueError) as exc:
            raise ValueError("max_lag muss eine ganze Zahl sein.") from exc
        if max_lag < 1:
            raise ValueError("max_lag muss mindestens 1 sein.")

        collector = RunTelemetryCollector(run_type="Korrelation")
        with collector.track("correlation_job"):
            with get_session() as session:
                ts_a = get_series_by_slug(session, series_a)
                ts_b = get_series_by_slug(session, series_b)
                if ts_a is None or ts_b is None:
                    raise ValueError("Eine oder beide Zeitreihen wurden nicht gefunden.")

                ctx = self._overlap_context(series_a, series_b, frequency=frequency)
                if not ctx or not ctx.get("dates"):
                    raise ValueError("Keine gemeinsame Datenbasis fuer diese Paarung.")

                overlap_dates = ctx["dates"]
                eff_freq = ctx.get("suggested_frequency", "MS")
                start_date, end_date = _validate_date_range(
                    overlap_dates, start_date, end_date, frequency=eff_freq
                )

                eff_start, eff_end = resolve_study_dates_for_mode(
                    mode_config, start_date=start_date, end_date=end_date
                )

                full_a = load_series_full_pandas(session, series_a)
                full_b = load_series_full_pandas(session, series_b)
                resolve_correlation_study_dates(
                    full_a,
                    full_b,
                    start_date=eff_start,
                    end_date=eff_end,
                    frequency=eff_freq,
                )

                job = run_correlation_job(
                    session,
                    series_a,
                    series_b,
                    mode_config=mode_config,
                    start_date=eff_start,
                    end_date=eff_end,
                    max_lag=max_lag,
                    frequency=eff_freq,
                    run_name=str(payload.get("run_name") or suggest_run_name(series_a, series_b)),
                )

        out = str(job.output_dir)
        run_name = str(payload.get("run_name") or suggest_run_name(series_a, series_b))
        browse = browse_url_for(out)
        msg = f"Korrelation fertig: {run_name}"
        if job.best_lag is not None and job.best_r is not None:
            msg += f" (bestes |r|={abs(job.best_r):.3f} bei Lag {job.best_lag})"

        result = {
            "ok": True,
            "status": "done",
            "message": msg,
            "job": {
                "run_name": run_name,
                "series_a": series_a,
                "series_b": series_b,
                "analysis_mode": analysis_mode,
                "start_date": eff_start,
                "end_date": eff_end,
                "max_lag": max_lag,
                "best_lag": job.best_lag,
                "best_r": job.best_r,
                "output_dir": out,
                "output_preview": out,
                "browse_url": browse,
                "history_id": job.history_id,
                "started_at": datetime.now().isoformat(),
            },
        }
        report = None
        if self._want_ai_report(payload):
            with collector.track("ai_report", model=payload.get("report_model")):
                report = self._maybe_generate_ai_report(payload, out, run_type="Korrelation")
        if report:
            result["report"] = report
            if report.get("ok"):
                result["message"] += f" · {report.get('message', 'KI-Bericht')}"
                if report.get("ai_errors"):
                    result["message"] += f" ⚠ {len(report['ai_errors'])} KI-Fehler"
        return self._finalize_run(
            result,
            collector=collector,
            output_dir=out,
            browse_url=browse,
            ai_report=report,
        )

    def run_tsa(self, payload: dict) -> dict:
        if self.uses_mock:
            return {
                "ok": True,
                "status": "simulated",
                "message": "TSA simuliert (Mock-Modus)",
                "job": {
                    **payload,
                    "started_at": datetime.now().isoformat(),
                    "output_preview": "output/tsa_thesis_1987-12-01_to_2006-07-01/",
                },
            }

        series_slug = str(payload.get("series_slug", "")).strip()
        if not series_slug:
            raise ValueError("series_slug ist erforderlich.")
        if self.series_by_slug(series_slug) is None:
            raise ValueError(f"Zeitreihe '{series_slug}' wurde nicht gefunden.")

        analysis_mode, mode_config = _mode_config_from_payload(payload)

        train_start = _parse_date_field(
            payload.get("train_start"), field="train_start"
        )
        train_end = _parse_date_field(payload.get("train_end"), field="train_end")
        forecast_end = _parse_date_field(
            payload.get("forecast_end"), field="forecast_end"
        )

        series_dates = self.series_dates(series_slug)
        train_start, train_end = _validate_date_range(
            series_dates,
            train_start,
            train_end,
            start_label="Training Von-Datum",
            end_label="Training Bis-Datum",
        )

        raw_models = payload.get("models")
        if isinstance(raw_models, str):
            models = [m.strip() for m in raw_models.split(",") if m.strip()]
        elif isinstance(raw_models, list):
            models = [str(m).strip() for m in raw_models if str(m).strip()]
        else:
            models = []
        if not models:
            raise ValueError("Bitte mindestens ein Modell waehlen.")

        try:
            plot_window = forecast_plot_window_from_payload(payload)
        except (TypeError, ValueError) as exc:
            raise ValueError("Prognose-Grafikfenster: ungueltige Jahreswerte.") from exc

        collector = RunTelemetryCollector(run_type="TSA")
        with collector.track("tsa_job", models=",".join(models)):
            with get_session() as session:
                job = run_tsa_job(
                    session,
                    mode_config,
                    series_slug=series_slug,
                    start_date=train_start,
                    end_date=train_end,
                    forecast_end=forecast_end,
                    models=models,
                    plot_window=plot_window,
                    order_mode=str(payload.get("order_mode") or "auto"),
                    arma_user_orders=parse_order_list(payload.get("arma_order")),
                    garch_user_orders=parse_order_list(payload.get("garch_order")),
                )

        out = str(job.output_dir)
        browse = browse_url_for(out)
        model_label = ", ".join(job.models_run)
        msg = f"TSA fertig: {series_slug.upper()} ({model_label})"

        result = {
            "ok": True,
            "status": "done",
            "message": msg,
            "job": {
                "series_slug": series_slug,
                "models": job.models_run,
                "analysis_mode": analysis_mode,
                "train_start": train_start,
                "train_end": train_end,
                "forecast_end": forecast_end,
                "output_dir": out,
                "output_preview": out,
                "browse_url": browse,
                "history_id": job.history_id,
                "started_at": datetime.now().isoformat(),
            },
        }
        report = None
        if self._want_ai_report(payload):
            with collector.track("ai_report", model=payload.get("report_model")):
                report = self._maybe_generate_ai_report(payload, out, run_type="TSA")
        if report:
            result["report"] = report
            if report.get("ok"):
                result["message"] += f" · {report.get('message', 'KI-Bericht')}"
                if report.get("ai_errors"):
                    result["message"] += f" ⚠ {len(report['ai_errors'])} KI-Fehler"
        return self._finalize_run(
            result,
            collector=collector,
            output_dir=out,
            browse_url=browse,
            ai_report=report,
        )

    def tsa_window_preview(self, params: dict) -> dict:
        if self.uses_mock:
            slug = str(params.get("series_slug", "pdax"))
            series = self._load_series_pandas(slug)
            dates = [d.date().isoformat() for d in series.index]
            values = [round(float(v), 6) for v in series.values]
            return {
                "slug": slug,
                "dates": dates,
                "values": values,
                "regions": [],
                "plot_region": None,
                "observation_count": len(dates),
            }
        analysis_mode, mode_config = _mode_config_from_payload(params)
        with get_session() as session:
            return build_tsa_window_preview(
                session,
                mode_config=mode_config,
                series_slug=str(params.get("series_slug", "")).strip(),
                start_date=params.get("train_start"),
                end_date=params.get("train_end"),
                forecast_end=params.get("forecast_end"),
                plot_pre_years=float(params["plot_pre_years"]) if params.get("plot_pre_years") not in (None, "") else None,
                plot_forecast_years=float(params["plot_forecast_years"]) if params.get("plot_forecast_years") not in (None, "") else None,
                plot_post_years=float(params["plot_post_years"]) if params.get("plot_post_years") not in (None, "") else None,
            )

    def _delete_preview_to_dict(self, p: DeletePreview) -> dict:
        return {
            "entity_type": p.entity_type,
            "entity_id": p.entity_id,
            "label": p.label,
            "tags": p.tags,
            "actions": p.actions,
            "warnings": p.warnings,
            "blocked": p.blocked,
            "block_reason": p.block_reason,
        }

    def delete_preview(self, payload: dict) -> dict:
        entity_type = str(payload.get("entity_type", "")).strip()
        scope = str(payload.get("scope", "both")).strip()
        if scope not in ("ui", "storage", "both"):
            raise ValueError("scope muss ui, storage oder both sein.")
        with get_session() as session:
            if entity_type == ENTITY_SERIES:
                preview = preview_delete_series(session, str(payload.get("slug", "")), scope)  # type: ignore[arg-type]
            elif entity_type == ENTITY_CORRELATION:
                preview = preview_delete_correlation(session, int(payload.get("id")), scope)  # type: ignore[arg-type]
            elif entity_type == ENTITY_TSA:
                preview = preview_delete_tsa(session, int(payload.get("id")), scope)  # type: ignore[arg-type]
            else:
                raise ValueError("Unbekannter entity_type.")
        return {"ok": True, "preview": self._delete_preview_to_dict(preview)}

    def delete_confirm(self, payload: dict) -> dict:
        entity_type = str(payload.get("entity_type", "")).strip()
        scope = str(payload.get("scope", "both")).strip()
        if scope not in ("ui", "storage", "both"):
            raise ValueError("scope muss ui, storage oder both sein.")
        with get_session() as session:
            if entity_type == ENTITY_SERIES:
                delete_series(session, str(payload.get("slug", "")), scope)  # type: ignore[arg-type]
            elif entity_type == ENTITY_CORRELATION:
                delete_correlation(session, int(payload.get("id")), scope)  # type: ignore[arg-type]
            elif entity_type == ENTITY_TSA:
                delete_tsa(session, int(payload.get("id")), scope)  # type: ignore[arg-type]
            else:
                raise ValueError("Unbekannter entity_type.")
        return {"ok": True, "message": "Erfolgreich geloescht."}

    def update_tags(self, payload: dict) -> dict:
        entity_type = str(payload.get("entity_type", "")).strip()
        entity_id = payload.get("entity_id")
        tags = payload.get("tags") or []
        if not isinstance(tags, list):
            raise ValueError("tags muss eine Liste sein.")
        if self.uses_mock:
            return {"ok": True, "tags": tags}
        with get_session() as session:
            if entity_type == ENTITY_SERIES:
                ts = get_series_by_slug(session, str(entity_id))
                if ts is None:
                    raise LookupError("Zeitreihe nicht gefunden.")
                eid = ts.id
            else:
                eid = int(entity_id)
            clean = set_tags(session, entity_type, eid, [str(t) for t in tags])
        return {"ok": True, "tags": clean}

    def tag_suggestions(self, prefix: str = "") -> list[str]:
        if self.uses_mock:
            return [PROTECTED_TAG, "_Delete_20260715"]
        with get_session() as session:
            return suggest_tags(session, prefix=prefix)
