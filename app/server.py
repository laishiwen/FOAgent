"""Flask API server - provides REST API for the frontend.

Dev mode:  Vite dev server (port 5173) proxies /api to Flask (port 5050).
Prod mode: Flask serves the built Vite dist files directly.
"""

import json
import os

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from app.services.task_service import TaskService
from app.services.audit_service import AuditService
from app.core.logging import get_logger

logger = get_logger(__name__)

app = Flask(__name__, static_folder=None)
CORS(app)
svc = TaskService()
audit = AuditService()

FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend", "dist"
)


# ---- API Routes ----

@app.route("/api/tasks", methods=["POST"])
def create_task():
    """Create a new task. Frontend provides only root_path."""
    body = request.get_json() or {}
    root_path = body.get("root_path", "")
    dry_run = body.get("dry_run", True)

    if not root_path:
        return jsonify({"success": False, "error": "root_path is required"}), 400
    if not os.path.isdir(root_path):
        return jsonify({"success": False, "error": f"path not found: {root_path}"}), 400

    meta = svc.create_task(root_path, dry_run)
    return jsonify(meta), 201


@app.route("/api/tasks/<task_id>/plan", methods=["POST"])
def run_planning(task_id):
    """Run scan + Agent A + Agent B + plan generation."""
    try:
        result = svc.run_planning_phase(task_id)
        return jsonify(result)
    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        logger.error("Planning failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    """Get task details and status."""
    try:
        result = svc.get_task_status(task_id)
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({"success": False, "error": "task not found"}), 404


@app.route("/api/tasks/<task_id>/review", methods=["POST"])
def submit_review(task_id):
    """Submit human review results."""
    body = request.get_json() or {}
    action = body.get("action", "approve")

    if action in ("approve", "adjust", "reject"):
        from app.storage import TaskStore
        store = TaskStore()

        if action == "adjust":
            adjusted_plan = body.get("plan", {})
            if adjusted_plan:
                store.save_plan(task_id, adjusted_plan)

        new_status = "approved" if action != "reject" else "failed"
        store.update_status(task_id, new_status)
        return jsonify({"task_id": task_id, "status": new_status})

    return jsonify({"success": False, "error": f"unknown action: {action}"}), 400


@app.route("/api/tasks/<task_id>/execute", methods=["POST"])
def execute_task(task_id):
    """Execute the plan."""
    try:
        result = svc.run_execution_phase(task_id)
        return jsonify(result)
    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        logger.error("Execution failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/tasks/<task_id>/rollback", methods=["POST"])
def rollback_task(task_id):
    """Rollback a task."""
    try:
        result = svc.run_rollback(task_id)
        return jsonify(result)
    except FileNotFoundError as e:
        return jsonify({"success": False, "error": str(e)}), 404
    except Exception as e:
        logger.error("Rollback failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/tasks/<task_id>/harness", methods=["GET"])
def get_harness_report(task_id):
    """Get Harness Agent detection report."""
    try:
        report = audit.get_harness_report(task_id)
        return jsonify(report)
    except FileNotFoundError:
        return jsonify({"success": False, "error": "harness report not found"}), 404


@app.route("/api/tasks/<task_id>/export", methods=["GET"])
def export_task(task_id):
    """Export full task summary."""
    try:
        result = audit.export_task_summary(task_id)
        return jsonify(result)
    except FileNotFoundError:
        return jsonify({"success": False, "error": "task not found"}), 404


# ---- Production: serve Vite build ----

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path: str):
    if os.path.isdir(FRONTEND_DIST):
        file_path = os.path.join(FRONTEND_DIST, path) if path else ""
        if path and os.path.isfile(os.path.join(FRONTEND_DIST, path)):
            return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, "index.html")
    return jsonify({"message": "Frontend not built. Run: cd frontend && npm run dev"}), 200


def run_server(port: int = 5050):
    logger.info("Starting API server on http://localhost:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
