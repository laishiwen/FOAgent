"""CLI entry point for the Agent File Organizer.

Usage:
    uv run agent-organizer plan /path/to/dir
    uv run agent-organizer run /path/to/dir
    uv run agent-organizer serve --port 5050
"""

import argparse
import json
import sys

from services.task_service import TaskService
from services.audit_service import AuditService


def cmd_plan(args):
    svc = TaskService()
    task = svc.create_task(args.path, dry_run=not args.execute)
    print(f"Task created: {task['task_id']}")
    result = svc.run_planning_phase(task["task_id"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def cmd_run(args):
    svc = TaskService()
    task = svc.create_task(args.path, dry_run=False)
    print(f"Task created: {task['task_id']}")

    print("\n=== Planning Phase ===")
    plan_result = svc.run_planning_phase(task["task_id"])
    print(json.dumps(plan_result, ensure_ascii=False, indent=2))

    if plan_result["status"] in ("failed",):
        print("\nPlanning failed, aborting.")
        return plan_result

    print("\n=== Execution Phase ===")
    exec_result = svc.run_execution_phase(task["task_id"])
    print(json.dumps(exec_result, ensure_ascii=False, indent=2))

    if exec_result.get("harness_report"):
        print("\n=== Harness Report ===")
        hr = exec_result["harness_report"]
        print(f"Verdict: {hr.get('verdict', 'unknown')}")
        print(f"Assessment: {hr.get('overall_assessment', '')}")
        for issue in hr.get("issues", []):
            print(f"  - {issue}")

    return exec_result


def cmd_status(args):
    svc = TaskService()
    result = svc.get_task_status(args.task_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def cmd_rollback(args):
    svc = TaskService()
    result = svc.run_rollback(args.task_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def cmd_serve(args):
    from server import run_server
    run_server(port=args.port)


def main():
    parser = argparse.ArgumentParser(
        description="Agent File Organizer - Smart file classification"
    )
    sub = parser.add_subparsers(dest="command")

    p_plan = sub.add_parser("plan", help="Run planning phase only (dry-run)")
    p_plan.add_argument("path", help="Target directory path")
    p_plan.add_argument("--execute", action="store_true",
                        help="Mark as executable (not just dry-run)")

    p_run = sub.add_parser("run", help="Run full pipeline (plan + execute)")
    p_run.add_argument("path", help="Target directory path")

    p_status = sub.add_parser("status", help="Check task status")
    p_status.add_argument("task_id", help="Task ID")

    p_rollback = sub.add_parser("rollback", help="Rollback a task")
    p_rollback.add_argument("task_id", help="Task ID")

    p_serve = sub.add_parser("serve", help="Start web server")
    p_serve.add_argument("--port", type=int, default=5050,
                         help="Server port (default: 5050)")

    args = parser.parse_args()

    if args.command == "plan":
        cmd_plan(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "rollback":
        cmd_rollback(args)
    elif args.command == "serve":
        cmd_serve(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
