"""Audit service - provides log viewing utilities."""

import json
import os

from core.logging import get_logger
from storage import TaskStore

logger = get_logger(__name__)


class AuditService:
    def __init__(self, store: TaskStore = None):
        self.store = store or TaskStore()

    def get_execution_log(self, task_id: str) -> dict:
        return self.store.get_execution_log(task_id)

    def get_rollback_log(self, task_id: str) -> dict:
        return self.store.get_rollback_log(task_id)

    def get_harness_report(self, task_id: str) -> dict:
        return self.store.get_harness_report(task_id)

    def export_task_summary(self, task_id: str) -> dict:
        """Export full task summary for debugging."""
        result = {"task_id": task_id}
        for fname in ["request.json", "scan_result.json", "associations.json",
                       "plan.json", "execution_log.json", "harness_report.json",
                       "rollback_log.json"]:
            try:
                result[fname.replace(".json", "")] = self.store._read(task_id, fname)
            except FileNotFoundError:
                result[fname.replace(".json", "")] = None
        return result
