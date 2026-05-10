"""Workflow state machine - orchestrates the 12-node pipeline."""

from datetime import datetime, timezone
import json
import os

from app.core.logging import get_logger
from app.storage import TaskStore

logger = get_logger(__name__)

VALID_TRANSITIONS = {
    "created":      ["scanning"],
    "scanning":     ["planned", "review_required", "failed"],
    "planned":      ["review_required", "approved", "failed"],
    "review_required": ["approved", "failed"],
    "approved":     ["executing", "failed"],
    "executing":    ["completed", "failed"],
    "completed":    ["rolled_back"],
    "failed":       ["rolled_back"],
    "rolled_back":  [],
}


class WorkflowStateMachine:
    """Orchestrates the file organization workflow."""

    def __init__(self, task_id: str, store: TaskStore = None):
        self.task_id = task_id
        self.store = store or TaskStore()
        self.meta = self.store.get(task_id)

    @property
    def status(self) -> str:
        return self.store.get(self.task_id)["status"]

    def transition(self, new_status: str):
        current = self.status
        allowed = VALID_TRANSITIONS.get(current, [])
        if new_status not in allowed and current != new_status:
            logger.warning(
                "Non-standard transition: %s -> %s (allowed: %s)",
                current, new_status, allowed,
            )
        self.store.update_status(self.task_id, new_status)
        logger.info("Task %s: %s -> %s", self.task_id[:8], current, new_status)

    def now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---- Node implementations ----

    def node_scan(self) -> dict:
        """Node 1: ScanParentLevel - scan parent dir for files."""
        from app.tools.tool_runner import scan_parent_dir

        self.transition("scanning")
        root_path = self.meta["root_path"]

        data = {"root_path": root_path, "task_id": self.task_id}
        result = json.loads(scan_parent_dir(data))

        if not result["success"]:
            self.transition("failed")
            return result

        self.store.save_scan(self.task_id, result)
        return result

    def node_analyze(self, scan_result: dict) -> list:
        """Node 2: AnalyzeFileAttributes - get detailed file info."""
        from app.tools.tool_runner import get_file_info

        files = scan_result.get("files", [])
        enriched = []

        for f in files:
            data = {"file_path": f["path"], "task_id": self.task_id}
            result = json.loads(get_file_info(data))
            if result["success"]:
                # Merge scan data with file info
                merged = {**f, **{k: v for k, v in result.items()
                                  if k not in ("success", "error", "file_path")}}
                enriched.append(merged)
            else:
                enriched.append(f)

        return enriched

    def node_detect_associations(self, files: list) -> dict:
        """Node 3: Agent A - detect file associations."""
        from app.agents import run_agent_a

        result = run_agent_a(files, self.meta["root_path"])
        self.store.save_associations(self.task_id, result)
        return result

    def node_build_categories(self, associations: dict, files: list) -> dict:
        """Node 4: Agent B - generate category names and classification."""
        from app.agents import run_agent_b

        result = run_agent_b(associations, files)
        return result

    def node_generate_plan(self, categories_result: dict,
                           associations: dict) -> dict:
        """Node 5: GeneratePlan - deterministic plan from categories."""
        root_path = self.meta["root_path"]
        categories = categories_result.get("categories", [])
        category_order = categories_result.get("category_order", [])

        directories_to_create = []
        moves = []
        needs_review_items = []

        for cat in categories:
            cat_name = cat["category_name"]
            dir_path = os.path.join(root_path, cat_name)
            directories_to_create.append(dir_path)

            for member_path in cat.get("members", []):
                fname = os.path.basename(member_path)
                target_path = os.path.join(dir_path, fname)

                move = {
                    "source_path": member_path,
                    "target_path": target_path,
                    "category": cat_name,
                    "confidence": cat.get("confidence", 0.5),
                }
                moves.append(move)

                if cat.get("needs_review"):
                    needs_review_items.append(move)

        # Check for conflicts (same target from different sources)
        targets = {}
        conflicts = []
        for m in moves:
            tgt = m["target_path"]
            if tgt in targets:
                conflicts.append({
                    "target": tgt,
                    "source_a": targets[tgt],
                    "source_b": m["source_path"],
                })
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
            "category_order": category_order,
            "notes": categories_result.get("notes", []),
        }

        self.store.save_plan(self.task_id, plan)
        return plan

    def node_validate(self, plan: dict) -> dict:
        """Node 6: ValidatePlan - dry-run check."""
        from app.tools.tool_runner import bash_dry_run_moves

        data = {
            "task_id": self.task_id,
            "root_path": self.meta["root_path"],
            "moves": plan.get("moves", []),
        }
        result = json.loads(bash_dry_run_moves(data))

        plan["validation"] = result
        self.store.save_plan(self.task_id, plan)

        if not result.get("can_execute", False) or plan.get("conflicts"):
            plan["needs_review"] = True

        if plan.get("needs_review_items") or plan.get("needs_review"):
            self.transition("review_required")
        else:
            self.transition("approved")

        return plan

    def node_execute(self, plan: dict) -> dict:
        """Node 8: ExecutePlan - create dirs and move files."""
        from app.tools.tool_runner import bash_create_dirs, bash_move_files

        if self.meta.get("dry_run", True):
            logger.info("DRY RUN: skipping actual execution")
            execution_log = {
                "task_id": self.task_id,
                "root_path": self.meta["root_path"],
                "started_at": self.now(),
                "finished_at": self.now(),
                "status": "dry_run_skipped",
                "steps": [],
                "summary": {
                    "created_directories": 0,
                    "moved_files": 0,
                    "failed_steps": 0,
                    "rolled_back_steps": 0,
                },
            }
            self.store.save_execution_log(self.task_id, execution_log)
            return execution_log

        self.transition("executing")

        # Step 1: Create directories
        dirs_data = {
            "task_id": self.task_id,
            "root_path": self.meta["root_path"],
            "dry_run": False,
            "directories": [
                os.path.basename(d) for d in plan.get("directories_to_create", [])
            ],
        }
        dirs_result = json.loads(bash_create_dirs(dirs_data))
        if not dirs_result["success"]:
            logger.error("Directory creation failed")
            self.transition("failed")
            execution_log = {
                "task_id": self.task_id,
                "root_path": self.meta["root_path"],
                "started_at": self.now(),
                "finished_at": self.now(),
                "status": "failed",
                "steps": dirs_result.get("steps", []),
                "summary": {
                    "created_directories": 0,
                    "moved_files": 0,
                    "failed_steps": len(dirs_result.get("steps", [])),
                    "rolled_back_steps": 0,
                },
            }
            self.store.save_execution_log(self.task_id, execution_log)
            return execution_log

        # Step 2: Move files
        moves_data = {
            "task_id": self.task_id,
            "root_path": self.meta["root_path"],
            "moves": plan.get("moves", []),
        }
        moves_result = json.loads(bash_move_files(moves_data))

        # Combine steps
        all_steps = dirs_result.get("steps", []) + moves_result.get("steps", [])

        execution_log = {
            "task_id": self.task_id,
            "root_path": self.meta["root_path"],
            "started_at": self.now(),
            "finished_at": self.now(),
            "status": "completed" if moves_result["success"] else "failed",
            "steps": all_steps,
            "summary": {
                "created_directories": len(dirs_result.get("steps", [])),
                "moved_files": moves_result.get("summary", {}).get("completed", 0),
                "failed_steps": moves_result.get("summary", {}).get("failed", 0),
                "rolled_back_steps": 0,
            },
        }

        self.store.save_execution_log(self.task_id, execution_log)

        if not moves_result["success"]:
            self.transition("failed")
        else:
            self.transition("completed")

        return execution_log

    def node_verify(self, execution_log: dict) -> dict:
        """Node 9: VerifyExecution - bash-level file check."""
        root_path = self.meta["root_path"]
        scan = self.store.get_scan(self.task_id)
        plan = self.store.get_plan(self.task_id)

        original_files = {f["path"] for f in scan.get("files", [])}
        moved_sources = set()
        for step in execution_log.get("steps", []):
            if step.get("step_type") == "move_file" and step.get("status") == "completed":
                moved_sources.add(step.get("source_path", ""))

        missing_moves = original_files - moved_sources
        extra_moves = moved_sources - original_files

        return {
            "success": len(missing_moves) == 0,
            "original_count": len(original_files),
            "moved_count": len(moved_sources),
            "missing": list(missing_moves) if missing_moves else [],
            "extra": list(extra_moves) if extra_moves else [],
        }

    def node_harness_check(self) -> dict:
        """Node 10: Harness Agent - semantic final review."""
        from app.agents import run_harness_agent

        try:
            scan = self.store.get_scan(self.task_id)
            associations = self.store.get_associations(self.task_id)
            plan = self.store.get_plan(self.task_id)
            execution_log = self.store.get_execution_log(self.task_id)
        except FileNotFoundError as e:
            logger.error("Harness: missing data: %s", e)
            return {"verdict": "fail", "overall_assessment": f"缺少数据: {e}"}

        files = scan.get("files", [])
        result = run_harness_agent(files, associations, plan, execution_log)
        self.store.save_harness_report(self.task_id, result)
        return result

    def node_rollback(self) -> dict:
        """Node 11: Rollback - undo moves based on execution log."""
        from app.tools.tool_runner import bash_rollback

        exec_log_path = os.path.join(
            self.store._task_dir(self.task_id), "execution_log.json"
        )

        data = {
            "task_id": self.task_id,
            "root_path": self.meta["root_path"],
            "execution_log_path": exec_log_path,
        }
        result = json.loads(bash_rollback(data))
        self.store.save_rollback_log(self.task_id, result)
        self.transition("rolled_back")
        return result
