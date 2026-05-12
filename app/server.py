"""Flask API server - provides REST API for the frontend.

Dev mode:  Vite dev server (port 5173) proxies /api to Flask (port 5050).
Prod mode: Flask serves the built Vite dist files directly.
"""

import json
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from services.task_service import TaskService
from services.audit_service import AuditService
from core.logging import get_logger

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
    """Submit human review: approve, adjust, or reject."""
    body = request.get_json() or {}
    action = body.get("action", "approve")

    if action == "adjust":
        result = svc.adjust_plan(task_id, body.get("adjustments", {}))
        return jsonify(result)

    if action in ("approve", "reject"):
        from storage import TaskStore
        store = TaskStore()
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


# ---- Single-Agent Classification (SSE streaming) ----

@app.route("/api/classify", methods=["POST"])
def classify_files_stream():
    """Deep scan + classify with SSE progress streaming.

    Accepts: {"root_path": "/path/to/dir"}
    Returns: text/event-stream with real-time progress events + final result.
    """
    import queue
    import threading

    from flask import Response
    from tools.tool_runner import deep_scan_dir
    from agents import run_classifier

    body = request.get_json() or {}
    root_path = body.get("root_path", "")

    if not root_path:
        return jsonify({"success": False, "error": "root_path is required"}), 400
    if not os.path.isdir(root_path):
        return jsonify({"success": False, "error": f"path not found: {root_path}"}), 400

    def generate():
        # Step 1: deep scan (yield progress synchronously, scan is fast)
        yield _sse("progress", {"phase": "scanning", "current": 0, "total": 1,
                                "message": "正在深度扫描目录..."})
        scan_result = json.loads(deep_scan_dir({"root_path": root_path}))
        if not scan_result.get("success"):
            yield _sse("error", {"error": scan_result.get("error")})
            return

        files = scan_result.get("files", [])
        source_schema = scan_result.get("source_schema", {})
        dir_tree = scan_result.get("dir_tree", [])
        stats = scan_result.get("stats", {})
        yield _sse("progress", {"phase": "scanning", "current": 1, "total": 1,
                                "message": f"扫描完成，{stats['file_count']} 个文件，准备分类..."})

        # Step 2: classify in background thread, drain queue for real-time progress
        q: queue.Queue = queue.Queue()
        result_holder = {}

        def worker():
            def on_progress(phase, current, total, message):
                q.put(_sse("progress", {
                    "phase": phase, "current": current,
                    "total": total, "message": message,
                }))
            try:
                result_holder["data"] = run_classifier(files, on_progress=on_progress)
            except Exception as e:
                result_holder["error"] = str(e)
            q.put(None)  # sentinel

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        for item in iter(q.get, None):
            yield item

        t.join()

        if result_holder.get("error"):
            yield _sse("error", {"error": result_holder["error"]})
            return

        classification = result_holder.get("data", {})

        # Save result to timestamped JSON file
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        result_path = os.path.join(root_path, f"classify_result_{ts}.json")
        result_data = {
            "success": True,
            "root_path": scan_result["root_path"],
            "stats": stats,
            "dir_tree": dir_tree,
            "source_schema": source_schema,
            "categories": classification.get("categories", []),
            "category_order": classification.get("category_order", []),
            "total_files": classification.get("total_files", 0),
        }
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        logger.info("Result saved to %s", result_path)

        yield _sse("result", result_data)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no",
                             "Cache-Control": "no-cache"})


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---- Tool-based Classify (single-file tool calls) ----

@app.route("/api/classify-tool", methods=["POST"])
def classify_files_tool():
    """Tool-based classification: LLM calls classify_file tool once per file."""
    from tools.tool_runner import deep_scan_dir
    from agents import run_tool_classifier

    body = request.get_json() or {}
    root_path = body.get("root_path", "")

    if not root_path:
        return jsonify({"success": False, "error": "root_path is required"}), 400
    if not os.path.isdir(root_path):
        return jsonify({"success": False, "error": f"path not found: {root_path}"}), 400

    scan_result = json.loads(deep_scan_dir({"root_path": root_path}))
    if not scan_result.get("success"):
        return jsonify({"success": False, "error": scan_result.get("error")}), 500

    files = scan_result.get("files", [])
    source_schema = scan_result.get("source_schema", {})
    dir_tree = scan_result.get("dir_tree", [])
    stats = scan_result.get("stats", {})

    classification = run_tool_classifier(files)

    return jsonify({
        "success": True,
        "root_path": scan_result["root_path"],
        "stats": stats,
        "dir_tree": dir_tree,
        "source_schema": source_schema,
        "categories": classification.get("categories", []),
        "category_order": classification.get("category_order", []),
        "total_files": classification.get("total_files", 0),
        "llm_turns": classification.get("llm_turns", 0),
    })


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


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5050
    run_server(port)
