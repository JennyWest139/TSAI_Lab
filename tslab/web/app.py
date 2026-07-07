"""Flask-App: Dashboard-Oberflaeche (UI + DB/Mock-API)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, render_template, request, send_file

from tslab.config_loader import load_dotenv_file
from tslab.services.report_service import load_report_config
from tslab.web import mock_data as mock
from tslab.web.backend import WebBackend
from tslab.web.output_browser import list_directory, resolve_output_path, serve_output_file, zip_directory
from tslab.services.order_selection import order_table_rows
from tslab.web.perf import configure_perf_logging

_WEB_ROOT = Path(__file__).resolve().parent
APP_BOOT_ID = uuid4().hex


def create_app(*, use_mock: bool = False) -> Flask:
    load_dotenv_file()
    configure_perf_logging()
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
            "ai_reports_enabled": backend.ai_reports_enabled,
            "report_models": backend.list_report_models(),
            "all_tags": backend.all_tags(),
        }

    def _active_tag() -> str | None:
        tag = (request.args.get("tag") or "").strip()
        return tag or None

    def _series_dicts():
        tag = _active_tag()
        include_hidden = request.args.get("include_hidden", "0") in ("1", "true", "yes")
        return [
            mock.series_to_dict(s)
            for s in backend.list_series(tag=tag, include_hidden=include_hidden)
        ]

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
            series=backend.list_series(tag=_active_tag()),
            active_tag=_active_tag(),
        )

    @app.get("/tags")
    def tags_page():
        return render_template(
            "categories.html",
            page="tags",
            categories=backend.list_categories(),
            return_to=request.args.get("return_to") or "",
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
            runs=backend.list_correlation_history(tag=_active_tag()),
            active_tag=_active_tag(),
        )

    @app.get("/tsa")
    def tsa_page():
        return render_template(
            "tsa.html",
            page="tsa",
            series=backend.list_series(),
            models=mock.TSA_MODELS,
            order_rows=order_table_rows(),
        )

    @app.get("/tsa/history")
    def tsa_history_page():
        return render_template(
            "tsa_history.html",
            page="tsa_history",
            runs=backend.list_tsa_history(tag=_active_tag()),
            series=backend.list_series(),
            active_tag=_active_tag(),
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

    @app.get("/output/zip/")
    @app.get("/output/zip/<path:subpath>")
    def output_zip(subpath: str = ""):
        zpath = zip_directory(subpath)
        return send_file(zpath, as_attachment=True, download_name=f"{subpath or 'output'}.zip")

    @app.get("/api/series")
    def api_series():
        return jsonify(_series_dicts())

    @app.get("/api/series/<slug>/meta")
    def api_series_meta(slug: str):
        data = backend.series_meta(slug)
        if data is None:
            return jsonify({"error": "Serie nicht gefunden"}), 404
        return jsonify(data)

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
                frequency=request.args.get("frequency") or None,
            )
            return jsonify(data)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/overlap")
    def api_overlap():
        slug_a = request.args.get("a", "")
        slug_b = request.args.get("b", "")
        data = backend.pair_overlap(
            slug_a, slug_b, frequency=request.args.get("frequency") or None
        )
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

    @app.post("/api/upload/validate-dates")
    def api_upload_validate_dates():
        f = request.files.get("file")
        if f is None or not f.filename:
            return jsonify({"ok": False, "message": "Keine Datei gewaehlt"}), 400
        date_column = request.form.get("date_column", "")
        if not date_column:
            return jsonify({"ok": False, "message": "date_column fehlt"}), 400
        dayfirst_raw = request.form.get("dayfirst")
        dayfirst = None
        if dayfirst_raw in ("1", "true", "yes"):
            dayfirst = True
        elif dayfirst_raw in ("0", "false", "no"):
            dayfirst = False
        try:
            det = backend.validate_upload_dates(
                f.read(),
                f.filename,
                date_column=date_column,
                date_parse_mode=request.form.get("date_parse_mode", "auto"),
                date_format=request.form.get("date_format") or None,
                dayfirst=dayfirst,
            )
            return jsonify({"ok": True, "date_detection": det})
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/upload/validate-decimals")
    def api_upload_validate_decimals():
        f = request.files.get("file")
        if f is None or not f.filename:
            return jsonify({"ok": False, "message": "Keine Datei gewaehlt"}), 400
        value_column = request.form.get("value_column", "")
        if not value_column:
            return jsonify({"ok": False, "message": "value_column fehlt"}), 400
        try:
            det = backend.validate_upload_decimals(
                f.read(),
                f.filename,
                value_column=value_column,
                decimal_mode=request.form.get("decimal_mode", "auto"),
            )
            return jsonify({"ok": True, "decimal_detection": det})
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/upload")
    def api_upload():
        f = request.files.get("file")
        if f is None or not f.filename:
            return jsonify({"ok": False, "message": "Keine Datei gewaehlt"}), 400
        dayfirst_raw = request.form.get("dayfirst")
        dayfirst = None
        if dayfirst_raw in ("1", "true", "yes"):
            dayfirst = True
        elif dayfirst_raw in ("0", "false", "no"):
            dayfirst = False
        try:
            result = backend.import_upload(
                f.read(),
                f.filename,
                date_column=request.form.get("date_column", ""),
                value_column=request.form.get("value_column", ""),
                series_name=request.form.get("series_name") or None,
                date_parse_mode=request.form.get("date_parse_mode", "auto"),
                date_format=request.form.get("date_format") or None,
                dayfirst=dayfirst,
                sep=request.form.get("sep", ";"),
                encoding=request.form.get("encoding", "utf-8-sig"),
                decimal_mode=request.form.get("decimal_mode", "auto"),
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

    @app.get("/api/tsa/window-preview")
    def api_tsa_window_preview():
        try:
            return jsonify(backend.tsa_window_preview(dict(request.args)))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/delete/preview")
    def api_delete_preview():
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(backend.delete_preview(body))
        except (ValueError, LookupError) as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/delete/confirm")
    def api_delete_confirm():
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(backend.delete_confirm(body))
        except (ValueError, LookupError) as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/tags")
    def api_tags_set():
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(backend.update_tags(body))
        except (ValueError, LookupError) as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.get("/api/tags/suggest")
    def api_tags_suggest():
        return jsonify(backend.tag_suggestions(request.args.get("q", "")))

    @app.get("/api/backend/status")
    def api_backend_status():
        return jsonify(
            {
                "uses_mock": backend.uses_mock,
                "mode_label": backend.mode_label,
                "database_url": backend.database_url,
                "database_kind": backend.database_kind,
            }
        )

    @app.get("/api/app-session")
    def api_app_session():
        """Boot-ID wechselt bei Server-Neustart — Formular-Session wird dann zurückgesetzt."""
        return jsonify({"boot_id": APP_BOOT_ID})

    @app.get("/api/categories")
    def api_categories():
        return jsonify(backend.list_categories())

    @app.post("/api/categories")
    def api_categories_create():
        body = request.get_json(silent=True) or {}
        name = str(body.get("name", "")).strip()
        if not name:
            return jsonify({"ok": False, "message": "Kategoriename fehlt."}), 400
        try:
            return jsonify(backend.create_category_entry(name))
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 500

    @app.patch("/api/categories/<int:category_id>")
    def api_categories_update(category_id: int):
        body = request.get_json(silent=True) or {}
        name = str(body.get("name", "")).strip()
        try:
            return jsonify(backend.update_category_entry(category_id, name))
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.delete("/api/categories/<int:category_id>")
    def api_categories_delete(category_id: int):
        try:
            return jsonify(backend.delete_category_entry(category_id))
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.patch("/api/series/<slug>")
    def api_series_update(slug: str):
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(
                backend.update_series_meta(slug, name=str(body.get("name", "")))
            )
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.get("/api/report/models")
    def api_report_models():
        return jsonify(
            {
                "enabled": backend.ai_reports_enabled,
                "models": backend.list_report_models(),
                "default_model": load_report_config().default_model,
            }
        )

    @app.post("/api/report/generate")
    def api_report_generate():
        body = request.get_json(silent=True) or {}
        output_dir = str(body.get("output_dir", "")).strip()
        if not output_dir:
            return jsonify({"ok": False, "message": "output_dir fehlt."}), 400
        try:
            result = backend.generate_output_report(
                output_dir,
                model_id=body.get("report_model"),
                run_type=str(body.get("run_type") or "Analyse"),
                analysis_mode=str(body.get("analysis_mode") or "extended"),
            )
            return jsonify(result)
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "message": str(exc)}), 500

    @app.post("/api/report/session/prepare")
    def api_report_session_prepare():
        body = request.get_json(silent=True) or {}
        output_dir = str(body.get("output_dir", "")).strip()
        if not output_dir:
            return jsonify({"ok": False, "message": "output_dir fehlt."}), 400
        try:
            return jsonify(
                backend.prepare_output_report(
                    output_dir,
                    model_id=body.get("report_model"),
                    run_type=str(body.get("run_type") or "Analyse"),
                    analysis_mode=str(body.get("analysis_mode") or "extended"),
                )
            )
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/report/session/step")
    def api_report_session_step():
        body = request.get_json(silent=True) or {}
        output_dir = str(body.get("output_dir", "")).strip()
        if not output_dir:
            return jsonify({"ok": False, "message": "output_dir fehlt."}), 400
        action = body.get("action")
        if action is not None:
            action = str(action).strip() or None
        try:
            return jsonify(backend.step_output_report(output_dir, action=action))
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    @app.post("/api/run/finalize")
    def api_run_finalize():
        body = request.get_json(silent=True) or {}
        output_dir = str(body.get("output_dir", "")).strip()
        if not output_dir:
            return jsonify({"ok": False, "message": "output_dir fehlt."}), 400
        try:
            return jsonify(
                backend.finalize_deferred_run(
                    output_dir,
                    report_result=body.get("report_result"),
                )
            )
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400

    return app
