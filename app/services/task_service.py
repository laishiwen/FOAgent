"""Task service - high-level API with ID-based workflow and summary."""

import os

from core.logging import get_logger
from graph.state import WorkflowStateMachine
from storage import TaskStore

logger = get_logger(__name__)


class TaskService:
    def __init__(self, store: TaskStore = None):
        self.store = store or TaskStore()

    def create_task(self, root_path: str, dry_run: bool = True) -> dict:
        meta = self.store.create(root_path, dry_run)
        logger.info("Created task %s for %s", meta["task_id"], root_path)
        return meta

    def run_planning_phase(self, task_id: str) -> dict:
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
            return {"status": "planned", "task_id": task_id,
                    "current_files": [], "target_structure": {},
                    "plan": {"moves": [], "directories_to_create": []},
                    "needs_review": False}

        # Node 3: Agent A
        logger.info("--- Node 3: Agent A ---")
        associations = wf.node_detect_associations(files)

        # Node 4: Agent B
        logger.info("--- Node 4: Agent B ---")
        categories = wf.node_build_categories(associations, files)

        # Node 5: Generate Plan (ID→path)
        logger.info("--- Node 5: GeneratePlan ---")
        plan = wf.node_generate_plan(categories, associations)

        # Node 6: Validate
        wf.transition("planned")
        logger.info("--- Node 6: ValidatePlan ---")
        plan = wf.node_validate(plan)

        # Build response
        schema = self.store.get_source_schema(task_id)
        target_structure = {"root_path": wf.meta["root_path"], "categories": []}
        for cat in plan.get("categories", []):
            member_ids = cat.get("member_ids", cat.get("members", []))
            members = [schema.get(str(mid), {}).get("name", str(mid))
                       for mid in member_ids]
            target_structure["categories"].append({
                "name": cat["category_name"], "members": members,
                "member_ids": member_ids,
                "confidence": cat.get("confidence", 0),
            })

        return {
            "status": wf.status, "task_id": task_id,
            "current_files": [schema.get(f["id"], {}).get("name", f["name"])
                              for f in files],
            "source_schema": schema,
            "target_structure": target_structure,
            "plan": {
                "directories_to_create": plan.get("directories_to_create", []),
                "moves": [{"file_id": m["file_id"],
                           "source_path": m["source_path"],
                           "target_path": m["target_path"],
                           "category": m.get("category", ""),
                           "confidence": m.get("confidence", 0)}
                          for m in plan.get("moves", [])],
                "conflicts": plan.get("conflicts", []),
                "needs_review_items": plan.get("needs_review_items", []),
            },
            "needs_review": wf.status in ("review_required",),
            "notes": plan.get("notes", []),
        }

    def run_execution_phase(self, task_id: str) -> dict:
        wf = WorkflowStateMachine(task_id, self.store)
        plan = self.store.get_plan(task_id)

        logger.info("--- Node 8: ExecutePlan ---")
        execution_log = wf.node_execute(plan)

        if wf.status == "failed":
            return {"status": "failed", "task_id": task_id,
                    "execution_log": execution_log, "harness_report": None}

        logger.info("--- Node 9: VerifyExecution ---")
        verify_result = wf.node_verify(execution_log)

        logger.info("--- Node 10: HarnessCheck ---")
        harness_report = wf.node_harness_check()

        # Write final summary
        summary = wf.write_summary()

        return {"status": "completed", "task_id": task_id,
                "execution_log": execution_log, "verify_result": verify_result,
                "harness_report": harness_report, "summary": summary}

    def run_rollback(self, task_id: str) -> dict:
        wf = WorkflowStateMachine(task_id, self.store)
        result = wf.node_rollback()
        return {"status": "rolled_back", "task_id": task_id,
                "rollback_log": result}

    def adjust_plan(self, task_id: str, adjustments: dict) -> dict:
        """Accept frontend adjustments to the plan before execution."""
        plan = self.store.get_plan(task_id)
        schema = self.store.get_source_schema(task_id)

        for move_adj in adjustments.get("moves", []):
            fid = move_adj.get("file_id")
            new_category = move_adj.get("category")
            if fid and new_category:
                for m in plan["moves"]:
                    if m["file_id"] == fid:
                        entry = schema.get(str(fid), {})
                        fname = entry.get("name", str(fid))
                        m["target_path"] = os.path.join(
                            plan["root_path"], new_category, fname)
                        m["category"] = new_category

        for cat_adj in adjustments.get("categories", []):
            old_name = cat_adj.get("old_name")
            new_name = cat_adj.get("new_name")
            if old_name and new_name:
                for m in plan["moves"]:
                    if m["category"] == old_name:
                        m["category"] = new_name
                        fname = os.path.basename(m["target_path"])
                        m["target_path"] = os.path.join(
                            plan["root_path"], new_name, fname)
                plan["directories_to_create"] = [
                    d for d in plan["directories_to_create"]
                    if os.path.basename(d) != old_name
                ]
                new_dir = os.path.join(plan["root_path"], new_name)
                if new_dir not in plan["directories_to_create"]:
                    plan["directories_to_create"].append(new_dir)

        plan["needs_review"] = False
        self.store.save_plan(task_id, plan)
        self.store.update_status(task_id, "approved")
        return {"status": "approved", "task_id": task_id}

    def get_task_status(self, task_id: str) -> dict:
        meta = self.store.get(task_id)
        result = {"task_id": task_id, "status": meta["status"],
                  "root_path": meta["root_path"],
                  "dry_run": meta.get("dry_run", True),
                  "created_at": meta.get("created_at", "")}
        try:
            result["state"] = self.store.get_state(task_id)
        except FileNotFoundError:
            pass
        try:
            result["summary"] = self.store.get_summary(task_id)
        except FileNotFoundError:
            pass
        try:
            result["harness_report"] = self.store.get_harness_report(task_id)
        except FileNotFoundError:
            pass
        return result
