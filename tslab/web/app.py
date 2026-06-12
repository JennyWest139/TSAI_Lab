"""Flask-App: Dashboard-Oberflaeche (UI + Mock-API)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from tslab.web import mock_data as mock

_WEB_ROOT = Path(__file__).resolve().parent


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(_WEB_ROOT / "templates"),
        static_folder=str(_WEB_ROOT / "static"),
    )
    app.config["SECRET_KEY"] = "tslab-dev-ui-only"

    @app.get("/")
    def dashboard():
        return render_template(
            "dashboard.html",
            page="dashboard",
            series=mock.MOCK_SERIES,
            corr_count=len(mock.MOCK_CORRELATION_HISTORY),
            tsa_count=len(mock.MOCK_TSA_HISTORY),
        )

    @app.get("/upload")
    def upload_page():
        return render_template("upload.html", page="upload")

    @app.get("/series")
    def series_page():
        return render_template(
            "series.html",
            page="series",
            series=mock.MOCK_SERIES,
        )

    @app.get("/correlation")
    def correlation_page():
        return render_template(
            "correlation.html",
            page="correlation",
            series=mock.MOCK_SERIES,
        )

    @app.get("/correlation/history")
    def correlation_history_page():
        return render_template(
            "correlation_history.html",
            page="correlation_history",
            runs=mock.MOCK_CORRELATION_HISTORY,
            series=mock.MOCK_SERIES,
        )

    @app.get("/tsa")
    def tsa_page():
        return render_template(
            "tsa.html",
            page="tsa",
            series=mock.MOCK_SERIES,
            models=mock.TSA_MODELS,
        )

    @app.get("/tsa/history")
    def tsa_history_page():
        return render_template(
            "tsa_history.html",
            page="tsa_history",
            runs=mock.MOCK_TSA_HISTORY,
            series=mock.MOCK_SERIES,
        )

  # --- Mock API (spaeter: echte Services) ---

    @app.get("/api/series")
    def api_series():
        return jsonify([mock.series_to_dict(s) for s in mock.MOCK_SERIES])

    @app.get("/api/series/<slug>")
    def api_series_detail(slug: str):
        s = mock.series_by_slug(slug)
        if s is None:
            return jsonify({"error": "Serie nicht gefunden"}), 404
        return jsonify(mock.series_to_dict(s))

    @app.get("/api/overlap")
    def api_overlap():
        slug_a = request.args.get("a", "")
        slug_b = request.args.get("b", "")
        data = mock.pair_overlap(slug_a, slug_b)
        if data is None:
            return jsonify({"error": "Keine Ueberlappung oder ungueltige Serie"}), 400
        return jsonify(data)

    @app.get("/api/correlation/history")
    def api_correlation_history():
        rows = []
        for r in mock.MOCK_CORRELATION_HISTORY:
            rows.append(
                {
                    "id": r.id,
                    "series_a": r.series_a,
                    "series_b": r.series_b,
                    "start_date": r.start_date.isoformat(),
                    "end_date": r.end_date.isoformat(),
                    "analysis_mode": r.analysis_mode,
                    "max_lag": r.max_lag,
                    "best_lag": r.best_lag,
                    "best_r": r.best_r,
                    "created_at": r.created_at.isoformat(),
                }
            )
        return jsonify(rows)

    @app.get("/api/tsa/models")
    def api_tsa_models():
        return jsonify(mock.TSA_MODELS)

    @app.get("/api/tsa/history")
    def api_tsa_history():
        rows = []
        for r in mock.MOCK_TSA_HISTORY:
            rows.append(
                {
                    "id": r.id,
                    "series_slug": r.series_slug,
                    "models": r.models,
                    "analysis_mode": r.analysis_mode,
                    "train_start": r.train_start.isoformat(),
                    "train_end": r.train_end.isoformat(),
                    "forecast_end": r.forecast_end.isoformat(),
                    "status": r.status,
                    "created_at": r.created_at.isoformat(),
                }
            )
        return jsonify(rows)

    @app.post("/api/upload")
    def api_upload():
        f = request.files.get("file")
        if f is None or not f.filename:
            return jsonify({"ok": False, "message": "Keine Datei gewaehlt"}), 400
        return jsonify(mock.mock_upload_result(f.filename))

    @app.post("/api/correlation/run")
    def api_correlation_run():
        body = request.get_json(silent=True) or {}
        return jsonify(
            {
                "ok": True,
                "status": "queued",
                "message": "Korrelation simuliert (Backend folgt)",
                "job": {
                    **body,
                    "started_at": datetime.now().isoformat(),
                    "output_preview": "output/correlation_thesis_pdax_vs_erwerbslose_.../",
                },
            }
        )

    @app.post("/api/tsa/run")
    def api_tsa_run():
        body = request.get_json(silent=True) or {}
        return jsonify(
            {
                "ok": True,
                "status": "queued",
                "message": "TSA-Lauf simuliert (Backend folgt)",
                "job": {
                    **body,
                    "started_at": datetime.now().isoformat(),
                    "output_preview": "output/tsa_thesis_1987-12-01_to_2006-07-01/",
                },
            }
        )

    return app
