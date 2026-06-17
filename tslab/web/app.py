"""Flask-App: Dashboard-Oberflaeche (UI + DB/Mock-API)."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, request

from tslab.web import mock_data as mock
from tslab.web.backend import WebBackend
from tslab.web.output_browser import list_directory, resolve_output_path, serve_output_file

_WEB_ROOT = Path(__file__).resolve().parent


def create_app(*, use_mock: bool = False) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(_WEB_ROOT / "templates"),
        static_folder=str(_WEB_ROOT / "static"),
    )
    app.config["SECRET_KEY"] = "tslab-dev-ui-only"
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

    backend = WebBackend(use_mock=use_mock)
    app.extensions["tslab_backend"] = backend

    @app.context_processor
    def inject_backend():
        return {
            "backend_mode": backend.mode_label,
            "uses_mock": backend.uses_mock,
        }

    def _series_dicts():
        return [mock.series_to_dict(s) for s in backend.list_series()]

    @app.get("/")
    def dashboard():
        return render_template(
            "dashboard.html",
            page="dashboard",
            series=backend.list_series(),
            corr_count=len(backend.list_correlation_history()),
            tsa_count=len(backend.list_tsa_history()),
        )

    @app.get("/upload")
    def upload_page():
        return render_template("upload.html", page="upload")

    @app.get("/series")
    def series_page():
        return render_template(
            "series.html",
            page="series",
            series=backend.list_series(),
        )

    @app.get("/series/<slug>")
    def series_detail_page(slug: str):
        s = backend.series_by_slug(slug)
        if s is None:
            return render_template("404.html", page="series", message="Zeitreihe nicht gefunden"), 404
        return render_template(
            "series_detail.html",
            page="series",
            series=s,
        )

    @app.get("/correlation")
    def correlation_page():
        return render_template(
            "correlation.html",
            page="correlation",
            series=backend.list_series(),
        )

    @app.get("/correlation/history")
    def correlation_history_page():
        return render_template(
            "correlation_history.html",
            page="correlation_history",
            runs=backend.list_correlation_history(),
        )

    @app.get("/tsa")
    def tsa_page():
        return render_template(
            "tsa.html",
            page="tsa",
            series=backend.list_series(),
            models=mock.TSA_MODELS,
        )

    @app.get("/tsa/history")
    def tsa_history_page():
        return render_template(
            "tsa_history.html",
            page="tsa_history",
            runs=backend.list_tsa_history(),
            series=backend.list_series(),
        )

    @app.get("/output/browse/")
    @app.get("/output/browse/<path:subpath>")
    def output_browse(subpath: str = ""):
        listing = list_directory(subpath)
        return render_template(
            "output_browse.html",
            page="output",
            listing=listing,
        )

    @app.get("/output/file/<path:subpath>")
    def output_file(subpath: str):
        return serve_output_file(subpath)

    @app.get("/api/series")
    def api_series():
        return jsonify(_series_dicts())

    @app.get("/api/series/<slug>")
    def api_series_detail(slug: str):
        s = backend.series_by_slug(slug)
        if s is None:
            return jsonify({"error": "Serie nicht gefunden"}), 404
        data = mock.series_to_dict(s)
        data["dates"] = backend.series_dates(slug)
        return jsonify(data)

    @app.get("/api/series/<slug>/dates")
    def api_series_dates(slug: str):
        return jsonify({"slug": slug, "dates": backend.series_dates(slug)})

    @app.get("/api/series/<slug>/chart")
    def api_series_chart(slug: str):
        try:
            include_returns = request.args.get("show_returns", "0") in ("1", "true", "yes")
            data = backend.series_chart_data(
                slug,
                start=request.args.get("start") or None,
                end=request.args.get("end") or None,
                include_returns=include_returns,
                analysis_mode=request.args.get("analysis_mode") or None,
            )
            return jsonify(data)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/correlation/preview")
    def api_correlation_preview():
        try:
            include_returns = request.args.get("show_returns", "0") in ("1", "true", "yes")
            data = backend.correlation_preview(
                request.args.get("a", ""),
                request.args.get("b", ""),
                start=request.args.get("start") or None,
                end=request.args.get("end") or None,
                include_returns=include_returns,
                analysis_mode=request.args.get("analysis_mode") or None,
            )
            return jsonify(data)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/overlap")
    def api_overlap():
        slug_a = request.args.get("a", "")
        slug_b = request.args.get("b", "")
        data = backend.pair_overlap(slug_a, slug_b)
        if data is None:
            return jsonify({"error": "Keine Ueberlappung oder ungueltige Serie"}), 400
        return jsonify(data)

    @app.get("/api/correlation/history")
    def api_correlation_history():
        rows = []
        for r in backend.list_correlation_history():
            rows.append(
                {
                    "id": r.id,
                    "run_name": r.display_name,
                    "series_a": r.series_a,
                    "series_b": r.series_b,
                    "start_date": r.start_date.isoformat(),
                    "end_date": r.end_date.isoformat(),
                    "analysis_mode": r.analysis_mode,
                    "max_lag": r.max_lag,
                    "best_lag": r.best_lag,
                    "best_r": r.best_r,
                    "created_at": r.created_at.isoformat(),
                    "output_dir": r.output_dir,
                    "browse_url": r.browse_url,
                }
            )
        return jsonify(rows)

    @app.get("/api/tsa/models")
    def api_tsa_models():
        return jsonify(mock.TSA_MODELS)

    @app.get("/api/tsa/history")
    def api_tsa_history():
        rows = []
        for r in backend.list_tsa_history():
            rows.append(
                {
                    "id": r.id,
                    "display_name": r.display_name,
                    "series_slug": r.series_slug,
                    "models": r.models,
                    "analysis_mode": r.analysis_mode,
                    "train_start": r.train_start.isoformat(),
                    "train_end": r.train_end.isoformat(),
                    "forecast_end": r.forecast_end.isoformat(),
                    "status": r.status,
                    "created_at": r.created_at.isoformat(),
                    "output_dir": r.output_dir,
                    "browse_url": r.browse_url,
                }
            )
        return jsonify(rows)

    @app.post("/api/upload/preview")
    def api_upload_preview():
        f = request.files.get("file")
        if f is None or not f.filename:
            return jsonify({"ok": False, "message": "Keine Datei gewaehlt"}), 400
        try:
            preview = backend.preview_upload(f.read(), f.filename)
            return jsonify({"ok": True, **preview})
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/upload")
    def api_upload():
        f = request.files.get("file")
        if f is None or not f.filename:
            return jsonify({"ok": False, "message": "Keine Datei gewaehlt"}), 400
        try:
            result = backend.import_upload(
                f.read(),
                f.filename,
                date_column=request.form.get("date_column", ""),
                value_column=request.form.get("value_column", ""),
                series_name=request.form.get("series_name") or None,
                date_format=request.form.get("date_format", "%d.%m.%Y"),
                sep=request.form.get("sep", ";"),
            )
            return jsonify(result)
        except (ValueError, KeyError) as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/correlation/run")
    def api_correlation_run():
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(backend.run_correlation(body))
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 500

    @app.post("/api/tsa/run")
    def api_tsa_run():
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(backend.run_tsa(body))
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 500

    return app
