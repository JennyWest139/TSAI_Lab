"""Web-Backend: DB-Services mit Mock-Fallback."""

from __future__ import annotations

import tempfile
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
)
from tslab.db.models import CorrelationHistory, Observation, TimeSeries
from tslab.services.analysis_mode import (
    AnalysisMode,
    get_analysis_mode_config,
    resolve_study_dates_for_mode,
)
from tslab.services.correlation import resolve_correlation_study_dates
from tslab.services.correlation_job import run_correlation_job
from tslab.services.tsa_job import forecast_plot_window_from_payload, run_tsa_job
from tslab.services.frequency_detect import detect_frequency_from_dates
from tslab.services.timeseries_store import (
    available_dates_for_series,
    get_series_by_slug,
    import_series_from_csv,
    list_series,
)
from tslab.web import mock_data as mock
from tslab.web.csv_preview import preview_upload_bytes
from tslab.web.mock_data import FREQUENCY_OPTIONS, SeriesMeta, suggest_run_name
from tslab.web.output_browser import browse_url_for, output_root, relative_output_path


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

    @property
    def display_name(self) -> str:
        return self.run_name or suggest_run_name(self.series_a, self.series_b)

    @property
    def browse_url(self) -> str | None:
        return browse_url_for(self.output_dir)


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

    @property
    def display_name(self) -> str:
        return f"{self.series_slug.upper()}_{'-'.join(self.models)}"

    @property
    def browse_url(self) -> str | None:
        return browse_url_for(self.output_dir)


def _ts_to_meta(session, ts: TimeSeries) -> SeriesMeta:
    dates = available_dates_for_series(session, ts.id)
    freq_id, freq_label = detect_frequency_from_dates(dates) if dates else ("MS", "Monatlich")
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
) -> tuple[str | None, str | None]:
    if start and start not in dates:
        raise ValueError(f"{start_label} ist kein gueltiger Zeitstempel der Zeitreihe.")
    if end and end not in dates:
        raise ValueError(f"{end_label} ist kein gueltiger Zeitstempel der Zeitreihe.")
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
        if self._db_ok is not None:
            return self._db_ok
        try:
            check_connection()
            self._db_ok = True
        except (DatabaseConnectionError, OSError):
            self._db_ok = False
        return self._db_ok

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

    def list_series(self) -> list[SeriesMeta]:
        if self.uses_mock:
            return list(mock.MOCK_SERIES)
        with get_session() as session:
            return [_ts_to_meta(session, ts) for ts in list_series(session)]

    def series_by_slug(self, slug: str) -> SeriesMeta | None:
        if self.uses_mock:
            return mock.series_by_slug(slug)
        with get_session() as session:
            ts = get_series_by_slug(session, slug)
            return _ts_to_meta(session, ts) if ts else None

    def series_dates(self, slug: str) -> list[str]:
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

    def overlap_dates(self, slug_a: str, slug_b: str) -> list[str]:
        if self.uses_mock:
            data = mock.pair_overlap(slug_a, slug_b)
            if data is None:
                return []
            return data.get("dates", [])

        with get_session() as session:
            ts_a = get_series_by_slug(session, slug_a)
            ts_b = get_series_by_slug(session, slug_b)
            if ts_a is None or ts_b is None:
                return []
            a_dates = set(available_dates_for_series(session, ts_a.id))
            b_dates = set(available_dates_for_series(session, ts_b.id))
            return sorted(d.isoformat() for d in a_dates & b_dates)

    def preview_upload(self, data: bytes, filename: str) -> dict:
        return preview_upload_bytes(data, filename)

    def import_upload(
        self,
        data: bytes,
        filename: str,
        *,
        date_column: str,
        value_column: str,
        series_name: str | None = None,
        date_format: str = "%d.%m.%Y",
        sep: str = ";",
    ) -> dict:
        if self.uses_mock:
            return mock.mock_upload_result(filename)

        suffix = Path(filename).suffix or ".csv"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        name = (series_name or value_column).strip()
        try:
            with get_session() as session:
                ts = import_series_from_csv(
                    session,
                    name=name,
                    csv_path=tmp_path,
                    date_column=date_column,
                    value_column=value_column,
                    date_format=date_format,
                    sep=sep,
                )
                meta = _ts_to_meta(session, ts)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return {
            "ok": True,
            "message": f"Importiert: {meta.label_de} ({meta.observation_count} Werte)",
            "series": mock.series_to_dict(meta),
        }

    def pair_overlap(self, slug_a: str, slug_b: str) -> dict | None:
        if self.uses_mock:
            return mock.pair_overlap(slug_a, slug_b)

        with get_session() as session:
            ts_a = get_series_by_slug(session, slug_a)
            ts_b = get_series_by_slug(session, slug_b)
            if ts_a is None or ts_b is None or not ts_a.first_date or not ts_b.first_date:
                return None

            overlap_start = max(ts_a.first_date, ts_b.first_date)
            overlap_end = min(ts_a.last_date or overlap_start, ts_b.last_date or overlap_start)
            if overlap_start > overlap_end:
                return None

            overlap_n = _overlap_observation_count(
                session, ts_a.id, ts_b.id, overlap_start, overlap_end
            )
            overlap_date_list = self.overlap_dates(slug_a, slug_b)
            freq_id, freq_label = detect_frequency_from_dates(
                [date.fromisoformat(d) for d in overlap_date_list]
            ) if overlap_date_list else ("MS", "Monatlich")
            a_dict = mock.series_to_dict(_ts_to_meta(session, ts_a))
            b_dict = mock.series_to_dict(_ts_to_meta(session, ts_b))
            return {
                "series_a": a_dict,
                "series_b": b_dict,
                "overlap_start": overlap_start.isoformat(),
                "overlap_end": overlap_end.isoformat(),
                "suggested_start": overlap_start.isoformat(),
                "suggested_end": overlap_end.isoformat(),
                "overlap_observations": overlap_n,
                "suggested_frequency": freq_id,
                "suggested_frequency_label": freq_label,
                "suggested_run_name": suggest_run_name(slug_a, slug_b),
                "dates": overlap_date_list,
                "frequencies": FREQUENCY_OPTIONS,
            }

    def list_correlation_history(self) -> list[CorrelationRunView]:
        if self.uses_mock:
            return [
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

        with get_session() as session:
            rows = session.scalars(
                select(CorrelationHistory).order_by(CorrelationHistory.created_at.desc())
            ).all()
            return [
                CorrelationRunView(
                    id=r.id,
                    series_a=r.series_a_slug,
                    series_b=r.series_b_slug,
                    start_date=r.start_date or date.today(),
                    end_date=r.end_date or date.today(),
                    analysis_mode=None,
                    max_lag=r.max_lag,
                    best_lag=r.best_lag,
                    best_r=r.best_correlation,
                    created_at=r.created_at,
                    output_dir=r.output_dir,
                    run_name=suggest_run_name(r.series_a_slug, r.series_b_slug),
                )
                for r in rows
            ]

    def list_tsa_history(self) -> list[TsaRunView]:
        views: list[TsaRunView] = []
        if self.uses_mock:
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

        root = output_root()
        idx = 0
        for path in sorted(root.glob("tsa_*"), reverse=True):
            if not path.is_dir():
                continue
            idx += 1
            rel = relative_output_path(path) or path.name
            views.append(
                TsaRunView(
                    id=idx,
                    series_slug="pdax",
                    models=["arma-garch"],
                    analysis_mode="thesis",
                    train_start=date(1987, 12, 1),
                    train_end=date(2006, 7, 1),
                    forecast_end=date(2008, 7, 1),
                    status="fertig",
                    created_at=datetime.fromtimestamp(path.stat().st_mtime),
                    output_dir=str(path),
                )
            )
        if views:
            return views
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

        try:
            max_lag = int(payload.get("max_lag", 24))
        except (TypeError, ValueError) as exc:
            raise ValueError("max_lag muss eine ganze Zahl sein.") from exc
        if max_lag < 1:
            raise ValueError("max_lag muss mindestens 1 sein.")

        eff_start, eff_end = resolve_study_dates_for_mode(
            mode_config, start_date=start_date, end_date=end_date
        )

        with get_session() as session:
            # Fenster gegen echte Ueberlappung pruefen
            ts_a = get_series_by_slug(session, series_a)
            ts_b = get_series_by_slug(session, series_b)
            if ts_a is None or ts_b is None:
                raise ValueError("Eine oder beide Zeitreihen wurden nicht gefunden.")

            from tslab.services.timeseries_store import load_series_full_pandas

            overlap_dates = self.overlap_dates(series_a, series_b)
            _validate_date_range(overlap_dates, start_date, end_date)

            full_a = load_series_full_pandas(session, series_a)
            full_b = load_series_full_pandas(session, series_b)
            resolve_correlation_study_dates(
                full_a, full_b, start_date=eff_start, end_date=eff_end
            )

            job = run_correlation_job(
                session,
                series_a,
                series_b,
                mode_config=mode_config,
                start_date=eff_start,
                end_date=eff_end,
                max_lag=max_lag,
            )

        out = str(job.output_dir)
        run_name = str(payload.get("run_name") or suggest_run_name(series_a, series_b))
        browse = browse_url_for(out)
        msg = f"Korrelation fertig: {run_name}"
        if job.best_lag is not None and job.best_r is not None:
            msg += f" (bestes |r|={abs(job.best_r):.3f} bei Lag {job.best_lag})"

        return {
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
            )

        out = str(job.output_dir)
        browse = browse_url_for(out)
        model_label = ", ".join(job.models_run)
        msg = f"TSA fertig: {series_slug.upper()} ({model_label})"

        return {
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
                "study_label": job.context.study.analysis_label,
                "started_at": datetime.now().isoformat(),
            },
        }
