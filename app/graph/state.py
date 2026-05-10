"""Workflow state machine with step tracking and ID-based resolution."""

from datetime import datetime, timezone
import json
import os

from core.logging import get_logger
from storage import TaskStore

logger = get_logger(__name__)

VALID_TRANSITIONS = {
    "created":         ["scanning"],
    "scanning":        ["associating", "failed"],
    "associating":     ["naming", "failed"],
    "naming":          ["planned", "failed"],
    "planned":         ["review_required", "approved", "failed"],
    "review_required": ["approved", "failed"],
    "approved":        ["executing", "failed"],
    "executing":       ["completed", "failed"],
    "completed":       ["rolled_back"],
    "failed":          ["rolled_back"],
    "rolled_back":     [],
}


class WorkflowStateMachine:
    def __init__(self, task_id: str, store: TaskStore = None):
        self.task_id = task_id
        self.store = store or TaskStore()
        self.meta = self.store.get(task_id)
        self._state_log = []

    @property
    def status(self) -> str:
        return self.store.get(self.task_id)["status"]

    def transition(self, new_status: str):
        current = self.status
        allowed = VALID_TRANSITIONS.get(current, [])
        if new_status not in allowed and current != new_status:
            logger.warning("Non-standard: %s -> %s", current, new_status)
        self.store.update_status(self.task_id, new_status)

    def now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _log_step(self, step: str, status: str, input_summary: dict,
                  output_summary: dict):
        entry = {
            "step": step, "status": status,
            "started_at": self.now(),
            "input": input_summary,
            "output": output_summary,
        }
        self._state_log.append(entry)
        self.store.save_state(self.task_id, self._state_log)

    def _record_final_step(self, step: str, status: str, output_summary: dict):
        if self._state_log:
            self._state_log[-1]["finished_at"] = self.now()
        entry = {
            "step": step, "status": status,
            "finished_at": self.now(),
            "output": output_summary,
        }
        self._state_log.append(entry)
        self.store.save_state(self.task_id, self._state_log)

    # ---- Node 1: Scan ----

    def node_scan(self) -> dict:
        from tools.tool_runner import scan_parent_dir

        self.transition("scanning")
        root_path = self.meta["root_path"]
        data = {"root_path": root_path, "task_id": self.task_id}
        result = json.loads(scan_parent_dir(data))

        if not result["success"]:
            self.transition("failed")
            self._log_step("scan", "failed",
                           {"root_path": root_path},
                           {"error": result.get("error")})
            return result

        self.store.save_scan(self.task_id, result)
        self.store.save_source_schema(self.task_id,
                                      result.get("source_schema", {}))
        self._log_step("scan", "done",
                       {"root_path": root_path},
                       {"file_count": result["stats"]["file_count"],
                        "buckets": 1})
        return result

    # ---- Node 2: Analyze (enrich with file info) ----

    def node_analyze(self, scan_result: dict) -> list:
        from tools.tool_runner import get_file_info

        files = scan_result.get("files", [])
        enriched = []
        for f in files:
            data = {"file_path": f["path"], "task_id": self.task_id}
            result = json.loads(get_file_info(data))
            if result["success"]:
                merged = {**f, **{k: v for k, v in result.items()
                                  if k not in ("success", "error", "file_path")}}
                # Update source schema with kind
                if f.get("id"):
                    schema = self.store.get_source_schema(self.task_id)
                    schema[f["id"]]["kind"] = merged.get("kind", "?")
                    self.store.save_source_schema(self.task_id, schema)
                enriched.append(merged)
            else:
                enriched.append(f)
        return enriched

    # ---- Node 3: Agent A ----

    def node_detect_associations(self, files: list) -> dict:
        from agents import run_agent_a
        from utils.bucket import bucket_count

        self.transition("associating")
        result = run_agent_a(files, self.meta["root_path"])
        self.store.save_associations(self.task_id, result)

        n_buckets = bucket_count(len(files))
        self._log_step("assoc", "done",
                       {"file_count": len(files), "buckets": n_buckets},
                       {"groups": len(result.get("groups", [])),
                        "ungrouped": len(result.get("ungrouped", []))})
        return result

    # ---- Node 4: Agent B ----

    def node_build_categories(self, associations: dict, files: list) -> dict:
        from agents import run_agent_b

        self.transition("naming")
        result = run_agent_b(associations, files)
        self._log_step("naming", "done",
                       {"groups": len(associations.get("groups", []))},
                       {"categories": len(result.get("categories", []))})
        return result

    # ---- Node 5: Generate Plan (deterministic ID→path) ----

    def node_generate_plan(self, categories_result: dict,
                           associations: dict) -> dict:
        root_path = self.meta["root_path"]
        schema = self.store.get_source_schema(self.task_id)
        categories = categories_result.get("categories", [])

        directories_to_create = []
        moves = []
        needs_review_items = []

        for cat in categories:
            cat_name = cat["category_name"]
            dir_path = os.path.join(root_path, cat_name)
            directories_to_create.append(dir_path)

            member_ids = cat.get("member_ids", cat.get("members", []))
            for mid in member_ids:
                entry = schema.get(str(mid), {})
                fname = entry.get("name", str(mid))
                source_path = entry.get("path", os.path.join(root_path, fname))

                move = {
                    "file_id": mid,
                    "source_path": source_path,
                    "target_path": os.path.join(dir_path, fname),
                    "category": cat_name,
                    "confidence": cat.get("confidence", 0.5),
                }
                moves.append(move)
                if cat.get("needs_review"):
                    needs_review_items.append(move)

        # Conflict check
        targets = {}
        conflicts = []
        for m in moves:
            tgt = m["target_path"]
            if tgt in targets:
                conflicts.append({"target": tgt, "source_a": targets[tgt],
                                  "source_b": m["source_path"]})
            else:
                targets[tgt] = m["source_path"]

        plan = {
            "task_id": self.task_id,
            "root_path": root_path,
            "directories_to_create": list(set(directories_to_create)),
            "moves": moves,
            "conflicts": conflicts,
            "needs_review_items": needs_review_items,
            "categories": categories,
            "category_order": categories_result.get("category_order", []),
            "notes": categories_result.get("notes", []),
        }

        self.store.save_plan(self.task_id, plan)
        self._log_step("plan", "done",
                       {"categories": len(categories)},
                       {"moves": len(moves),
                        "dirs": len(set(directories_to_create)),
                        "conflicts": len(conflicts)})
        return plan

    # ---- Node 6: Validate ----

    def node_validate(self, plan: dict) -> dict:
        from tools.tool_runner import bash_dry_run_moves

        data = {"task_id": self.task_id, "root_path": self.meta["root_path"],
                "moves": plan.get("moves", [])}
        result = json.loads(bash_dry_run_moves(data))
        plan["validation"] = result
        self.store.save_plan(self.task_id, plan)

        has_issues = not result.get("can_execute", False) or plan.get("conflicts") or plan.get("needs_review_items")
        plan["needs_review"] = has_issues
        self.transition("review_required" if has_issues else "approved")
        return plan

    # ---- Node 8: Execute ----

    def node_execute(self, plan: dict) -> dict:
        from tools.tool_runner import bash_create_dirs, bash_move_files

        if self.meta.get("dry_run", True):
            logger.info("DRY RUN: skipping execution")
            log = {"task_id": self.task_id, "root_path": self.meta["root_path"],
                   "started_at": self.now(), "finished_at": self.now(),
                   "status": "dry_run_skipped", "steps": [],
                   "summary": {"created_directories": 0, "moved_files": 0,
                               "failed_steps": 0, "rolled_back_steps": 0}}
            self.store.save_execution_log(self.task_id, log)
            self._log_step("execute", "skipped", {"dry_run": True}, {"moves": 0})
            return log

        self.transition("executing")

        dirs_data = {"task_id": self.task_id, "root_path": self.meta["root_path"],
                     "dry_run": False,
                     "directories": [os.path.basename(d) for d in
                                     plan.get("directories_to_create", [])]}
        dirs_result = json.loads(bash_create_dirs(dirs_data))
        if not dirs_result["success"]:
            self.transition("failed")
            log = {"task_id": self.task_id, "status": "failed",
                   "steps": dirs_result.get("steps", []),
                   "summary": {"created_directories": 0, "moved_files": 0,
                               "failed_steps": len(dirs_result.get("steps", [])),
                               "rolled_back_steps": 0}}
            self.store.save_execution_log(self.task_id, log)
            self._log_step("execute", "failed", {}, {"error": "mkdir failed"})
            return log

        moves_data = {"task_id": self.task_id, "root_path": self.meta["root_path"],
                      "moves": plan.get("moves", [])}
        moves_result = json.loads(bash_move_files(moves_data))
        all_steps = dirs_result.get("steps", []) + moves_result.get("steps", [])

        log = {"task_id": self.task_id, "root_path": self.meta["root_path"],
               "started_at": self.now(), "finished_at": self.now(),
               "status": "completed" if moves_result["success"] else "failed",
               "steps": all_steps,
               "summary": {
                   "created_directories": len(dirs_result.get("steps", [])),
                   "moved_files": moves_result.get("summary", {}).get("completed", 0),
                   "failed_steps": moves_result.get("summary", {}).get("failed", 0),
                   "rolled_back_steps": 0,
               }}
        self.store.save_execution_log(self.task_id, log)
        self.transition("completed" if moves_result["success"] else "failed")
        self._log_step("execute", "done" if moves_result["success"] else "failed",
                       {"moves": len(plan.get("moves", []))},
                       {"moved": moves_result.get("summary", {}).get("completed", 0),
                        "failed": moves_result.get("summary", {}).get("failed", 0)})
        return log

    # ---- Node 9: Verify ----

    def node_verify(self, execution_log: dict) -> dict:
        scan = self.store.get_scan(self.task_id)
        plan = self.store.get_plan(self.task_id)
        original = {f["path"] for f in scan.get("files", [])}
        moved = set()
        for s in execution_log.get("steps", []):
            if s.get("status") == "completed":
                moved.add(s.get("source_path", ""))
        missing = original - moved
        self._log_step("verify", "done", {},
                       {"moved": len(moved), "total": len(original),
                        "missing": len(missing)})
        return {"success": len(missing) == 0, "original_count": len(original),
                "moved_count": len(moved),
                "missing": list(missing), "extra": list(moved - original)}

    # ---- Node 10: Harness ----

    def node_harness_check(self) -> dict:
        from agents import run_harness_agent
        try:
            scan = self.store.get_scan(self.task_id)
            assoc = self.store.get_associations(self.task_id)
            plan = self.store.get_plan(self.task_id)
            exec_log = self.store.get_execution_log(self.task_id)
        except FileNotFoundError as e:
            return {"verdict": "fail", "overall_assessment": f"missing data: {e}"}

        result = run_harness_agent(scan.get("files", []), assoc, plan, exec_log)
        self.store.save_harness_report(self.task_id, result)
        self._record_final_step("harness", "done",
                                {"verdict": result.get("verdict")})
        return result

    # ---- Node 11: Rollback ----

    def node_rollback(self) -> dict:
        from tools.tool_runner import bash_rollback
        exec_log_path = os.path.join(self.store._task_dir(self.task_id),
                                     "execution_log.json")
        data = {"task_id": self.task_id, "root_path": self.meta["root_path"],
                "execution_log_path": exec_log_path}
        result = json.loads(bash_rollback(data))
        self.store.save_rollback_log(self.task_id, result)
        self.transition("rolled_back")
        self._record_final_step("rollback", "done",
                                {"steps": len(result.get("steps", []))})
        return result

    # ---- Summary ----

    def write_summary(self):
        scan = self.store.get_scan(self.task_id)
        plan = self.store.get_plan(self.task_id)
        harness = {}
        try:
            harness = self.store.get_harness_report(self.task_id)
        except FileNotFoundError:
            pass

        summary = {
            "task_id": self.task_id,
            "root_path": self.meta["root_path"],
            "status": self.status,
            "created_at": self.meta.get("created_at", ""),
            "finished_at": self.now(),
            "files_total": scan.get("stats", {}).get("file_count", 0),
            "categories": len(plan.get("categories", [])),
            "moves_planned": len(plan.get("moves", [])),
            "verdict": harness.get("verdict", "unknown"),
            "pipeline": self._state_log,
        }
        self.store.save_summary(self.task_id, summary)
        logger.info("Summary written for task %s", self.task_id[:8])
        return summary
