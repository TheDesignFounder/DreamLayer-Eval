"""Local research API, attachable to the original DreamLayer Flask app."""

from __future__ import annotations

import io
import os
import threading
import uuid
from pathlib import Path

from flask import Blueprint, Flask, jsonify, request, send_file
from flask_cors import CORS

from . import __version__, analysis, bundles, comparison, experiments, human, judges
from .contracts import record
from .media import image_evidence
from .metrics import REGISTRY
from .store import Store
from .types import PathLike


def blueprint(db_path: PathLike | None = None, media_root: PathLike | None = None) -> Blueprint:
    "Build local research routes backed by one SQLite store and managed media root."
    bp = Blueprint("research", __name__, url_prefix="/api/research")
    db_path = db_path or os.getenv("DREAMLAYER_RESEARCH_DB", ".research/research.sqlite3")
    media_root = Path(media_root or Path(db_path).parent / "media").resolve()
    media_root.mkdir(parents=True, exist_ok=True)
    store = Store(db_path)

    @bp.errorhandler(ValueError)
    @bp.errorhandler(KeyError)
    @bp.errorhandler(TypeError)
    def invalid(exc):
        return jsonify({"error": str(exc)}), 400

    @bp.route("/health")
    def health():
        return jsonify({"status": "ok", "schema_version": 1})

    @bp.route("/metrics")
    def metrics():
        return jsonify(list(REGISTRY.values()))

    @bp.route("/experiments", methods=["GET", "POST"])
    def experiments_list():
        if request.method == "POST":
            return jsonify(experiments.create(store, request.get_json(), media_root)), 201
        return jsonify(store.list("experiment"))

    @bp.route("/experiments/<eid>")
    def experiment(eid):
        return jsonify(
            {
                "experiment": store.get(eid),
                "records": store.list(experiment_id=eid),
                "job": store.job(eid),
            }
        )

    @bp.route("/preview", methods=["POST"])
    def preview():
        return jsonify(experiments.preview(request.get_json()))

    @bp.route("/judges/<rid>/retry", methods=["POST"])
    def retry_judge(rid):
        return jsonify(judges.retry_request(store, rid, **request.get_json()))

    @bp.route("/judges/<rid>/reconcile", methods=["POST"])
    def reconcile_judge(rid):
        return jsonify(judges.reconcile_request(store, rid, **request.get_json()))

    @bp.route("/experiments/<eid>/comparison", methods=["GET", "POST"])
    def compare(eid):
        config = request.get_json(silent=True) or {
            "label_view": request.args.get("label_view", "raw")
        }
        return jsonify(comparison.compare(store, eid, **config))

    @bp.route("/experiments/<eid>/comparison-rows", methods=["GET", "POST"])
    def comparison_rows(eid):
        config = request.get_json(silent=True) or {
            "label_view": request.args.get("label_view", "raw")
        }
        return jsonify(comparison.joined_rows(store, eid, **config))

    @bp.route("/experiments/<eid>/analysis-input/<operation>", methods=["POST"])
    def analysis_input(eid, operation):
        return jsonify(
            comparison.analysis_input(
                store, eid, operation, **(request.get_json(silent=True) or {})
            )
        )

    @bp.route("/import-rankings", methods=["POST"])
    def import_rankings():
        from .historical_import import import_rankings

        uploaded = request.files["file"]
        suffix = ".csv" if uploaded.filename.lower().endswith(".csv") else ".json"
        path = media_root / "uploads" / (str(uuid.uuid4()) + suffix)
        path.parent.mkdir(exist_ok=True, parents=True)
        uploaded.save(path)
        try:
            return jsonify(import_rankings(store, path)), 201
        finally:
            path.unlink()

    @bp.route("/experiments/<eid>/plan")
    def plan(eid):
        return jsonify(experiments.plan(store, eid))

    @bp.route("/experiments/<eid>/run", methods=["POST"])
    def run(eid):
        store.get(eid)
        options = request.get_json(silent=True) or {}
        rerun_failed = bool(options.get("rerun_failed", False))
        upgrade = bool(options.get("upgrade_evaluators", False))
        from .upgrades import warnings

        notices = warnings(store, eid, upgrade, rerun_failed)

        def worker():
            try:
                experiments.execute(
                    store, eid, media_root, rerun_failed=rerun_failed, upgrade_evaluators=upgrade
                )
            except Exception:
                pass  # Durable job.error contains the failure for UI/CLI inspection.

        threading.Thread(target=worker, daemon=True).start()
        return jsonify({"state": "queued", "resume_warnings": notices}), 202

    @bp.route("/experiments/<eid>/cancel", methods=["POST"])
    def cancel(eid):
        return jsonify(store.job(eid, cancel=1))

    @bp.route("/experiments/<eid>/analysis", methods=["GET", "POST"])
    def analyze(eid):
        config = request.get_json(silent=True) or {"seed": 0, "label_view": "raw"}
        output = analysis.summarize(store, eid, **config)
        if request.method == "POST":
            store.put(
                record(
                    "analysis",
                    eid,
                    config=config,
                    output=output,
                    implementation=f"dreamlayer-research-{__version__}",
                )
            )
        return jsonify(output)

    @bp.route("/upload", methods=["POST"])
    def upload():
        if "file" not in request.files:
            raise ValueError("Media file required")
        file = request.files["file"]
        filename = Path(file.filename).name
        dest = media_root / "uploads" / str(uuid.uuid4()) / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        file.save(dest)
        try:
            asset = experiments.managed_asset(dest, media_root)
        except Exception as exc:
            return jsonify({"error": "Cannot inspect media: " + str(exc)}), 400
        return jsonify(
            {
                "path": asset["locator"],
                "original_filename": filename,
                "media": asset["media"],
                "sha256": asset["sha256"],
            }
        ), 201

    @bp.route("/assets/<aid>/media")
    def asset_media(aid):
        asset = store.get(aid)
        if asset["kind"] != "asset":
            raise ValueError("Not a media asset")
        return send_file(asset["locator"], conditional=True)

    @bp.route("/experiments/<eid>/assign", methods=["POST"])
    def assign(eid):
        assignments = human.assign(store, eid, **request.get_json())
        return jsonify([human.blinded(store, a) for a in assignments])

    @bp.route("/review")
    def review_list():
        rater = request.args.get("rater", "")
        return jsonify(
            [human.blinded(store, a) for a in store.list("assignment") if a["rater_id"] == rater]
        )

    @bp.route("/review/<aid>", methods=["GET", "POST"])
    def review(aid):
        if request.method == "POST":
            return jsonify(human.annotate(store, aid, request.get_json())), 201
        return jsonify(human.blinded(store, store.get(aid)))

    @bp.route("/review/<aid>/media/<int:slot>")
    @bp.route("/review/<aid>/reference/<int:slot>")
    def blind_media(aid, slot):
        assignment = store.get(aid)
        field = "reference_ids" if "/reference/" in request.path else "asset_ids"
        ids = assignment.get(field, [])
        if slot >= len(ids):
            raise ValueError("Invalid blind presentation slot")
        asset = store.get(ids[slot])
        if asset["media"]["modality"] == "image":
            out = io.BytesIO()
            image_evidence(asset["locator"], 2048).save(out, "PNG")
            out.seek(0)
            return send_file(out, mimetype="image/png", download_name="evidence.png")
        return send_file(
            asset["locator"],
            conditional=True,
            download_name="evidence" + Path(asset["locator"]).suffix,
        )

    @bp.route("/experiments/<eid>/annotations", methods=["GET", "POST"])
    def annotations(eid):
        format = request.args.get("format", "jsonl")
        if request.method == "POST":
            count = human.import_annotations(
                store, request.get_data(as_text=True), format, experiment_id=eid
            )
            return jsonify({"imported": count})
        return (
            human.export_annotations(
                store, eid, format, blinded_export=request.args.get("blinded") == "1"
            ),
            200,
            {"Content-Type": "text/plain; charset=utf-8"},
        )

    @bp.route("/experiments/<eid>/export")
    def export(eid):
        dest = media_root.parent / (eid + ".zip")
        bundles.export_bundle(store, eid, dest, include_media=request.args.get("media", "1") == "1")
        return send_file(dest, as_attachment=True, download_name="dreamlayer-experiment.zip")

    @bp.route("/import-bundle", methods=["POST"])
    def import_zip():
        file = request.files["file"]
        eid = bundles.import_bundle(store, file.stream, media_root)
        return jsonify({"experiment_id": eid}), 201

    return bp


def create_app(db_path: PathLike | None = None, media_root: PathLike | None = None) -> Flask:
    "Create the standalone Flask research application."
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024
    app.json.sort_keys = True
    CORS(app, origins=["http://127.0.0.1:8080", "http://localhost:8080", "http://127.0.0.1:4173"])
    app.register_blueprint(blueprint(db_path, media_root))
    return app
