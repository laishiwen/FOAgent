import json
import os
import uuid
from datetime import datetime, timezone

from app.core.config import STORE_DIR


class TaskStore:
    def __init__(self):
        self._base = os.path.join(STORE_DIR, "tasks")

    def _task_dir(self, task_id: str) -> str:
        return os.path.join(self._base, task_id)

    def create(self, root_path: str, dry_run: bool = True) -> dict:
        task_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        meta = {
            "task_id": task_id,
            "root_path": os.path.abspath(root_path),
            "dry_run": dry_run,
            "status": "created",
            "created_at": now,
            "updated_at": now,
        }
        os.makedirs(self._task_dir(task_id), exist_ok=True)
        self._write(task_id, "request.json", meta)
        return meta

    def get(self, task_id: str) -> dict:
        return self._read(task_id, "request.json")

    def update_status(self, task_id: str, status: str):
        meta = self.get(task_id)
        meta["status"] = status
        meta["updated_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        self._write(task_id, "request.json", meta)

    def save_scan(self, task_id: str, data: dict):
        self._write(task_id, "scan_result.json", data)

    def get_scan(self, task_id: str) -> dict:
        return self._read(task_id, "scan_result.json")

    def save_associations(self, task_id: str, data: dict):
        self._write(task_id, "associations.json", data)

    def get_associations(self, task_id: str) -> dict:
        return self._read(task_id, "associations.json")

    def save_plan(self, task_id: str, data: dict):
        self._write(task_id, "plan.json", data)

    def get_plan(self, task_id: str) -> dict:
        return self._read(task_id, "plan.json")

    def save_execution_log(self, task_id: str, data: dict):
        self._write(task_id, "execution_log.json", data)

    def get_execution_log(self, task_id: str) -> dict:
        return self._read(task_id, "execution_log.json")

    def save_harness_report(self, task_id: str, data: dict):
        self._write(task_id, "harness_report.json", data)

    def get_harness_report(self, task_id: str) -> dict:
        return self._read(task_id, "harness_report.json")

    def save_rollback_log(self, task_id: str, data: dict):
        self._write(task_id, "rollback_log.json", data)

    def _write(self, task_id: str, filename: str, data: dict):
        path = os.path.join(self._task_dir(task_id), filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _read(self, task_id: str, filename: str) -> dict:
        path = os.path.join(self._task_dir(task_id), filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"{filename} not found for task {task_id}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
