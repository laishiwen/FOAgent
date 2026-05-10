"""Task service - high-level API for the file organization workflow."""

from app.core.logging import get_logger
from app.graph.state import WorkflowStateMachine
from app.storage import TaskStore

logger = get_logger(__name__)


class TaskService:
    """High-level service that runs the full workflow pipeline."""

    def __init__(self, store: TaskStore = None):
        self.store = store or TaskStore()

    def create_task(self, root_path: str, dry_run: bool = True) -> dict:
        """Create a new task. Frontend only provides root_path."""
        meta = self.store.create(root_path, dry_run)
        logger.info("Created task %s for %s (dry_run=%s)",
                     meta["task_id"], root_path, dry_run)
        return meta

    def run_planning_phase(self, task_id: str) -> dict:
        """Run scan + Agent A + Agent B + plan generation.

        Returns the plan dict with status.
        """
        wf = WorkflowStateMachine(task_id, self.store)

        # Node 1: Scan
        logger.info("--- Node 1: ScanParentLevel ---")
        scan_result = wf.node_scan()
        if wf.status == "failed":
            return {"status": "failed", "error": scan_result.get("error")}

        # Node 2: Analyze
        logger.info("--- Node 2: AnalyzeFileAttributes ---")
        files = wf.node_analyze(scan_result)
        if not files:
            wf.transition("planned")
            return {
                "status": "planned",
                "task_id": task_id,
                "current_files": [],
                "target_structure": {},
                "plan": {"moves": [], "directories_to_create": []},
                "needs_review": False,
            }

        # Node 3: Agent A - Associations
        logger.info("--- Node 3: Agent A (Association) ---")
        associations = wf.node_detect_associations(files)

        # Node 4: Agent B - Categories
        logger.info("--- Node 4: Agent B (Naming) ---")
        categories = wf.node_build_categories(associations, files)

        # Node 5: Generate Plan
        logger.info("--- Node 5: GeneratePlan ---")
        plan = wf.node_generate_plan(categories, associations)

        # Transition to planned before validation
        wf.transition("planned")

        # Node 6: Validate
        logger.info("--- Node 6: ValidatePlan ---")
        plan = wf.node_validate(plan)

        current_files = [f["name"] for f in files]
        target_structure = {
            "root_path": wf.meta["root_path"],
            "categories": [
                {"name": c["category_name"], "members": [
                    os.path.basename(m) for m in c.get("members", [])
                ]}
                for c in plan.get("categories", [])
            ],
        }

        return {
            "status": wf.status,
            "task_id": task_id,
            "current_files": current_files,
            "target_structure": target_structure,
            "plan": {
                "directories_to_create": plan.get("directories_to_create", []),
                "moves": [
                    {"source_path": m["source_path"],
                     "target_path": m["target_path"],
                     "category": m.get("category", ""),
                     "confidence": m.get("confidence", 0)}
                    for m in plan.get("moves", [])
                ],
                "conflicts": plan.get("conflicts", []),
                "needs_review_items": [
                    {"source_path": m["source_path"],
                     "target_path": m["target_path"]}
                    for m in plan.get("needs_review_items", [])
                ],
            },
            "needs_review": wf.status in ("review_required",),
            "notes": plan.get("notes", []),
        }

    def run_execution_phase(self, task_id: str) -> dict:
        """Run execute + verify + harness check.

        Returns execution result with harness report.
        """
        wf = WorkflowStateMachine(task_id, self.store)
        plan = self.store.get_plan(task_id)

        # Node 8: Execute
        logger.info("--- Node 8: ExecutePlan ---")
        execution_log = wf.node_execute(plan)

        if wf.status == "failed":
            return {
                "status": "failed",
                "task_id": task_id,
                "execution_log": execution_log,
                "harness_report": None,
            }

        # Node 9: Verify
        logger.info("--- Node 9: VerifyExecution ---")
        verify_result = wf.node_verify(execution_log)

        # Node 10: Harness Check
        logger.info("--- Node 10: HarnessCheck ---")
        harness_report = wf.node_harness_check()

        return {
            "status": "completed",
            "task_id": task_id,
            "execution_log": execution_log,
            "verify_result": verify_result,
            "harness_report": harness_report,
        }

    def run_rollback(self, task_id: str) -> dict:
        """Run rollback for a failed or completed task."""
        wf = WorkflowStateMachine(task_id, self.store)
        logger.info("--- Node 11: Rollback ---")
        result = wf.node_rollback()
        return {
            "status": "rolled_back",
            "task_id": task_id,
            "rollback_log": result,
        }

    def get_task_status(self, task_id: str) -> dict:
        """Get current task status and available data."""
        meta = self.store.get(task_id)
        result = {
            "task_id": task_id,
            "status": meta["status"],
            "root_path": meta["root_path"],
            "dry_run": meta.get("dry_run", True),
            "created_at": meta.get("created_at", ""),
        }

        # Try to include available data
        try:
            scan = self.store.get_scan(task_id)
            result["scan"] = {
                "file_count": scan.get("stats", {}).get("file_count", 0),
                "files": [f["name"] for f in scan.get("files", [])],
            }
        except FileNotFoundError:
            pass

        try:
            plan = self.store.get_plan(task_id)
            result["plan_summary"] = {
                "categories": len(plan.get("categories", [])),
                "moves": len(plan.get("moves", [])),
                "directories_to_create": len(plan.get("directories_to_create", [])),
            }
        except FileNotFoundError:
            pass

        try:
            result["harness_report"] = self.store.get_harness_report(task_id)
        except FileNotFoundError:
            pass

        return result


import os  # noqa: E402
