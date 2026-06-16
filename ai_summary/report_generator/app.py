"""
Flask App — AI Summary Report Generator.
Web UI + Swagger API for generating beautiful HTML reports from Elasticsearch data.

Swagger UI available at: /apidocs
"""

import os
import json
import time
import threading
import uuid

from flask import (
    Flask, render_template, request, jsonify,
    send_file, redirect, url_for, abort,
)
from flasgger import Swagger

from config import MODES, REPORT_DIR, LLM_MODEL, OLLAMA_URL, VECTOR_INDEX, logger
from rag_engine import generate_report, get_es
from report_store import save_report, load_report, list_reports
from report_renderer import render_report

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Swagger configuration
app.config['SWAGGER'] = {
    'title': 'AI Summary Report Generator API',
    'description': 'Generate AI-powered summary reports from Elasticsearch data. Supports 14+ intent types including enumeration, analysis, comparison, trends, predictions, and more.',
    'version': '3.0',
    'termsOfService': '',
    'specs_route': '/apidocs/',
    'uiversion': 3,
}
Swagger(app)

# In-memory job store for async generation
_jobs = {}
_jobs_lock = threading.Lock()
_jobs_lock = threading.Lock()


def _run_generation(job_id, query, mode, filters):
    """Background thread: generate report and store result."""
    try:
        with _jobs_lock:
            _jobs[job_id]['status'] = 'running'
            _jobs[job_id]['started_at'] = time.time()

        report_data = generate_report(query=query, mode=mode, filters=filters)
        report_id = save_report(report_data)

        with _jobs_lock:
            _jobs[job_id]['status'] = 'done'
            _jobs[job_id]['report_id'] = report_id
            _jobs[job_id]['title'] = report_data['title']
            _jobs[job_id]['mode'] = mode
            _jobs[job_id]['generation_time'] = report_data['metadata']['generation_time']
            _jobs[job_id]['ended_at'] = time.time()

        logger.info(f"Job {job_id} done: report {report_id}")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        with _jobs_lock:
            _jobs[job_id]['status'] = 'error'
            _jobs[job_id]['error'] = str(e)
            _jobs[job_id]['ended_at'] = time.time()


# ── Routes ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """
    Main page — report generation form
    ---
    tags:
      - UI
    responses:
      200:
        description: HTML page with report generation form
    """
    reports = list_reports(limit=10)
    return render_template("index.html", modes=MODES, reports=reports, model=LLM_MODEL)


@app.route("/generate", methods=["POST"])
def generate():
    """
    Start a report generation job (async)
    ---
    tags:
      - Generation
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - query
          properties:
            query:
              type: string
              description: The question or prompt
              example: "List all locations"
            mode:
              type: string
              enum: [answer, analyze, predict, summarize]
              default: answer
              description: Report mode
            activity_type:
              type: string
              description: Filter by activity type
            form_type:
              type: string
              description: Filter by form type
            source_type:
              type: string
              description: Filter by source type
            location_name:
              type: string
              description: Filter by location name
            activity_name:
              type: string
              description: Filter by activity name
    responses:
      202:
        description: Job accepted, returns job_id for polling
        schema:
          type: object
          properties:
            job_id:
              type: string
              example: "a1b2c3d4-e5f6"
            status:
              type: string
              example: "queued"
      400:
        description: Invalid request (missing query or invalid mode)
      429:
        description: This report is already being generated
    """
    data = request.get_json() or request.form
    query = (data.get("query") or "").strip()
    mode = (data.get("mode") or "answer").strip().lower()

    if not query:
        return jsonify({"error": "Please enter a query"}), 400
    if mode not in MODES:
        return jsonify({"error": f"Invalid mode: {mode}"}), 400

    filters = {}
    for f in ["activity_type", "form_type", "source_type", "location_name", "activity_name"]:
        val = (data.get(f) or "").strip()
        if val:
            filters[f] = val

    job_id = str(uuid.uuid4())[:12]
    with _jobs_lock:
        _jobs[job_id] = {
            'status': 'queued',
            'query': query,
            'mode': mode,
            'filters': filters,
            'created_at': time.time(),
        }

    thread = threading.Thread(
        target=_run_generation,
        args=(job_id, query, mode, filters if filters else None),
        daemon=True,
    )
    thread.start()

    logger.info(f"Job {job_id} started: mode={mode}, query='{query[:60]}'")
    return jsonify({"job_id": job_id, "status": "queued"}), 202


@app.route("/jobs/<job_id>")
def job_status(job_id):
    """
    Check status of a generation job
    ---
    tags:
      - Generation
    parameters:
      - in: path
        name: job_id
        type: string
        required: true
        description: Job ID returned from /generate
    responses:
      200:
        description: Job status
        schema:
          type: object
          properties:
            status:
              type: string
              enum: [queued, running, done, error]
            report_id:
              type: string
              description: Report ID (when done)
            title:
              type: string
              description: Report title (when done)
            generation_time:
              type: number
              description: Generation time in seconds (when done)
            error:
              type: string
              description: Error message (when error)
      404:
        description: Job not found
    """
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/report/<report_id>")
def view_report(report_id):
    """
    View a generated report as a full HTML page
    ---
    tags:
      - Reports
    parameters:
      - in: path
        name: report_id
        type: string
        required: true
        description: Report ID
    responses:
      200:
        description: Full HTML report page
      404:
        description: Report not found
    """
    report_data = load_report(report_id)
    if not report_data:
        abort(404)
    html = render_report(report_data)
    return html


@app.route("/report/<report_id>/download")
def download_report(report_id):
    """
    Download report as HTML file
    ---
    tags:
      - Reports
    parameters:
      - in: path
        name: report_id
        type: string
        required: true
    responses:
      200:
        description: HTML file download
      404:
        description: Report not found
    """
    report_data = load_report(report_id)
    if not report_data:
        abort(404)
    html = render_report(report_data)
    filepath = os.path.join(REPORT_DIR, f"report_{report_id}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    return send_file(filepath, as_attachment=True,
                     download_name=f"ai_report_{report_id}.html",
                     mimetype="text/html")


@app.route("/report/<report_id>/json")
def report_json(report_id):
    """
    Get report data as JSON
    ---
    tags:
      - Reports
    parameters:
      - in: path
        name: report_id
        type: string
        required: true
    responses:
      200:
        description: Report data as JSON
      404:
        description: Report not found
    """
    report_data = load_report(report_id)
    if not report_data:
        abort(404)
    return jsonify(report_data)


@app.route("/api/reports")
def api_list_reports():
    """
    List recent reports
    ---
    tags:
      - Reports
    parameters:
      - in: query
        name: limit
        type: integer
        default: 20
        description: Maximum number of reports to return
    responses:
      200:
        description: List of recent reports
    """
    limit = request.args.get("limit", 20, type=int)
    return jsonify({"reports": list_reports(limit=limit)})


@app.route("/api/status")
def api_status():
    """
    Check system status — ES connection, Ollama, index count
    ---
    tags:
      - System
    responses:
      200:
        description: System status
        schema:
          type: object
          properties:
            status:
              type: string
              enum: [ok, degraded]
            components:
              type: object
              properties:
                elasticsearch:
                  type: object
                  properties:
                    status:
                      type: string
                    cluster:
                      type: string
                    cluster_status:
                      type: string
                ollama:
                  type: object
                  properties:
                    status:
                      type: string
                    models_count:
                      type: integer
                    current_model:
                      type: string
    """
    status = {"status": "ok", "components": {}}

    try:
        es = get_es()
        health = es.cluster.health()
        count = es.count(index=VECTOR_INDEX)["count"]
        status["components"]["elasticsearch"] = {
            "status": "ok",
            "cluster": health["cluster_name"],
            "cluster_status": health["status"],
            f"index_{VECTOR_INDEX}_count": count,
        }
    except Exception as e:
        status["components"]["elasticsearch"] = {"status": "error", "error": str(e)}
        status["status"] = "degraded"

    try:
        import requests as req_lib
        r = req_lib.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        status["components"]["ollama"] = {
            "status": "ok",
            "url": OLLAMA_URL,
            "models_count": len(models),
            "current_model": LLM_MODEL,
        }
    except Exception as e:
        status["components"]["ollama"] = {"status": "error", "error": str(e)}
        status["status"] = "degraded"

    return jsonify(status)


@app.route("/api/filters")
def api_filters():
    """
    Get available filter values from the index (aggregations)
    ---
    tags:
      - System
    responses:
      200:
        description: Available filter values
        schema:
          type: object
          properties:
            activity_type:
              type: array
              items:
                type: string
            form_type:
              type: array
              items:
                type: string
            source_type:
              type: array
              items:
                type: string
            location_name:
              type: array
              items:
                type: string
            activity_name:
              type: array
              items:
                type: string
      500:
        description: ES aggregation failed
    """
    try:
        es = get_es()
        agg_result = es.search(index=VECTOR_INDEX, size=0, body={
            "aggs": {
                "activity_types": {"terms": {"field": "activity_type.keyword", "size": 50}},
                "form_types": {"terms": {"field": "form_type.keyword", "size": 50}},
                "source_types": {"terms": {"field": "source_type.keyword", "size": 50}},
                "locations": {"terms": {"field": "location_name.keyword", "size": 100}},
                "activities": {"terms": {"field": "activity_name.keyword", "size": 100}},
            }
        })
        aggs = agg_result["aggregations"]
        return jsonify({
            "activity_type": [b["key"] for b in aggs["activity_types"]["buckets"]],
            "form_type": [b["key"] for b in aggs["form_types"]["buckets"]],
            "source_type": [b["key"] for b in aggs["source_types"]["buckets"]],
            "location_name": [b["key"] for b in aggs["locations"]["buckets"]],
            "activity_name": [b["key"] for b in aggs["activities"]["buckets"]],
        })
    except Exception as e:
        logger.error(f"Filter aggregation failed: {e}")
        return jsonify({"error": str(e)}), 500


# ── Error handlers ────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting AI Summary Report Generator on port 5001")
    app.run(host="0.0.0.0", port=5001, debug=True, threaded=True)
